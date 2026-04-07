import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import uuid

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="Inventario Motodrive - Privado", layout="wide")

# 2. VERIFICACIÓN DE USUARIO (Método compatible con Streamlit 1.35+)
# Intentamos obtener el correo desde st.context.user
try:
    user_email = st.context.user.email
except AttributeError:
    # Si st.context no está disponible, intentamos el método antiguo
    user_email = getattr(st, "user", {}).get("email", None)

if not user_email:
    st.error("⚠️ Acceso denegado. Esta aplicación requiere inicio de sesión con Google.")
    st.info("Asegúrate de haber activado 'Viewer Authentication' en los Settings de Streamlit Cloud.")
    st.stop()

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

# 4. VALIDAR CORREO EN LA HOJA DE USUARIOS
# IMPORTANTE: Tu hoja 'Usuarios' debe tener una columna llamada 'Correo'
if user_email not in df_usr['Correo'].values:
    st.error(f"El correo {user_email} no está autorizado.")
    st.stop()

# Obtener el nombre del Regional (Asumiendo que el nombre está en la primera columna)
nombre_col_usuario = df_usr.columns[0]
nombre_regional = df_usr[df_usr['Correo'] == user_email][nombre_col_usuario].values[0]

gerentes = df_usr.iloc[:, 0].dropna().tolist()
sucursales = df_age.iloc[:, 0].dropna().tolist()

# 5. CÁLCULOS DE INVENTARIO
for g in gerentes:
    df_inv[g] = pd.to_numeric(df_inv[g], errors='coerce').fillna(0)
df_inv['Disponible Inicial'] = pd.to_numeric(df_inv['Disponible Inicial'], errors='coerce').fillna(0)
df_inv['Disponible Restante'] = df_inv['Disponible Inicial'] - df_inv[gerentes].sum(axis=1)

# 6. INTERFAZ
st.title(f"🏍️ Bienvenido, {nombre_regional}")
st.caption(f"Conectado como: {user_email}")

# Barra Lateral
st.sidebar.metric("Tus Apartados", int(df_inv[nombre_regional].sum()))
if st.sidebar.button("🔄 Sincronizar Datos"):
    st.cache_data.clear()
    st.rerun()

# 7. BUSCADOR Y APARTADO
st.subheader("📋 Registro de Unidades")
opciones_modelos = df_inv.apply(
    lambda x: f"{x['Item Number']} - {x['Modelo']} ({x['Color']}) - {x['Año Modelo']}", axis=1
).tolist()

seleccion_modelo = st.selectbox("Selecciona la unidad:", ["Seleccione..."] + opciones_modelos)

if seleccion_modelo != "Seleccione...":
    item_id = seleccion_modelo.split(" - ")[0]
    row = df_inv[df_inv['Item Number'] == item_id].iloc[0]
    
    with st.expander(f"Confirmar registro para: {row['Modelo']} ({row['Año Modelo']})", expanded=True):
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
            
            st.success("¡Registrado exitosamente!")
            st.cache_data.clear()
            st.rerun()

# 8. TABLA DE VISTA
st.dataframe(df_inv[['Item Number', 'Modelo', 'Color', 'Año Modelo', 'Disponible Inicial', 'Disponible Restante']], 
             use_container_width=True, hide_index=True)
