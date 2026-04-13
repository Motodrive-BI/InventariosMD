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

# CSS MEJORADO: Compatible con modo oscuro y tarjetas fijas
st.markdown("""
    <style>
    .moto-card {
        background-color: #1a5276 !important;
        color: #ffffff !important;
        padding: 15px;
        border-radius: 8px 8px 0px 0px;
        border: 1px solid #444;
        height: 180px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }

    .moto-card div, .moto-card span, .moto-card b, .moto-card strong {
        color: #ffffff !important; 
        line-height: 1.3;
        font-size: 14px;
    }

    .label-red {
        color: #ff4d4d !important;
        font-weight: bold;
    }

    /* Estilo del botón y del mensaje de agotado */
    div.stButton > button {
        border-radius: 0px 0px 8px 8px !important;
        margin-top: -2px;
        height: 42px;
        background-color: #0e3b57 !important;
        color: white !important;
        border: 1px solid #444 !important;
        width: 100%;
        font-weight: bold;
    }
    
    div.stButton > button:hover {
        border-color: #ff4d4d !important;
        color: #ff4d4d !important;
    }

    /* Mensaje de Agotado con el mismo estilo del botón pero gris */
    .sold-out-msg {
        background-color: #424949 !important;
        color: #bdc3c7 !important;
        text-align: center;
        padding: 10px;
        border-radius: 0px 0px 8px 8px;
        border: 1px solid #444;
        font-weight: bold;
        font-size: 14px;
        height: 42px;
        margin-top: -2px;
    }

    [data-testid="stMetric"] {
        background-color: rgba(255, 255, 255, 0.05);
        border: 1px solid #2e7d32;
        padding: 10px;
        border-radius: 8px;
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
    return gspread.authorize(creds).open_by_url(URL)

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
df_inv = df_inv[df_inv['Modelo'].notna()].copy()

# ============================================
# VENTANA FLOTANTE (MODAL)
# ============================================
@st.dialog("Confirmar Apartado de Unidad")
def ventana_apartar(item_row, nombre_regional, user_email):
    disp_real = int(item_row['Disponible Restante'])
    
    st.write(f"### {item_row['Modelo']}")
    st.write(f"**Color:** {item_row['Color']} | **Año:** {item_row['Año Modelo']}")
    st.write(f"**Stock Disponible:** {disp_real:,}")
    
    st.divider()
    
    if disp_real > 0:
        suc_dest = st.selectbox("Seleccione Sucursal Destino", df_age.iloc[:, 0].dropna())
        cant = st.number_input("Cantidad a apartar", min_value=1, max_value=disp_real, step=1)
        
        col_v1, col_v2 = st.columns(2)
        with col_v1:
            if st.button("Cancelar", use_container_width=True):
                st.rerun()
        with col_v2:
            if st.button("Confirmar", type="primary", use_container_width=True):
                idx_inv = df_inv.index[df_inv['Item Number'] == item_row['Item Number']][0]
                col_usr_idx = df_inv.columns.get_loc(nombre_regional)
                fila_sheet = int(idx_inv) + 2
                col_sheet = int(col_usr_idx) + 1
                val_actual = int(df_inv.at[idx_inv, nombre_regional])
                ws_inv.update_cell(fila_sheet, col_sheet, val_actual + cant)
                
                nuevo_mov = [
                    str(uuid.uuid4())[:8].upper(),
                    datetime.now().strftime("%d/%m/%Y %H:%M"),
                    item_row['Item Number'], item_row['Modelo'], item_row['Color'],
                    item_row['Año Modelo'], suc_dest, int(cant), user_email
                ]
                ws_movs.append_row(nuevo_mov)
                st.success("✅ Apartado registrado con éxito")
                st.cache_data.clear()
                st.rerun()
    else:
        st.error("Lo sentimos, este modelo ya no tiene inventario disponible.")
        if st.button("Cerrar", use_container_width=True):
            st.rerun()

# ============================================
# LOGIN Y PROCESAMIENTO
# ============================================
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.markdown("### Acceso al Sistema")
    email_input = st.text_input("Correo Electrónico")
    pass_input = st.text_input("Contraseña", type="password") # Campo de contraseña oculto
    
    if st.button("Ingresar"):
        # Normalizamos entrada para evitar errores de mayúsculas/espacios
        user_row = df_usr[df_usr['Correo'].astype(str).str.lower() == email_input.lower().strip()]
        
        if not user_row.empty:
            # Verificamos si la contraseña coincide (ajusta 'Password' al nombre real de tu columna)
            db_password = str(user_row.iloc[0]['Password']).strip()
            
            if pass_input == db_password:
                st.session_state.autenticado = True
                st.session_state.user_email = email_input.lower().strip()
                st.rerun()
            else:
                st.error("Contraseña incorrecta")
        else:
            st.error("Usuario no encontrado")
    st.stop()
# ============================================
# INTERFAZ PRINCIPAL
# ============================================
st.title("Sistema de Apartado de Inventario MD:")
st.header(f"BIENVENIDO – {Nombre}")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Inventario Inicial:", f"{int(df_inv['Disponible Inicial'].sum()):,}")
c2.metric("Inventario Restante:", f"{int(df_inv['Disponible Restante'].sum()):,}")
c3.metric("Tus Apartados:", f"{int(df_inv[nombre_regional].sum()):,}" if nombre_regional in df_inv.columns else "0")
with c4:
    st.write(" ")
    if st.button("🔄 Actualizar Datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.write("---")

# Función Callback para limpiar filtros
def reset_filtros():
    st.session_state.bus_txt = ""
    st.session_state.f_mod = []
    st.session_state.f_col = []
    st.session_state.f_ano = []

# Se agrega una quinta columna para el botón de limpieza
colf1, colf2, colf3, colf4, colf5 = st.columns([2, 2, 2, 2, 1.5])
df_f = df_inv.copy()

with colf1: bus = st.text_input("Cuadro de Búsqueda:", key="bus_txt")
with colf2: mod = st.multiselect("Filtro Modelo:", sorted(df_f['Modelo'].unique()), key="f_mod")
with colf3: col = st.multiselect("Filtro Color:", sorted(df_f['Color'].unique()), key="f_col")
with colf4: ano = st.multiselect("Filtro Año:", sorted(df_f['Año Modelo'].unique().astype(str)), key="f_ano")
with colf5: 
    # Añadimos un pequeño margen superior para alinear el botón con las cajas de texto
    st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
    st.button("🧹 Limpiar Filtros", on_click=reset_filtros, use_container_width=True)

if bus: df_f = df_f[df_f['Modelo'].str.contains(bus, case=False, na=False)]
if mod: df_f = df_f[df_f['Modelo'].isin(mod)]
if col: df_f = df_f[df_f['Color'].isin(col)]
if ano: df_f = df_f[df_f['Año Modelo'].astype(str).isin(ano)]

# ============================================
# GRID DE TARJETAS
# ============================================
st.subheader("Listado de Modelos Disponibles:")
n_cols = 4
rows = [df_f.iloc[i:i+n_cols] for i in range(0, len(df_f), n_cols)]

for row_data in rows:
    cols = st.columns(n_cols)
    for i, (idx, row) in enumerate(row_data.iterrows()):
        disp_restante = int(row['Disponible Restante'])
        with cols[i]:
            st.markdown(f"""
                <div class="moto-card">
                    <div><span class="label-red">Item:</span> <b>{row['Item Number']}</b></div>
                    <div><strong>Modelo:</strong> {row['Modelo']}</div>
                    <div><strong>Color:</strong> {row['Color']}</div>
                    <div><strong>Año:</strong> {row['Año Modelo']}</div>
                    <div><strong>Disponible:</strong> {disp_restante:,}</div>
                </div>
            """, unsafe_allow_html=True)
            
            # Validación de Inventario Agotado
            if disp_restante > 0:
                if st.button("Apartar", key=f"btn_{idx}", use_container_width=True):
                    ventana_apartar(row, nombre_regional, user_email)
            else:
                st.markdown('<div class="sold-out-msg">🚫 Inventario Agotado</div>', unsafe_allow_html=True)

# ============================================
# TABLA DE MOVIMIENTOS
# ============================================
st.write("---")
st.subheader("Resumen de Movimientos:")

col_formato = 'Cantidad Apartada' # <--- ESTA ES LA LÍNEA A CAMBIAR

if col_formato in df_movs.columns:
    df_styled = df_movs.style.format(subset=[col_formato], formatter="{:,}")
    st.dataframe(df_styled, use_container_width=True, hide_index=True)
else:
    st.dataframe(df_movs, use_container_width=True, hide_index=True)
