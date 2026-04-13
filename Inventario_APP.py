import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import uuid
import gspread
from google.oauth2.service_account import Credentials

# ============================================
# CONFIG
# ============================================
st.set_page_config(page_title="Inventario Motodrive", layout="wide")

# CSS Personalizado para imitar la imagen
st.markdown("""
    <style>
    /* Estilo para las métricas superiores */
    [data-testid="stMetric"] {
        background-color: #ffffff;
        border: 2px solid #2e7d32;
        padding: 10px;
        border-radius: 5px;
        text-align: center;
    }
    
    /* Estilo de las tarjetas de inventario */
    .moto-card {
        background-color: #1a5276;
        color: white;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #000;
        margin-bottom: 10px;
        font-family: sans-serif;
    }
    .label-red {
        color: #ff4d4d;
        font-weight: bold;
    }
    .text-white {
        color: white;
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1mbzAa6zn_otA_y1932IyW8fSuf8XOehzarvxZBpleu0/edit?usp=sharing"

# ============================================
# GSPREAD
# ============================================
@st.cache_resource
def connect_gspread():
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(
        st.secrets["connections"]["gsheets"],
        scopes=scope
    )
    client = gspread.authorize(creds)
    sheet = client.open_by_url(URL)
    return sheet

gsheet = connect_gspread()
ws_inv = gsheet.worksheet("Inventario")
ws_movs = gsheet.worksheet("Movimientos_Apartados")

# ============================================
# LOAD DATA
# ============================================
@st.cache_data(ttl=60)
def load_data():
    inv = conn.read(spreadsheet=URL, worksheet="Inventario")
    usr = conn.read(spreadsheet=URL, worksheet="Usuarios")
    age = conn.read(spreadsheet=URL, worksheet="Agencias")
    movs = conn.read(spreadsheet=URL, worksheet="Movimientos_Apartados")
    return inv, usr, age, movs

df_inv, df_usr, df_age, df_movs = load_data()
df_inv = df_inv[
    df_inv['Modelo'].notna() &
    df_inv['Color'].notna() &
    df_inv['Año Modelo'].notna()
].copy()

df_inv = df_inv[df_inv['Modelo'].astype(str).str.strip() != ""]

def clean_unique(series):
    return sorted(series.dropna().astype(str).str.strip().unique())

# ============================================
# LOGIN
# ============================================
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    email = st.text_input("Correo")
    if st.button("Login"):
        if email.lower() in df_usr['Correo'].astype(str).str.lower().values:
            st.session_state.autenticado = True
            st.session_state.user_email = email.lower()
            st.rerun()
        else:
            st.error("No autorizado")
    st.stop()

# ============================================
# USER DATA PROCESSING
# ============================================
user_email = st.session_state.user_email
datos_usuario = df_usr[df_usr['Correo'].astype(str).str.lower() == user_email].iloc[0]
nombre_regional = datos_usuario.iloc[0]

gerentes = [g for g in df_usr.iloc[:,0].dropna().tolist() if g in df_inv.columns]

for g in gerentes:
    df_inv[g] = pd.to_numeric(df_inv[g], errors='coerce').fillna(0).astype(int)

df_inv['Disponible Inicial'] = pd.to_numeric(df_inv['Disponible Inicial'], errors='coerce').fillna(0).astype(int)
df_inv['Disponible Restante'] = (df_inv['Disponible Inicial'] - df_inv[gerentes].sum(axis=1)).astype(int)

df_inv_calc = df_inv.copy()
df_inv_calc['Apartado'] = df_inv_calc['Disponible Inicial'] - df_inv_calc['Disponible Restante']

# ============================================
# HEADER & KPIs (Igual a la imagen)
# ============================================
st.title("Sistema de Apartado de Inventario MD:")
st.header(f"BIENVENIDO – “{nombre_regional}”")

total_inicial = int(df_inv['Disponible Inicial'].sum())
total_restante = int(df_inv['Disponible Restante'].sum())
apartados_usuario = int(df_inv[nombre_regional].sum()) if nombre_regional in df_inv.columns else 0

c1, c2, c3, c4 = st.columns([2, 2, 2, 2])
c1.metric("Inventario Inicial:", total_inicial)
c2.metric("Inventario Restante:", total_restante)
c3.metric("Apartados:", apartados_usuario)
with c4:
    st.write("") # Espaciador
    if st.button("BOTÓN\nActualizar datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ============================================
# FILTROS
# ============================================
st.markdown("### Listado de Modelos Disponibles:")

colf1, colf2, colf3, colf4, colf5 = st.columns([2, 2, 2, 2, 2])
df_temp = df_inv.copy()

with colf1:
    busqueda = st.text_input("Cuadro de Búsqueda:", key="busqueda_txt")
    if busqueda:
        df_temp = df_temp[df_temp['Modelo'].astype(str).str.contains(busqueda, case=False, na=False)]

with colf2:
    filtro_modelo = st.multiselect("Filtro Modelo:", clean_unique(df_temp['Modelo']), key="filtro_mod")
    if filtro_modelo:
        df_temp = df_temp[df_temp['Modelo'].astype(str).isin(filtro_modelo)]

with colf3:
    filtro_color = st.multiselect("Filtro Color:", clean_unique(df_temp['Color']), key="filtro_col")
    if filtro_color:
        df_temp = df_temp[df_temp['Color'].astype(str).isin(filtro_color)]

with colf4:
    filtro_año = st.multiselect("Filtro Año Modelo:", clean_unique(df_temp['Año Modelo']), key="filtro_ano")
    if filtro_año:
        df_temp = df_temp[df_temp['Año Modelo'].astype(str).isin(filtro_año)]

with colf5:
    st.write("")
    if st.button("BOTÓN\nReestablecer", use_container_width=True):
        for clave in ["busqueda_txt", "filtro_mod", "filtro_col", "filtro_ano"]:
            if clave in st.session_state: del st.session_state[clave]
        st.rerun()

df_filtrado = df_temp

# ============================================
# CUADRÍCULA DE MODELOS (VISUALIZACIÓN DE TARJETAS)
# ============================================
st.write("---")
# Creamos filas de 4 columnas
cols = st.columns(4)

for i, (idx, row) in enumerate(df_filtrado.iterrows()):
    stock = int(row['Disponible Restante'])
    col_idx = i % 4
    
    with cols[col_idx]:
        # HTML para la tarjeta
        st.markdown(f"""
            <div class="moto-card">
                <span class="label-red">Item:</span> <span class="text-white">{row['Item Number']}</span><br>
                <span class="text-white">Modelo:</span> {row['Modelo']}<br>
                <span class="text-white">Color:</span> {row['Color']}<br>
                <span class="text-white">Año:</span> {row['Año Modelo']}<br>
                <span class="text-white">Disponible:</span> {stock}
            </div>
        """, unsafe_allow_html=True)
        
        # Botón de selección justo debajo de la tarjeta
        if st.button("BOTÓN Apartar", key=f"btn_{idx}", use_container_width=True):
            st.session_state.modelo = row['Item Number']
            st.rerun()

# ============================================
# SIDEBAR - PROCESO DE APARTADO
# ============================================
with st.sidebar:
    st.subheader("📂 Historial Acumulado")
    st.dataframe(df_movs, use_container_width=True)
    st.markdown("---")
    st.subheader("🏍️ Apartar unidad")

    if "modelo" in st.session_state:
        row_sel = df_inv[df_inv['Item Number'] == st.session_state.modelo].iloc[0]
        disp = int(row_sel['Disponible Restante'])

        st.success(f"Seleccionado: {row_sel['Modelo']}")
        
        if st.button("❌ Cancelar selección"):
            del st.session_state.modelo
            st.rerun()

        if disp > 0:
            suc = st.selectbox("Sucursal Destino", df_age.iloc[:, 0].dropna())
            cant = st.number_input("Cantidad", 1, disp)

            if st.button("Confirmar Apartado", use_container_width=True):
                # Lógica de actualización en GSheets
                idx_inv = df_inv.index[df_inv['Item Number'] == row_sel['Item Number']][0]
                col_name_idx = df_inv.columns.get_loc(nombre_regional)
                
                fila_sheet = int(idx_inv) + 2
                col_sheet = int(col_name_idx) + 1
                
                valor_actual = int(df_inv.at[idx_inv, nombre_regional])
                ws_inv.update_cell(fila_sheet, col_sheet, valor_actual + cant)

                nuevo_mov = [
                    str(uuid.uuid4())[:8].upper(),
                    datetime.now().strftime("%d/%m/%Y %H:%M"),
                    row_sel['Item Number'], row_sel['Modelo'], row_sel['Color'],
                    row_sel['Año Modelo'], suc, int(cant), user_email
                ]
                ws_movs.append_row(nuevo_mov)

                st.success("✅ ¡Apartado registrado!")
                del st.session_state.modelo
                st.cache_data.clear()
                st.rerun()
        else:
            st.error("Sin stock disponible")

# ============================================
# RESUMEN DE MOVIMIENTOS (TABLA INFERIOR)
# ============================================
st.write("---")
st.subheader("Resumen de Movimientos:")
st.dataframe(df_movs, use_container_width=True, hide_index=True)

# Dashboard simple al final
st.write("---")
st.subheader("Inventario Completo")
st.dataframe(df_inv, use_container_width=True)
