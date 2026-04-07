import streamlit as st
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Sistema de Inventario Bajaj", layout="wide")

st.title("📊 Control de Inventario - Conexión Real")

# Crear la conexión usando los secretos
conn = st.connection("gsheets", type=GSheetsConnection)

# URL de tu hoja (la que me pasaste)
URL_SHEET = "https://docs.google.com/spreadsheets/d/1c9WqiNYi_ycGeVCTo94bUmJBvDAddH8u9jM0KW1SQmw/edit"

try:
    # Intentamos leer la pestaña de "Asiganciones Por Agencia"
    df_asignaciones = conn.read(spreadsheet=URL_SHEET, worksheet="Asiganciones Por Agencia")
    
    st.success("¡Conexión exitosa!")
    
    # Mostrar un resumen rápido
    st.subheader("Vista Previa de Asignaciones")
    st.dataframe(df_asignaciones.head(10))

except Exception as e:
    st.error(f"Error de conexión: {e}")
    st.info("Revisa que hayas compartido la hoja con el correo de la cuenta de servicio.")