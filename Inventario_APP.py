import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# Configuración de la página
st.set_page_config(page_title="Inventario Bajaj", layout="wide", page_icon="🏍️")

# Título y estilo
st.title("🏍️ Sistema de Inventario - Sucursales")
st.markdown("---")

# 1. Conexión a los datos
conn = st.connection("gsheets", type=GSheetsConnection)

URL_SHEET = "https://docs.google.com/spreadsheets/d/1c9WqiNYi_ycGeVCTo94bUmJBvDAddH8u9jM0KW1SQmw/edit"

@st.cache_data(ttl=600) # Los datos se actualizan cada 10 minutos para ser rápidos
def load_data():
    df = conn.read(spreadsheet=URL_SHEET, worksheet="Asiganciones Por Agencia")
    # Limpieza básica: quitar filas vacías si las hay
    df = df.dropna(subset=['Sucursal'])
    return df

try:
    data = load_data()

    # --- SIDEBAR: FILTROS ---
    st.sidebar.header("Filtros de Búsqueda")
    
    # Filtro por Sucursal
    sucursales = ["Todas"] + sorted(data['Sucursal'].unique().tolist())
    sucursal_sel = st.sidebar.selectbox("Selecciona Agencia", sucursales)

    # Filtro por Gerente
    gerentes = ["Todos"] + sorted(data['Gerente SR'].unique().tolist())
    gerente_sel = st.sidebar.selectbox("Filtrar por Gerente SR", gerentes)

    # Aplicar Filtros
    df_filtered = data.copy()
    if sucursal_sel != "Todas":
        df_filtered = df_filtered[df_filtered['Sucursal'] == sucursal_sel]
    if gerente_sel != "Todos":
        df_filtered = df_filtered[df_filtered['Gerente SR'] == gerente_sel]

    # --- CUERPO PRINCIPAL: MÉTRICAS ---
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Unidades", int(df_filtered['Cantidad Apartada'].sum()))
    with col2:
        st.metric("Modelos Únicos", df_filtered['MODELO'].nunique())
    with col3:
        st.metric("Agencias Mostradas", df_filtered['Sucursal'].nunique())

    # --- TABLA DE DATOS ---
    st.subheader(f"Listado de Inventario: {sucursal_sel}")
    
    # Selector de columnas para no saturar la vista (estilo AppSheet)
    cols_a_mostrar = ['Sucursal', 'MODELO', 'COLOR', 'Cantidad Apartada', 'Gerente SR', 'Gerente JR']
    
    st.dataframe(
        df_filtered[cols_a_mostrar], 
        use_container_width=True,
        hide_index=True
    )

    # --- BUSCADOR ESPECÍFICO ---
    st.divider()
    search = st.text_input("🔍 Buscar modelo o color específico...")
    if search:
        search_res = df_filtered[df_filtered.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)]
        st.write("Resultados de búsqueda:")
        st.table(search_res[cols_a_mostrar])

except Exception as e:
    st.error("No se pudo cargar la información.")
    st.info("Asegúrate de que tus 'Secrets' en Streamlit Cloud tengan el formato correcto del JSON de Google.")
