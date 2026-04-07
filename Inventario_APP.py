import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.set_page_config(page_title="Sistema de Apartados Bajaj", layout="wide")

# 1. Conexión y Carga de Datos
conn = st.connection("gsheets", type=GSheetsConnection)
URL_SHEET = "https://docs.google.com/spreadsheets/d/1c9WqiNYi_ycGeVCTo94bUmJBvDAddH8u9jM0KW1SQmw/edit"

def load_data():
    df_inv = conn.read(spreadsheet=URL_SHEET, worksheet="Inventario")
    df_user = conn.read(spreadsheet=URL_SHEET, worksheet="Usuarios")
    return df_inv, df_user

df_inventario, df_usuarios = load_data()
lista_gerentes = df_usuarios.iloc[:, 0].dropna().unique().tolist()

# --- INTERFAZ ---
st.title("🏍️ Gestión de Apartados Regionales")

# Sidebar para Filtros y Registro
st.sidebar.header("Configuración")
gerente_identificado = st.sidebar.selectbox("¿Quién eres? (Gerente Regional)", lista_gerentes)

st.sidebar.divider()
st.sidebar.subheader("📝 Registrar Nuevo Apartado")

# Formulario para apartar
with st.sidebar.form("form_apartado"):
    # Buscamos por descripción para que sea más fácil de identificar
    modelo_opciones = df_inventario['Descripción del artículo'].unique().tolist()
    item_a_apartar = st.selectbox("Selecciona el Artículo", modelo_opciones)
    cantidad = st.number_input("Cantidad a apartar", min_value=1, step=1)
    
    boton_guardar = st.form_submit_button("Confirmar Apartado")

    if boton_guardar:
        # 1. Localizar la fila y la columna
        # Filtramos el dataframe original para encontrar el índice de la fila
        idx_fila = df_inventario.index[df_inventario['Descripción del artículo'] == item_a_apartar].tolist()[0]
        
        # 2. Verificar disponibilidad restante antes de apartar
        disponible_actual = df_inventario.at[idx_fila, 'Disponible Restante']
        
        if disponible_actual >= cantidad:
            # 3. Actualizar el valor en la columna del Gerente
            # Sumamos lo que ya tenía ese gerente + la nueva cantidad
            valor_previo_gerente = df_inventario.at[idx_fila, gerente_identificado]
            # Manejar si la celda está vacía (NaN)
            if pd.isna(valor_previo_gerente): valor_previo_gerente = 0
            
            df_inventario.at[idx_fila, gerente_identificado] = valor_previo_gerente + cantidad
            
            # 4. Enviar los datos de vuelta a Google Sheets
            try:
                conn.update(spreadsheet=URL_SHEET, worksheet="Inventario", data=df_inventario)
                st.sidebar.success(f"✅ Apartado registrado con éxito para {item_a_apartar}")
                # Limpiamos caché para que la tabla principal se actualice
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"Error al guardar en Google Sheets: {e}")
        else:
            st.sidebar.error(f"❌ No hay suficiente stock. Disponible: {disponible_actual}")

# --- PANTALLA PRINCIPAL: VISTA DE INVENTARIO ---
st.subheader(f"Estado de Inventario - Regional: {gerente_identificado}")

# Filtro rápido de búsqueda
busqueda = st.text_input("🔍 Buscar por descripción, modelo o color...")

# Columnas a mostrar (Dinámicas según el gerente)
cols_ver = ['Item Number', 'Descripción del artículo', 'Modelo', 'Color', 'Año Modelo', 'Disponible Inicial', gerente_identificado, 'Disponible Restante']

df_final = df_inventario.copy()
if busqueda:
    df_final = df_final[df_final.astype(str).apply(lambda x: x.str.contains(busqueda, case=False)).any(axis=1)]

st.dataframe(df_final[cols_ver], use_container_width=True, hide_index=True)

# Métricas
c1, c2 = st.columns(2)
with c1:
    total_gerente = df_final[gerente_identificado].sum()
    st.metric(f"Total Apartado por {gerente_identificado}", f"{int(total_gerente)} uds")
with c2:
    total_disponible = df_final['Disponible Restante'].sum()
    st.metric("Total Disponible General", f"{int(total_disponible)} uds")
