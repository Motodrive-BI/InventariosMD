import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import uuid

# 1. Configuración y Conexión
conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1c9WqiNYi_ycGeVCTo94bUmJBvDAddH8u9jM0KW1SQmw/edit"

# 2. Carga de datos (Agregamos Agencias)
@st.cache_data(ttl=300)
def load_all_data():
    inv = conn.read(spreadsheet=URL, worksheet="Inventario")
    usr = conn.read(spreadsheet=URL, worksheet="Usuarios")
    age = conn.read(spreadsheet=URL, worksheet="Agencias")
    return inv, usr, age

df_inv, df_usr, df_age = load_all_data()
gerentes = df_usr.iloc[:, 0].dropna().tolist()
sucursales = df_age.iloc[:, 0].dropna().tolist()

# 3. Interfaz Principal
st.title("Sistema de Apartados y Logística")
gerente_sel = st.sidebar.selectbox("Gerente Regional", gerentes)

# --- FORMULARIO DE APARTADO ---
with st.sidebar.form("Registro_Movimiento"):
    st.subheader("📝 Nuevo Apartado")
    modelo_sel = st.selectbox("Modelo / Artículo", df_inv['Descripción del artículo'])
    sucursal_dest = st.selectbox("Sucursal Destino", sucursales)
    cantidad = st.number_input("Cantidad", min_value=1, step=1)
    
    if st.form_submit_button("Confirmar y Registrar"):
        # Localizar datos del modelo
        fila_data = df_inv[df_inv['Descripción del artículo'] == modelo_sel].iloc[0]
        idx = df_inv.index[df_inv['Descripción del artículo'] == modelo_sel][0]
        
        if fila_data['Disponible Restante'] >= cantidad:
            # A. ACTUALIZAR HOJA INVENTARIO (Columna del Gerente)
            df_inv.at[idx, gerente_sel] = (df_inv.at[idx, gerente_sel] or 0) + cantidad
            conn.update(spreadsheet=URL, worksheet="Inventario", data=df_inv)
            
            # B. REGISTRAR EN HOJA MOVIMIENTOS_APARTADOS
            df_movs = conn.read(spreadsheet=URL, worksheet="Movimientos_Apartados")
            
            nuevo_mov = {
                "ID_Apartado": str(uuid.uuid4())[:8], # Genera ID corto único
                "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "Item_Number": fila_data['Item Number'],
                "Modelo": fila_data['Modelo'],
                "Color": fila_data['Color'],
                "Año Modelo": fila_data['Año Modelo'],
                "Sucursal_Destino": sucursal_dest,
                "Cantidad": cantidad,
                "Nombre Regional": gerente_sel
            }
            
            df_movs = pd.concat([df_movs, pd.DataFrame([nuevo_mov])], ignore_index=True)
            conn.update(spreadsheet=URL, worksheet="Movimientos_Apartados", data=df_movs)
            
            st.success(f"Movimiento {nuevo_mov['ID_Apartado']} registrado correctamente")
            st.cache_data.clear()
            st.rerun()
        else:
            st.error("No hay stock suficiente.")

# 4. Visualización de Inventario (Tabla General)
st.subheader(f"Inventario Actual - Vista {gerente_sel}")
cols_vista = ['Item Number', 'Modelo', 'Color', 'Año Modelo', 'Disponible Inicial', gerente_sel, 'Disponible Restante']
st.dataframe(df_inv[cols_vista], use_container_width=True, hide_index=True)

# 5. Visualización de Historial (Opcional para ver qué se ha registrado)
if st.checkbox("Ver historial de movimientos"):
    df_historial = conn.read(spreadsheet=URL, worksheet="Movimientos_Apartados")
    st.write("### Últimos Movimientos")
    st.dataframe(df_historial.tail(10), use_container_width=True)
