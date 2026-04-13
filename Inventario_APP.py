import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import uuid
import gspread
from google.oauth2.service_account import Credentials

# ============================================
# CONFIGURACIÓN DE PÁGINA
# ============================================
st.set_page_config(page_title="Inventario Motodrive", layout="wide")

# CSS PERSONALIZADO: Tarjetas alineadas y fuentes ajustadas
st.markdown("""
    <style>
    /* Contenedor de la métrica superior */
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
        padding: 12px;
        border-radius: 5px 5px 0px 0px; /* Bordes redondeados solo arriba */
        border: 1px solid #000;
        height: 180px; /* Altura fija para alineación total */
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        overflow: hidden;
    }

    /* Ajuste de texto para nombres largos */
    .moto-card div {
        line-height: 1.2;
        font-size: 13px; /* Tamaño base ligeramente más pequeño */
    }

    .label-red {
        color: #ff4d4d;
        font-weight: bold;
    }

    .text-white {
        color: white;
        font-weight: bold;
    }

    /* Ajuste del botón para que pegue con la tarjeta */
    .stButton > button {
        border-radius: 0px 0px 5px 5px !important; /* Bordes redondeados solo abajo */
        margin-top: -1px;
        height: 40px;
        background-color: #0e3b57;
        color: white;
        border: 1px solid #000;
    }
    
    .stButton > button:hover {
        background-color: #1a5276;
        color: #ff4d4d;
    }
    </style>
    """, unsafe_allow_html=True)

# ============================================
# CONEXIONES Y DATOS
# ============================================
conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1mbzAa6zn_otA_y1932IyW8fSuf8XOehzarvxZBpleu0/edit?usp=sharing"

@st.cache_resource
def connect_gspread():
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(st.secrets["connections"]["gsheets"], scopes=scope)
    client = gspread.authorize(creds)
    return client.open_by_url(URL)

gsheet = connect_gspread()
ws_inv = gsheet.worksheet("Inventario")
ws_movs = gsheet.worksheet("Movimientos_Apartados")

@st.cache_data(ttl=60)
def load_data():
    inv = conn.read(spreadsheet=URL, worksheet="Inventario")
    usr = conn.read(spreadsheet=URL, worksheet="Usuarios")
    age = conn.read(spreadsheet=URL, worksheet="Agencias")
    movs = conn.read(spreadsheet=URL, worksheet="Movimientos_Apartados")
    return inv, usr, age, movs

df_inv, df_usr, df_age, df_movs = load_data()

# Limpieza básica
df_inv = df_inv[df_inv['Modelo'].notna()].copy()

# ============================================
# LOGIN
# ============================================
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    col_l1, col_l2, col_l3 = st.columns([1,2,1])
    with col_l2:
        st.title("Acceso al Sistema")
        email = st.text_input("Correo Electrónico")
        if st.button("Ingresar", use_container_width=True):
            if email.lower() in df_usr['Correo'].astype(str).str.lower().values:
                st.session_state.autenticado = True
                st.session_state.user_email = email.lower()
                st.rerun()
            else:
                st.error("Usuario no autorizado.")
    st.stop()

# ============================================
# PROCESAMIENTO DE INFORMACIÓN
# ============================================
user_email = st.session_state.user_email
datos_usuario = df_usr[df_usr['Correo'].astype(str).str.lower() == user_email].iloc[0]
nombre_regional = datos_usuario.iloc[0]

gerentes = [g for g in df_usr.iloc[:,0].dropna().tolist() if g in df_inv.columns]
for g in gerentes:
    df_inv[g] = pd.to_numeric(df_inv[g], errors='coerce').fillna(0).astype(int)

df_inv['Disponible Inicial'] = pd.to_numeric(df_inv['Disponible Inicial'], errors='coerce').fillna(0).astype(int)
df_inv['Disponible Restante'] = (df_inv['Disponible Inicial'] - df_inv[gerentes].sum(axis=1)).astype(int)

# ============================================
# HEADER Y KPIs
# ============================================
st.title("Sistema de Apartado de Inventario MD:")
st.subheader(f"BIENVENIDO – {nombre_regional}")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Inventario Inicial:", int(df_inv['Disponible Inicial'].sum()))
c2.metric("Inventario Restante:", int(df_inv['Disponible Restante'].sum()))
c3.metric("Apartados:", int(df_inv[nombre_regional].sum()) if nombre_regional in df_inv.columns else 0)
with c4:
    st.write(" ")
    if st.button("🔄 Actualizar datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ============================================
# FILTROS
# ============================================
st.markdown("### Listado de Modelos Disponibles:")
colf1, colf2, colf3, colf4, colf5 = st.columns(5)

df_f = df_inv.copy()

with colf1:
    bus = st.text_input("Cuadro de Búsqueda:", key="bus_txt")
    if bus: df_f = df_f[df_f['Modelo'].str.contains(bus, case=False, na=False)]

with colf2:
    mod = st.multiselect("Filtro Modelo:", sorted(df_f['Modelo'].unique()), key="f_mod")
    if mod: df_f = df_f[df_f['Modelo'].isin(mod)]

with colf3:
    col = st.multiselect("Filtro Color:", sorted(df_f['Color'].unique()), key="f_col")
    if col: df_f = df_f[df_f['Color'].isin(col)]

with colf4:
    ano = st.multiselect("Filtro Año:", sorted(df_f['Año Modelo'].unique().astype(str)), key="f_ano")
    if ano: df_f = df_f[df_f['Año Modelo'].astype(str).isin(ano)]

with colf5:
    st.write(" ")
    if st.button("🧹 Reestablecer", use_container_width=True):
        for k in ["bus_txt", "f_mod", "f_col", "f_ano"]: 
            if k in st.session_state: del st.session_state[k]
        st.rerun()

# ============================================
# GRID DE TARJETAS (CUADRÍCULA DE 4)
# ============================================
st.write("---")

# Dividimos el dataframe en grupos de 4 para las filas
n_cols = 4
rows = [df_f.iloc[i:i+n_cols] for i in range(0, len(df_f), n_cols)]

for row_data in rows:
    cols = st.columns(n_cols)
    for i, (idx, row) in enumerate(row_data.iterrows()):
        with cols[i]:
            # Tarjeta HTML
            st.markdown(f"""
                <div class="moto-card">
                    <div><span class="label-red">Item:</span> <span class="text-white">{row['Item Number']}</span></div>
                    <div><span class="text-white">Modelo:</span> {row['Modelo']}</div>
                    <div><span class="text-white">Color:</span> {row['Color']}</div>
                    <div><span class="text-white">Año:</span> {row['Año Modelo']}</div>
                    <div><span class="text-white">Disponible:</span> {int(row['Disponible Restante'])}</div>
                </div>
            """, unsafe_allow_html=True)
            
            # Botón Streamlit
            if st.button("Apartar Unidad", key=f"btn_{idx}", use_container_width=True):
                st.session_state.modelo = row['Item Number']
                st.rerun()

# ============================================
# SIDEBAR: PROCESO DE APARTADO
# ============================================
with st.sidebar:
    st.header("🛒 Apartar Unidad")
    if "modelo" in st.session_state:
        sel = df_inv[df_inv['Item Number'] == st.session_state.modelo].iloc[0]
        st.success(f"Seleccionado: {sel['Modelo']}")
        
        suc_dest = st.selectbox("Sucursal Destino", df_age.iloc[:, 0].dropna())
        cant = st.number_input("Cantidad", 1, int(sel['Disponible Restante']))
        
        if st.button("Confirmar Apartado", use_container_width=True):
            # Lógica GSheets
            idx_inv = df_inv.index[df_inv['Item Number'] == sel['Item Number']][0]
            col_usr_idx = df_inv.columns.get_loc(nombre_regional)
            
            fila_sheet = int(idx_inv) + 2
            col_sheet = int(col_usr_idx) + 1
            
            val_actual = int(df_inv.at[idx_inv, nombre_regional])
            ws_inv.update_cell(fila_sheet, col_sheet, val_actual + cant)
            
            # Movimiento
            nuevo_mov = [
                str(uuid.uuid4())[:8].upper(),
                datetime.now().strftime("%d/%m/%Y %H:%M"),
                sel['Item Number'], sel['Modelo'], sel['Color'],
                sel['Año Modelo'], suc_dest, int(cant), user_email
            ]
            ws_movs.append_row(nuevo_mov)
            
            st.balloons()
            del st.session_state.modelo
            st.cache_data.clear()
            st.rerun()
            
        if st.button("Cancelar"):
            del st.session_state.modelo
            st.rerun()
    else:
        st.info("Selecciona un modelo de la lista para comenzar.")
    
    st.write("---")
    st.subheader("Historial Reciente")
    st.dataframe(df_movs.tail(10), use_container_width=True)

# ============================================
# RESUMEN FINAL
# ============================================
st.write("---")
st.subheader("Resumen de Movimientos:")
st.dataframe(df_movs, use_container_width=True, hide_index=True)
