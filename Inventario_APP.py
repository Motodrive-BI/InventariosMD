import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import uuid

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="Inventario Motodrive - Control de Stock", layout="wide")

# 2. CONEXIÓN Y CARGA DE DATOS (Con manejo de errores de permiso)
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
        st.info("Asegúrate de haber compartido el Excel con el correo de la cuenta de servicio.")
        st.stop()

df_inv, df_usr, df_age = load_data()

# --- SISTEMA DE LOGIN ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("https://upload.wikimedia.org/wikipedia/commons/4/44/Microsoft_logo.svg", width=200)
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

# --- VALIDACIÓN DE COLUMNAS Y CÁLCULO ---
user_email = st.session_state.user_email
datos_usuario = df_usr[df_usr['Correo'] == user_email].iloc[0]
nombre_regional = datos_usuario.iloc[0]

# Identificar gerentes que tienen columna en Inventario
gerentes_en_tabla = [g for g in df_usr.iloc[:, 0].dropna().tolist() if g in df_inv.columns]

for g in gerentes_en_tabla:
    df_inv[g] = pd.to_numeric(df_inv[g], errors='coerce').fillna(0)

df_inv['Disponible Inicial'] = pd.to_numeric(df_inv['Disponible Inicial'], errors='coerce').fillna(0)
df_inv['Disponible Restante'] = df_inv['Disponible Inicial'] - df_inv[gerentes_en_tabla].sum(axis=1)

# 3. INTERFAZ Y BOTÓN DE REFRESH
col_tit, col_ref = st.columns([4, 1])
with col_tit:
    st.title(f"🏍️ Bienvenido, {nombre_regional}")
with col_ref:
    # BOTÓN DE ACTUALIZACIÓN
    if st.button("🔄 Sincronizar Datos"):
        st.cache_data.clear()
        st.rerun()

st.sidebar.metric("Tus Apartados", int(df_inv[nombre_regional].sum()))
if st.sidebar.button("Cerrar Sesión"):
    st.session_state.autenticado = False
    st.rerun()

# --- BUSCADOR Y APARTADO CON RESTRICCIÓN ---
st.subheader("📋 Registro de Apartados")
opciones_modelos = df_inv.apply(
    lambda x: f"{x['Item Number']} - {x['Modelo']} ({x['Color']}) - {x['Año Modelo']}", axis=1
).tolist()

seleccion_modelo = st.selectbox("Selecciona la unidad:", ["Seleccione..."] + opciones_modelos)

if seleccion_modelo != "Seleccione...":
    item_id = seleccion_modelo.split(" - ")[0]
    row = df_inv[df_inv['Item Number'] == item_id].iloc[0]
    disponible_real = int(row['Disponible Restante'])
    
    with st.expander(f"Confirmar registro: {row['Modelo']} ({row['Año Modelo']})", expanded=True):
        # RESTRICCIÓN DE STOCK EN 0
        if disponible_real <= 0:
            st.error(f"🚫 No hay stock disponible para el modelo {row['Modelo']}. No se pueden realizar movimientos.")
        else:
            c1, c2 = st.columns(2)
            with c1:
                sucursales = df_age.iloc[:, 0].dropna().tolist()
                sucursal = st.selectbox("Sucursal Destino:", sucursales)
            with c2:
                cant = st.number_input("Cantidad a apartar:", min_value=1, max_value=disponible_real, step=1)
            
            if st.button("Confirmar Apartado", use_container_width=True):
                # Guardar cambios
                idx = df_inv.index[df_inv['Item Number'] == item_id][0]
                df_inv.at[idx, nombre_regional] += cant
                conn.update(spreadsheet=URL, worksheet="Inventario", data=df_inv)
                
                # Registrar Historial
                df_movs = conn.read(spreadsheet=URL, worksheet="Movimientos_Apartados")
                nuevo_mov = pd.DataFrame([{
                    "ID_Apartado": str(uuid.uuid4())[:8].upper(),
                    "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "Item_Number": row['Item Number'],
                    "Modelo": row['Modelo'],
                    "Color": row['Color'],
                    "Año Modelo": row['Año Modelo'],
                    "Sucursal_Destino": sucursal,
                    "Cantidad": cant,
                    "Nombre Regional": nombre_regional
                }])
                df_movs = pd.concat([df_movs, nuevo_mov], ignore_index=True)
                conn.update(spreadsheet=URL, worksheet="Movimientos_Apartados", data=df_movs)
                
                st.success("✅ ¡Apartado registrado exitosamente!")
                st.cache_data.clear()
                st.rerun()

# 4. VISUALIZACIÓN DE TABLA
st.markdown("---")
cols_mostrar = ['Item Number', 'Modelo', 'Color', 'Año Modelo', 'Disponible Inicial', 'Disponible Restante']

# Aplicar estilo visual: Resaltar en rojo si el disponible es 0
def color_stock(val):
    color = 'red' if val <= 0 else 'white'
    return f'color: {color}'

st.dataframe(
    df_inv[cols_mostrar].style.applymap(color_stock, subset=['Disponible Restante']),
    use_container_width=True, 
    hide_index=True
)
