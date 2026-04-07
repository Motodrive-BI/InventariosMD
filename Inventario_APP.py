import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import uuid

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="Inventario Motodrive - Control de Stock", layout="wide")

# 2. CONEXIÓN Y CARGA DE DATOS
conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1mbzAa6zn_otA_y1932IyW8fSuf8XOehzarvxZBpleu0/edit?usp=sharing"

@st.cache_data(ttl=60)
def load_data():
    try:
        inv = conn.read(spreadsheet=URL, worksheet="Inventario")
        usr = conn.read(spreadsheet=URL, worksheet="Usuarios")
        age = conn.read(spreadsheet=URL, worksheet="Agencias")
        return inv, usr, age
    except Exception as e:
        st.error("🚨 Error de conexión o permisos con Google Sheets.")
        st.stop()

df_inv, df_usr, df_age = load_data()

# --- SISTEMA DE LOGIN ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("https://upload.wikimedia.org/wikipedia/commons/4/44/Microsoft_logo.svg", width=150)
        st.subheader("Inicio de Sesión Corporativo")
        email_input = st.text_input("Correo electrónico de Microsoft", placeholder="usuario@motodrive.com")
        if st.button("Iniciar Sesión", use_container_width=True):
            email_clean = email_input.strip().lower()
            df_usr['Correo'] = df_usr['Correo'].str.strip().str.lower()
            if email_clean in df_usr['Correo'].values:
                st.session_state.autenticado = True
                st.session_state.user_email = email_clean
                st.rerun()
            else:
                st.error("Correo no autorizado.")
    st.stop()

# --- CÁLCULOS Y FORMATEO DE NÚMEROS ---
user_email = st.session_state.user_email
datos_usuario = df_usr[df_usr['Correo'] == user_email].iloc[0]
nombre_regional = datos_usuario.iloc[0]

gerentes_en_tabla = [g for g in df_usr.iloc[:, 0].dropna().tolist() if g in df_inv.columns]

# Convertir columnas de gerentes a entero
for g in gerentes_en_tabla:
    df_inv[g] = pd.to_numeric(df_inv[g], errors='coerce').fillna(0).astype(int)

# Convertir Disponible Inicial y calcular Restante como entero
df_inv['Disponible Inicial'] = pd.to_numeric(df_inv['Disponible Inicial'], errors='coerce').fillna(0).astype(int)
df_inv['Disponible Restante'] = (df_inv['Disponible Inicial'] - df_inv[gerentes_en_tabla].sum(axis=1)).astype(int)

# 3. INTERFAZ
col_tit, col_ref = st.columns([4, 1])
with col_tit:
    st.title(f"🏍️ Bienvenido, {nombre_regional}")
with col_ref:
    if st.button("🔄 Sincronizar Datos"):
        st.cache_data.clear()
        st.rerun()

st.sidebar.metric("Tus Apartados", int(df_inv[nombre_regional].sum()))
if st.sidebar.button("Cerrar Sesión"):
    st.session_state.autenticado = False
    st.rerun()

# --- BUSCADOR Y APARTADO ---
st.subheader("📋 Registro de Apartados")
opciones_modelos = df_inv.apply(
    lambda x: f"{x['Item Number']} - {x['Modelo']} ({x['Color']}) - {x['Año Modelo']}", axis=1
).tolist()

seleccion_modelo = st.selectbox("Selecciona la unidad:", ["Seleccione..."] + opciones_modelos)

if seleccion_modelo != "Seleccione...":
    item_id = seleccion_modelo.split(" - ")[0]
    row = df_inv[df_inv['Item Number'] == item_id].iloc[0]
    disp_real = int(row['Disponible Restante'])
    
    with st.expander(f"Confirmar registro: {row['Modelo']} ({row['Año Modelo']})", expanded=True):
        if disp_real <= 0:
            st.error("🚫 No hay stock disponible. Movimiento bloqueado.")
        else:
            c1, c2 = st.columns(2)
            with c1:
                sucursales = df_age.iloc[:, 0].dropna().tolist()
                sucursal = st.selectbox("Sucursal Destino:", sucursales)
            with c2:
                cant = st.number_input("Cantidad:", min_value=1, max_value=disp_real, step=1)
            
            if st.button("Confirmar Apartado", use_container_width=True):
                idx = df_inv.index[df_inv['Item Number'] == item_id][0]
                df_inv.at[idx, nombre_regional] += cant
                conn.update(spreadsheet=URL, worksheet="Inventario", data=df_inv)
                
                df_movs = conn.read(spreadsheet=URL, worksheet="Movimientos_Apartados")
                nuevo = pd.DataFrame([{
                    "ID_Apartado": str(uuid.uuid4())[:8].upper(),
                    "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "Item_Number": row['Item Number'],
                    "Modelo": row['Modelo'],
                    "Color": row['Color'],
                    "Año Modelo": row['Año Modelo'],
                    "Sucursal_Destino": sucursal,
                    "Cantidad": int(cant),
                    "Nombre Regional": nombre_regional
                }])
                df_movs = pd.concat([df_movs, nuevo], ignore_index=True)
                conn.update(spreadsheet=URL, worksheet="Movimientos_Apartados", data=df_movs)
                
                st.success("✅ ¡Registrado!")
                st.cache_data.clear()
                st.rerun()

# 4. VISUALIZACIÓN (TABLA)
st.markdown("---")
cols_mostrar = ['Item Number', 'Modelo', 'Color', 'Año Modelo', 'Disponible Inicial', 'Disponible Restante']

def color_stock(val):
    color = '#FF4B4B' if val <= 0 else None
    return f'color: {color}; font-weight: bold' if color else ''

# Mostramos la tabla con formato de número entero (sin decimales)
st.dataframe(
    df_inv[cols_mostrar].style.map(color_stock, subset=['Disponible Restante']).format(precision=0),
    use_container_width=True, 
    hide_index=True
)
