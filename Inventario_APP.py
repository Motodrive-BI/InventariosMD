import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import uuid

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="Inventario Motodrive - Privado", layout="wide")

# 2. VERIFICACIÓN DE USUARIO (Google Login)
# Streamlit Cloud pasa el correo del usuario logueado en st.user
if not st.user.email:
    st.error("⚠️ Acceso denegado. Debes iniciar sesión con tu correo de Motodrive.")
    st.stop()

user_email = st.user.email

# 3. CONEXIÓN Y DATOS
conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1mbzAa6zn_otA_y1932IyW8fSuf8XOehzarvxZBpleu0/edit?usp=sharing"

@st.cache_data(ttl=60)
def load_data():
    inv = conn.read(spreadsheet=URL, worksheet="Inventario")
    usr = conn.read(spreadsheet=URL, worksheet="Usuarios")
    age = conn.read(spreadsheet=URL, worksheet="Agencias")
    return inv, usr, age

df_inv, df_usr, df_age = load_data()

# 4. VALIDAR SI EL CORREO ESTÁ AUTORIZADO
# Tu hoja 'Usuarios' debe tener una columna llamada 'Correo'
if user_email not in df_usr['Correo'].values:
    st.error(f"El correo {user_email} no está autorizado en la base de datos.")
    st.stop()

# Obtener el nombre del Regional basado en su correo
datos_usuario = df_usr[df_usr['Correo'] == user_email].iloc[0]
nombre_regional = datos_usuario[df_usr.columns[0]] # Asume que el nombre es la columna 1
gerentes = df_usr.iloc[:, 0].dropna().tolist()
sucursales = df_age.iloc[:, 0].dropna().tolist()

# 5. LÓGICA DE CÁLCULO
for g in gerentes:
    df_inv[g] = pd.to_numeric(df_inv[g], errors='coerce').fillna(0)
df_inv['Disponible Inicial'] = pd.to_numeric(df_inv['Disponible Inicial'], errors='coerce').fillna(0)
df_inv['Disponible Restante'] = df_inv['Disponible Inicial'] - df_inv[gerentes].sum(axis=1)

# 6. INTERFAZ PERSONALIZADA
st.title(f"🏍️ Bienvenido, {nombre_regional}")
st.caption(f"Sesión iniciada como: {user_email}")

# Barra Lateral con métrica del usuario logueado
st.sidebar.metric("Tus Apartados", int(df_inv[nombre_regional].sum()))

if st.sidebar.button("🔄 Refrescar Inventario"):
    st.cache_data.clear()
    st.rerun()

# --- BUSCADOR Y APARTADO ---
st.subheader("📋 Gestión de Apartados")
opciones_modelos = df_inv.apply(
    lambda x: f"{x['Item Number']} - {x['Modelo']} ({x['Color']}) - {x['Año Modelo']}", axis=1
).tolist()

seleccion_modelo = st.selectbox("Selecciona la unidad:", ["Seleccione..."] + opciones_modelos)

if seleccion_modelo != "Seleccione...":
    item_id = seleccion_modelo.split(" - ")[0]
    row = df_inv[df_inv['Item Number'] == item_id].iloc[0]
    
    with st.expander(f"Confirmar apartado: {row['Modelo']} ({row['Año Modelo']})", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            sucursal = st.selectbox("Destino:", sucursales)
        with col2:
            disp = int(row['Disponible Restante'])
            cant = st.number_input("Cantidad:", min_value=1, max_value=disp if disp > 0 else 1)
        
        if disp <= 0:
            st.error("Sin stock.")
        elif st.button("Registrar Apartado", use_container_width=True):
            # Guardar
            idx = df_inv.index[df_inv['Item Number'] == item_id][0]
            df_inv.at[idx, nombre_regional] += cant
            conn.update(spreadsheet=URL, worksheet="Inventario", data=df_inv)
            
            # Historial
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

# Tabla de Visualización
st.dataframe(df_inv[['Item Number', 'Modelo', 'Color', 'Año Modelo', 'Disponible Inicial', 'Disponible Restante']], 
             use_container_width=True, hide_index=True)
