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
    for g in lista_gerentes:
        df[g] = pd.to_numeric(df[g], errors='coerce').fillna(0)
    df['Disponible Inicial'] = pd.to_numeric(df['Disponible Inicial'], errors='coerce').fillna(0)
    df['Disponible Restante'] = df['Disponible Inicial'] - df[lista_gerentes].sum(axis=1)
    return df

@st.cache_data(ttl=300)
def load_all_data():
    inv = conn.read(spreadsheet=URL, worksheet="Inventario")
    usr = conn.read(spreadsheet=URL, worksheet="Usuarios")
    age = conn.read(spreadsheet=URL, worksheet="Agencias")
    return inv, usr, age

df_inv, df_usr, df_age = load_all_data()
gerentes = df_usr.iloc[:, 0].dropna().tolist()
sucursales = df_age.iloc[:, 0].dropna().tolist()
df_inv = recalcular_disponibles(df_inv, gerentes)

# --- FUNCIÓN PARA EL CUADRO DE DIÁLOGO (VENTANA EMERGENTE) ---
@st.dialog("Confirmar Apartado")
def ventana_apartado(row_data):
    st.write(f"**Modelo:** {row_data['Modelo']} - {row_data['Color']}")
    st.write(f"**Disponible:** {int(row_data['Disponible Restante'])} unidades")
    
    sucursal_dest = st.selectbox("Sucursal Destino", sucursales)
    cantidad = st.number_input("Cantidad a apartar", min_value=1, max_value=int(row_data['Disponible Restante']), step=1)
    
    if st.button("Registrar Apartado", use_container_width=True):
        # Lógica de guardado (misma que antes)
        idx = df_inv.index[df_inv['Item Number'] == row_data['Item Number']][0]
        
        # A. Actualizar Inventario
        df_inv.at[idx, gerente_sel] += cantidad
        df_inv_final = recalcular_disponibles(df_inv, gerentes)
        conn.update(spreadsheet=URL, worksheet="Inventario", data=df_inv_final)
        
        # B. Registrar Movimiento
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
            "Nombre Regional": gerente_sel
        }
        df_movs = pd.concat([df_movs, pd.DataFrame([nuevo_mov])], ignore_index=True)
        conn.update(spreadsheet=URL, worksheet="Movimientos_Apartados", data=df_movs)
        
        st.success("✅ ¡Apartado registrado!")
        st.cache_data.clear()
        st.rerun()

# 3. INTERFAZ SUPERIOR
st.title("🏍️ Gestión de Inventarios Bajaj")
if st.button("🔄 Sincronizar Datos"):
    st.cache_data.clear()
    st.rerun()

# 4. BARRA LATERAL
gerente_sel = st.sidebar.selectbox("Identifícate (Regional):", gerentes)
total_personal = df_inv[gerente_sel].sum()
st.sidebar.metric(f"Tus Apartados Totales", f"{int(total_personal)} uds")
st.sidebar.info("Selecciona una fila en la tabla para apartar unidades.")

# 5. TABLA INTERACTIVA
st.subheader("📋 Inventario General")
busqueda = st.text_input("🔍 Buscar por Modelo, Color o Item Number...")
df_final = df_inv.copy()

if busqueda:
    df_final = df_final[df_final.astype(str).apply(lambda x: x.str.contains(busqueda, case=False)).any(axis=1)]

cols_visibles = ['Item Number', 'Modelo', 'Color', 'Año Modelo', 'Disponible Inicial', 'Disponible Restante']

# --- CONFIGURACIÓN DE SELECCIÓN ---
event = st.dataframe(
    df_final[cols_visibles], 
    use_container_width=True, 
    hide_index=True,
    on_select="rerun",  # Permite que la app reaccione al clic
    selection_mode="single_row"  # Solo una fila a la vez
)

# Si el usuario selecciona una fila, abrimos la ventana
if event.selection.rows:
    selected_row_index = event.selection.rows[0]
    row_data = df_final.iloc[selected_row_index]
    
    # Validar que haya stock antes de abrir la ventana
    if row_data['Disponible Restante'] > 0:
        ventana_apartado(row_data)
    else:
        st.error("No hay unidades disponibles para este modelo.")

# 6. HISTORIAL
with st.expander("📂 Historial de Movimientos"):
    df_h = conn.read(spreadsheet=URL, worksheet="Movimientos_Apartados")
    st.dataframe(df_h.tail(10), use_container_width=True, hide_index=True)
