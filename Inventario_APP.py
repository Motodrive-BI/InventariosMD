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
]

df_inv = df_inv[
    df_inv['Modelo'].astype(str).str.strip() != ""
]
# ============================================
# 🔧 LIMPIEZA ROBUSTA (NUEVO)
# ============================================
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
# USER
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
# FILTROS
# ============================================
st.markdown("## 🔍 Búsqueda y filtros")

colf1, colf2, colf3, colf4 = st.columns(4)

with colf1:
    busqueda = st.text_input("Buscar modelo")

with colf2:
    filtro_modelo = st.multiselect("Modelo", clean_unique(df_inv['Modelo']))

with colf3:
    filtro_color = st.multiselect("Color", clean_unique(df_inv['Color']))

with colf4:
    filtro_año = st.multiselect("Año", clean_unique(df_inv['Año Modelo']))

df_filtrado = df_inv.copy()

if busqueda:
    df_filtrado = df_filtrado[
        df_filtrado['Modelo'].astype(str).str.contains(busqueda, case=False, na=False)
    ]

if filtro_modelo:
    df_filtrado = df_filtrado[
        df_filtrado['Modelo'].astype(str).isin(filtro_modelo)
    ]

if filtro_color:
    df_filtrado = df_filtrado[
        df_filtrado['Color'].astype(str).isin(filtro_color)
    ]

if filtro_año:
    df_filtrado = df_filtrado[
        df_filtrado['Año Modelo'].astype(str).isin(filtro_año)
    ]

# ============================================
# HEADER
# ============================================
st.title(f"🏍️ {nombre_regional}")

# ============================================
# KPIs
# ============================================
total_inicial = int(df_inv['Disponible Inicial'].sum())
total_restante = int(df_inv['Disponible Restante'].sum())
if nombre_regional in df_inv.columns:
    apartados_usuario = int(pd.to_numeric(df_inv[nombre_regional], errors='coerce').fillna(0).sum())
else:
    apartados_usuario = 0

c1, c2, c3 = st.columns(3)
c1.metric("Disponible Inicial", total_inicial)
c2.metric("Disponible Restante", total_restante)
c3.metric("Tus Apartados", apartados_usuario)

# ============================================
# SIDEBAR
# ============================================
with st.sidebar:

    st.subheader("📂 Historial Acumulado (Todos)")

    # MODIFICACIÓN: Muestra el historial completo sin filtrar por gerente
    st.dataframe(df_movs, use_container_width=True)

    st.markdown("---")

    st.subheader("🏍️ Apartar unidad")

    if "modelo" in st.session_state:
        row = df_inv[df_inv['Item Number'] == st.session_state.modelo].iloc[0]
        disp = int(row['Disponible Restante'])

        st.success(f"{row['Modelo']} ({row['Color']})")

        if st.button("❌ Cancelar selección"):
            # MODIFICACIÓN: Borrado seguro de session_state
            if 'modelo' in st.session_state:
                del st.session_state.modelo
            st.rerun()

        if disp > 0:
            suc = st.selectbox("Sucursal", df_age.iloc[:, 0].dropna(), key="suc")
            cant = st.number_input("Cantidad", 1, disp, key="cant")

            if st.button("Confirmar Apartado", use_container_width=True):

                idx = df_inv.index[df_inv['Item Number'] == row['Item Number']][0]
                col_idx = df_inv.columns.get_loc(nombre_regional)

                fila_sheet = idx + 2
                col_sheet = col_idx + 1

                valor_actual = int(df_inv.at[idx, nombre_regional])
                nuevo_valor = valor_actual + cant

                ws_inv.update_cell(fila_sheet, col_sheet, nuevo_valor)

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

                # MODIFICACIÓN: Inserción forzada calculando la última fila vacía
                filas_ocupadas = len(ws_movs.col_values(1)) 
                siguiente_fila = filas_ocupadas + 1
                ws_movs.insert_row(nuevo_mov, index=siguiente_fila)

                st.success("✅ Registrado sin romper fórmulas")

                # MODIFICACIÓN: Borrado seguro de session_state
                if 'modelo' in st.session_state:
                    del st.session_state.modelo
                st.cache_data.clear()
                st.rerun()
        else:
            st.error("🚫 Sin stock")
    else:
        st.info("Selecciona un modelo")

# ============================================
# MODELOS
# ============================================
st.markdown("---")
st.subheader("Modelos disponibles")

for i, row in df_filtrado.iterrows():
    stock = int(row['Disponible Restante'])
    color = "🔴" if stock <= 0 else "🟢"

    col1, col2 = st.columns([5,1])

    with col1:
        st.markdown(f"""
        **{row['Modelo']}** ({row['Color']})  
        Año: {row['Año Modelo']}  
        Stock: {color} {stock}
        """)

    with col2:
        if st.button("Seleccionar", key=f"btn_{i}"):
            st.session_state.modelo = row['Item Number']
            st.rerun()

# ============================================
# DASHBOARD
# ============================================
st.markdown("---")
st.header("📊 Dashboard")

c1, c2 = st.columns(2)

with c1:
    st.subheader("Disponible Inicial")
    st.bar_chart(df_inv.groupby("Modelo")["Disponible Inicial"].sum())

with c2:
    st.subheader("Apartados")
    st.bar_chart(df_inv_calc.groupby("Modelo")["Apartado"].sum())

# ============================================
# TABLA
# ============================================
st.markdown("---")
st.subheader("Inventario")
st.dataframe(df_inv, use_container_width=True)
