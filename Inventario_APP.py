import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import uuid

# ✅ NUEVO
import gspread
from google.oauth2.service_account import Credentials

# ============================================
# CONFIG
# ============================================
st.set_page_config(page_title="Inventario Motodrive", layout="wide")

conn = st.connection("gsheets", type=GSheetsConnection)

URL = "https://docs.google.com/spreadsheets/d/1mbzAa6zn_otA_y1932IyW8fSuf8XOehzarvxZBpleu0/edit?usp=sharing"

# ============================================
# 🔥 CONEXIÓN GSPREAD (NUEVO)
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

# ============================================
# 🔤 FUNCIÓN COLUMNAS (A, B, C...)
# ============================================
def col_to_letter(col_idx):
    letter = ""
    while col_idx >= 0:
        letter = chr(col_idx % 26 + 65) + letter
        col_idx = col_idx // 26 - 1
    return letter

# ============================================
# LOGIN
# ============================================
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    email = st.text_input("Correo")
    if st.button("Login"):
        if email.lower() in df_usr['Correo'].str.lower().values:
            st.session_state.autenticado = True
            st.session_state.user_email = email.lower()
            st.rerun()
        else:
            st.error("No autorizado")
    st.stop()

# ============================================
# USER
# ============================================
user_email = st.session_state.user_email
datos_usuario = df_usr[df_usr['Correo'].str.lower() == user_email].iloc[0]
nombre_regional = datos_usuario.iloc[0]

gerentes = [g for g in df_usr.iloc[:,0].dropna().tolist() if g in df_inv.columns]

for g in gerentes:
    df_inv[g] = pd.to_numeric(df_inv[g], errors='coerce').fillna(0).astype(int)

df_inv['Disponible Inicial'] = pd.to_numeric(df_inv['Disponible Inicial'], errors='coerce').fillna(0).astype(int)
df_inv['Disponible Restante'] = (df_inv['Disponible Inicial'] - df_inv[gerentes].sum(axis=1)).astype(int)

df_inv_calc = df_inv.copy()
df_inv_calc['Apartado'] = df_inv_calc['Disponible Inicial'] - df_inv_calc['Disponible Restante']

# ============================================
# UI
# ============================================
st.title(f"🏍️ {nombre_regional}")

# ============================================
# SIDEBAR
# ============================================
with st.sidebar:

    st.subheader("🏍️ Apartar unidad")

    if "modelo" in st.session_state:
        row = df_inv[df_inv['Item Number'] == st.session_state.modelo].iloc[0]
        disp = int(row['Disponible Restante'])

        if disp > 0:
            suc = st.selectbox("Sucursal", df_age.iloc[:, 0].dropna(), key="suc")
            cant = st.number_input("Cantidad", 1, disp, key="cant")

            if st.button("Confirmar Apartado", use_container_width=True):

                # ============================================
                # 🔥 UPDATE REAL POR CELDA (AQUÍ ESTÁ LA MAGIA)
                # ============================================

                idx = df_inv.index[df_inv['Item Number'] == row['Item Number']][0]
                col_idx = df_inv.columns.get_loc(nombre_regional)

                fila_sheet = idx + 2  # +2 header
                col_sheet = col_idx + 1  # 1-index

                valor_actual = int(df_inv.at[idx, nombre_regional])
                nuevo_valor = valor_actual + cant

                # ✅ SOLO ACTUALIZA UNA CELDA (NO BORRA FÓRMULAS)
                ws_inv.update_cell(fila_sheet, col_sheet, nuevo_valor)

                # ============================================
                # MOVIMIENTOS (append sin borrar)
                # ============================================
                nuevo_mov = [
                    str(uuid.uuid4())[:8].upper(),
                    datetime.now().strftime("%d/%m/%Y %H:%M"),
                    row['Item Number'],
                    row['Modelo'],
                    row['Color'],
                    row['Año Modelo'],
                    suc,
                    int(cant),
                    nombre_regional
                ]

                ws_movs.append_row(nuevo_mov)

                st.success("✅ Registrado sin romper fórmulas")

                del st.session_state.modelo
                st.cache_data.clear()
                st.rerun()
        else:
            st.error("🚫 Sin stock")
    else:
        st.info("Selecciona un modelo")
