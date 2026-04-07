import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import uuid

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="Inventario Motodrive", layout="wide")

# 2. CONEXIÓN
conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1mbzAa6zn_otA_y1932IyW8fSuf8XOehzarvxZBpleu0/edit?usp=sharing"

# 3. CARGA DE DATOS
@st.cache_data(ttl=60)
def load_data():
    inv = conn.read(spreadsheet=URL, worksheet="Inventario")
    usr = conn.read(spreadsheet=URL, worksheet="Usuarios")
    age = conn.read(spreadsheet=URL, worksheet="Agencias")
    return inv, usr, age

df_inv, df_usr, df_age = load_data()
gerentes = df_usr.iloc[:, 0].dropna().tolist()
sucursales = df_age.iloc[:, 0].dropna().tolist()

# 4. LÓGICA DE CÁLCULO DE STOCK
for g in gerentes:
    df_inv[g] = pd.to_numeric(df_inv[g], errors='coerce').fillna(0)
df_inv['Disponible Inicial'] = pd.to_numeric(df_inv['Disponible Inicial'], errors='coerce').fillna(0)
df_inv['Disponible Restante'] = df_inv['Disponible Inicial'] - df_inv[gerentes].sum(axis=1)

# 5. INTERFAZ
st.title("🏍️ Sistema de Inventarios Bajaj")

if st.button("🔄 Sincronizar con Google Sheets"):
    st.cache_data.clear()
    st.rerun()

# Barra Lateral
gerente_sel = st.sidebar.selectbox("Regional:", gerentes)
st.sidebar.metric("Tus Apartados", int(df_inv[gerente_sel].sum()))

# --- SISTEMA DE SELECCIÓN CON AÑO DEL MODELO ---
st.subheader("📋 Selecciona un modelo para apartar")

# MODIFICACIÓN AQUÍ: Agregamos 'Año Modelo' al texto de la opción
opciones_modelos = df_inv.apply(
    lambda x: f"{x['Item Number']} - {x['Modelo']} ({x['Color']}) - {x['Año Modelo']}", 
    axis=1
).tolist()

seleccion_modelo = st.selectbox("Busca y selecciona el equipo:", ["Seleccione..."] + opciones_modelos)

if seleccion_modelo != "Seleccione...":
    # Extraer el Item Number (que es la primera parte antes del primer guion)
    item_id = seleccion_modelo.split(" - ")[0]
    row = df_inv[df_inv['Item Number'] == item_id].iloc[0]
    
    with st.expander(f"Confirmar apartado para: {row['Modelo']} {row['Año Modelo']}", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            sucursal = st.selectbox("Destino:", sucursales)
        with col2:
            disp = int(row['Disponible Restante'])
            cant = st.number_input("Cantidad:", min_value=1, max_value=disp if disp > 0 else 1)
        
        if disp <= 0:
            st.error("⚠️ Sin stock disponible para este modelo.")
        elif st.button("Registrar Movimiento", use_container_width=True):
            # 1. Update Inventario
            idx = df_inv.index[df_inv['Item Number'] == item_id][0]
            df_inv.at[idx, gerente_sel] += cant
            conn.update(spreadsheet=URL, worksheet="Inventario", data=df_inv)
            
            # 2. Update Movimientos_Apartados
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
                "Nombre Regional": gerente_sel
            }])
            df_movs = pd.concat([df_movs, nuevo], ignore_index=True)
            conn.update(spreadsheet=URL, worksheet="Movimientos_Apartados", data=df_movs)
            
            st.success("✅ ¡Movimiento Guardado!")
            st.cache_data.clear()
            st.rerun()

# 6. TABLA DE VISUALIZACIÓN (Limpia)
st.markdown("---")
cols = ['Item Number', 'Modelo', 'Color', 'Año Modelo', 'Disponible Inicial', 'Disponible Restante']
st.dataframe(df_inv[cols], use_container_width=True, hide_index=True)
