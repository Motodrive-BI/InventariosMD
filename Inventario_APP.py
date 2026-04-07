import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import uuid

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="Inventario Bajaj Motodrive", layout="wide", page_icon="🏍️")

# 2. CONEXIÓN Y CARGA DE DATOS
conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1mbzAa6zn_otA_y1932IyW8fSuf8XOehzarvxZBpleu0/edit?usp=sharing"

# --- FUNCIÓN PARA RECALCULAR STOCK ---
def recalcular_disponibles(df, lista_gerentes):
    """Calcula el disponible restante restando todos los apartados de los regionales"""
    for g in lista_gerentes:
        df[g] = pd.to_numeric(df[g], errors='coerce').fillna(0)
    
    df['Disponible Inicial'] = pd.to_numeric(df['Disponible Inicial'], errors='coerce').fillna(0)
    # Resta horizontal: Inicial - Suma(Todos los regionales)
    df['Disponible Restante'] = df['Disponible Inicial'] - df[lista_gerentes].sum(axis=1)
    return df

@st.cache_data(ttl=300)
def load_all_data():
    inv = conn.read(spreadsheet=URL, worksheet="Inventario")
    usr = conn.read(spreadsheet=URL, worksheet="Usuarios")
    age = conn.read(spreadsheet=URL, worksheet="Agencias")
    return inv, usr, age

# Carga inicial
df_inv, df_usr, df_age = load_all_data()
gerentes = df_usr.iloc[:, 0].dropna().tolist()
sucursales = df_age.iloc[:, 0].dropna().tolist()

# Aplicar cálculo de stock inmediatamente
df_inv = recalcular_disponibles(df_inv, gerentes)

# 3. INTERFAZ SUPERIOR
st.title("🏍️ Gestión de Inventarios y Apartados")

col_refresh, col_empty = st.columns([1, 4])
with col_refresh:
    if st.button("🔄 Sincronizar Datos"):
        st.cache_data.clear()
        st.rerun()

st.markdown("---")

# 4. BARRA LATERAL (FILTROS Y REGISTRO)
st.sidebar.image("https://upload.wikimedia.org/wikipedia/en/thumb/d/d4/Bajaj_Auto_logo.svg/1200px-Bajaj_Auto_logo.svg.png", width=100)
st.sidebar.header("Panel de Control")

gerente_sel = st.sidebar.selectbox("Identifícate (Regional):", gerentes)

# Métrica personal en la barra lateral
total_personal = df_inv[gerente_sel].sum()
st.sidebar.metric(f"Tus Apartados Totales", f"{int(total_personal)} uds")

st.sidebar.divider()
st.sidebar.subheader("📝 Registrar Nuevo Apartado")

with st.sidebar.form("form_registro"):
    modelo_sel = st.selectbox("Selecciona Modelo", df_inv['Descripción del artículo'].unique())
    sucursal_dest = st.selectbox("Sucursal Destino", sucursales)
    cantidad = st.number_input("Cantidad a apartar", min_value=1, step=1)
    
    if st.form_submit_button("Confirmar Apartado"):
        idx = df_inv.index[df_inv['Descripción del artículo'] == modelo_sel][0]
        
        # Validar stock antes de guardar
        if df_inv.at[idx, 'Disponible Restante'] >= cantidad:
            # A. Actualizar Inventario
            df_inv.at[idx, gerente_sel] += cantidad
            df_inv = recalcular_disponibles(df_inv, gerentes)
            conn.update(spreadsheet=URL, worksheet="Inventario", data=df_inv)
            
            # B. Registrar Movimiento Histórico
            df_movs = conn.read(spreadsheet=URL, worksheet="Movimientos_Apartados")
            fila = df_inv.loc[idx]
            
            nuevo_mov = {
                "ID_Apartado": str(uuid.uuid4())[:8].upper(),
                "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "Item_Number": fila['Item Number'],
                "Modelo": fila['Modelo'],
                "Color": fila['Color'],
                "Año Modelo": fila['Año Modelo'],
                "Sucursal_Destino": sucursal_dest,
                "Cantidad": cantidad,
                "Nombre Regional": gerente_sel
            }
            
            df_movs = pd.concat([df_movs, pd.DataFrame([nuevo_mov])], ignore_index=True)
            conn.update(spreadsheet=URL, worksheet="Movimientos_Apartados", data=df_movs)
            
            st.success("✅ ¡Apartado exitoso!")
            st.cache_data.clear()
            st.rerun()
        else:
            st.error(f"❌ Stock insuficiente. Disponible: {int(df_inv.at[idx, 'Disponible Restante'])}")

# 5. CUERPO PRINCIPAL (TABLA LIMPIA)
st.subheader("📋 Disponibilidad General de Unidades")

# Buscador rápido
busqueda = st.text_input("🔍 Buscar por Modelo, Color o Item Number...")
df_final = df_inv.copy()

if busqueda:
    df_final = df_final[df_final.astype(str).apply(lambda x: x.str.contains(busqueda, case=False)).any(axis=1)]

# Definir columnas visibles (Ocultamos las de los nombres de regionales)
cols_visibles = [
    'Item Number', 'Modelo', 'Color', 'Año Modelo', 
    'Disponible Inicial', 'Disponible Restante'
]

# Mostrar tabla con formato
st.dataframe(
    df_final[cols_visibles], 
    use_container_width=True, 
    hide_index=True,
    column_config={
        "Disponible Restante": st.column_config.NumberColumn("Disponible Real", format="%d 🏍️"),
        "Disponible Inicial": st.column_config.NumberColumn("Stock Base", format="%d")
    }
)

# 6. HISTORIAL RECIENTE (OPCIONAL)
with st.expander("📂 Ver Historial de Movimientos Recientes"):
    df_h = conn.read(spreadsheet=URL, worksheet="Movimientos_Apartados")
    st.dataframe(df_h.tail(10), use_container_width=True, hide_index=True)
