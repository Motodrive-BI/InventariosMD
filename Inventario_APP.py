import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import uuid

# 1. CONFIGURACIÓN
st.set_page_config(page_title="Inventario Motodrive - Microsoft Login", layout="wide")

# 2. CONEXIÓN Y DATOS
conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1mbzAa6zn_otA_y1932IyW8fSuf8XOehzarvxZBpleu0/edit?usp=sharing"

@st.cache_data(ttl=60)
def load_data():
    inv = conn.read(spreadsheet=URL, worksheet="Inventario")
    usr = conn.read(spreadsheet=URL, worksheet="Usuarios")
    age = conn.read(spreadsheet=URL, worksheet="Agencias")
    return inv, usr, age

df_inv, df_usr, df_age = load_data()

# --- SISTEMA DE LOGIN DE MICROSOFT (SIMULADO) ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.container()
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("https://upload.wikimedia.org/wikipedia/commons/4/44/Microsoft_logo.svg", width=200)
        st.subheader("Inicio de Sesión Corporativo")
        email_input = st.text_input("Correo electrónico de Microsoft", placeholder="usuario@motodrive.com")
        
        if st.button("Iniciar Sesión", use_container_width=True):
            # Validamos que el correo termine en tu dominio y esté en la lista
            if "@" in email_input and email_input in df_usr['Correo'].values:
                st.session_state.autenticado = True
                st.session_state.user_email = email_input
                st.rerun()
            else:
                st.error("Correo no autorizado o formato incorrecto.")
    st.stop() # Detiene la app aquí si no está logueado

# --- SI LLEGA AQUÍ, EL USUARIO YA SE LOGUEÓ ---
user_email = st.session_state.user_email
datos_usuario = df_usr[df_usr['Correo'] == user_email].iloc[0]
nombre_regional = datos_usuario[df_usr.columns[0]]

gerentes = df_usr.iloc[:, 0].dropna().tolist()
sucursales = df_age.iloc[:, 0].dropna().tolist()

# 3. LÓGICA DE CÁLCULO
for g in gerentes:
    df_inv[g] = pd.to_numeric(df_inv[g], errors='coerce').fillna(0)
df_inv['Disponible Inicial'] = pd.to_numeric(df_inv['Disponible Inicial'], errors='coerce').fillna(0)
df_inv['Disponible Restante'] = df_inv['Disponible Inicial'] - df_inv[gerentes].sum(axis=1)

# 4. INTERFAZ
st.title(f"🏍️ Bienvenid@, {nombre_regional}")
st.sidebar.write(f"Sesión activa: **{user_email}**")
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
    
    with st.expander(f"Confirmar registro: {row['Modelo']} ({row['Año Modelo']})", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            sucursal = st.selectbox("Sucursal Destino:", sucursales)
        with c2:
            disp = int(row['Disponible Restante'])
            cant = st.number_input("Cantidad:", min_value=1, max_value=disp if disp > 0 else 1)
        
        if disp <= 0:
            st.error("No hay unidades disponibles.")
        elif st.button("Confirmar Apartado", use_container_width=True):
            # Guardar en Inventario
            idx = df_inv.index[df_inv['Item Number'] == item_id][0]
            df_inv.at[idx, nombre_regional] += cant
            conn.update(spreadsheet=URL, worksheet="Inventario", data=df_inv)
            
            # Guardar en Historial
            df_movs = conn.read(spreadsheet=URL, worksheet="Movimientos_Apartados")
            nuevo = pd.DataFrame([{
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
            df_movs = pd.concat([df_movs, nuevo], ignore_index=True)
            conn.update(spreadsheet=URL, worksheet="Movimientos_Apartados", data=df_movs)
            
            st.success("¡Registrado!")
            st.cache_data.clear()
            st.rerun()

# 5. TABLA DE VISTA
st.dataframe(df_inv[['Item Number', 'Modelo', 'Color', 'Año Modelo', 'Disponible Inicial', 'Disponible Restante']], 
             use_container_width=True, hide_index=True)
