import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import uuid

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="Inventario Bajaj Motodrive", layout="wide", page_icon="🏍️")

# 2. CONEXIÓN Y CARGA DE DATOS
conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1c9WqiNYi_ycGeVCTo94bUmJBvDAddH8u9jM0KW1SQmw/edit"

def recalcular_disponibles(df, lista_gerentes):
    """Calcula el disponible real basándose en los apartados de todos los regionales"""
    for g in lista_gerentes:
        df[g] = pd.to_numeric(df[g], errors='coerce').fillna(0)
    df['Disponible Inicial'] = pd.to_numeric(df['Disponible Inicial'], errors='coerce').fillna(0)
    # Disponible Restante = Inicial - Suma de columnas de todos los gerentes
    df['Disponible Restante'] = df['Disponible Inicial'] - df[lista_gerentes].sum(axis=1)
    return df

@st.cache_data(ttl=300)
def load_all_data():
    inv = conn.read(spreadsheet=URL, worksheet="Inventario")
    usr = conn.read(spreadsheet=URL, worksheet="Usuarios")
    age = conn.read(spreadsheet=URL, worksheet="Agencias")
    return inv, usr, age

# Carga de datos inicial
df_inv_raw, df_usr, df_age = load_all_data()
gerentes = df_usr.iloc[:, 0].dropna().tolist()
sucursales = df_age.iloc[:, 0].dropna().tolist()

# Aplicar cálculos de inventario
df_inv = recalcular_disponibles(df_inv_raw, gerentes)

# --- VENTANA EMERGENTE DE APARTADO ---
@st.dialog("Confirmar Registro de Apartado")
def ventana_apartado(row_data, gerente_name):
    st.markdown(f"### {row_data['Modelo']}")
    st.write(f"**Color:** {row_data['Color']} | **Año:** {row_data['Año Modelo']}")
    st.write(f"**Disponible Actual:** {int(row_data['Disponible Restante'])} unidades")
    
    with st.form("confirm_form"):
        sucursal_dest = st.selectbox("Sucursal de Destino", sucursales)
        max_av = int(row_data['Disponible Restante'])
        cantidad = st.number_input("Cantidad a apartar", min_value=1, max_value=max_av, step=1)
        
        if st.form_submit_button("Confirmar y Guardar en Google Sheets", use_container_width=True):
            # Identificar fila en el DataFrame original por Item Number
            idx = df_inv.index[df_inv['Item Number'] == row_data['Item Number']][0]
            
            # 1. Actualizar Hoja Inventario
            df_inv.at[idx, gerente_name] += cantidad
            df_inv_upd = recalcular_disponibles(df_inv, gerentes)
            conn.update(spreadsheet=URL, worksheet="Inventario", data=df_inv_upd)
            
            # 2. Registrar en Historial (Movimientos_Apartados)
            df_movs = conn.read(spreadsheet=URL, worksheet="Movimientos_Apartados")
            nuevo_mov = {
                "ID_Apartado": str(uuid.uuid4())[:8].upper(),
                "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "Item_Number": row_data['Item Number'],
                "Modelo": row_data['Modelo'],
                "Color": row_data['Color'],
                "Año Modelo": row_data['Año Modelo'],
                "Sucursal_Destino": sucursal_dest,
                "Cantidad": cantidad,
                "Nombre Regional": gerente_name
            }
            df_movs = pd.concat([df_movs, pd.DataFrame([nuevo_mov])], ignore_index=True)
            conn.update(spreadsheet=URL, worksheet="Movimientos_Apartados", data=df_movs)
            
            st.success("✅ Apartado registrado con éxito.")
            st.cache_data.clear()
            st.rerun()

# 3. INTERFAZ PRINCIPAL
st.title("🏍️ Sistema de Gestión de Inventarios")

if st.button("🔄 Sincronizar con Google Sheets"):
    st.cache_data.clear()
    st.rerun()

# 4. BARRA LATERAL
st.sidebar.header("Perfil")
gerente_sel = st.sidebar.selectbox("Selecciona tu nombre (Regional):", gerentes)
total_personal = df_inv[gerente_sel].sum()
st.sidebar.metric("Tu Total Apartado", f"{int(total_personal)} uds")
st.sidebar.divider()
st.sidebar.info("💡 Haz clic en cualquier fila de la tabla para abrir la ventana de apartado.")

# 5. TABLA DE INVENTARIO INTERACTIVA
st.subheader("📋 Inventario Disponible")
busqueda = st.text_input("🔍 Buscar por Modelo, Color o Item Number...")

df_filtrado = df_inv.copy()
if busqueda:
    mask = df_filtrado.astype(str).apply(lambda x: x.str.contains(busqueda, case=False)).any(axis=1)
    df_filtrado = df_filtrado[mask]

# Definir qué columnas mostrar al usuario
cols_visibles = ['Item Number', 'Modelo', 'Color', 'Año Modelo', 'Disponible Inicial', 'Disponible Restante']

# Renderizar tabla con capacidad de selección
seleccion = st.dataframe(
    df_filtrado[cols_visibles], 
    use_container_width=True, 
    hide_index=True,
    on_select="rerun",
    selection_mode=["get_full_row"]
)

# Lógica al seleccionar una fila
if len(seleccion.selection.rows) > 0:
    # Obtenemos la fila seleccionada del DataFrame filtrado
    idx_seleccionado = seleccion.selection.rows[0]
    datos_fila = df_filtrado.iloc[idx_seleccionado]
    
    if datos_fila['Disponible Restante'] > 0:
        ventana_apartado(datos_fila, gerente_sel)
    else:
        st.warning("⚠️ No hay unidades disponibles para este modelo.")

# 6. HISTORIAL (EXPANDER)
with st.expander("📂 Ver últimos movimientos registrados"):
    df_h = conn.read(spreadsheet=URL, worksheet="Movimientos_Apartados")
    st.dataframe(df_h.tail(15), use_container_width=True, hide_index=True)
