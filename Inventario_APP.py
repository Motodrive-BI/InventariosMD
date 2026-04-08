import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import uuid

# ============================================
# CONFIG
# ============================================
st.set_page_config(page_title="Inventario Motodrive", layout="wide")

conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1mbzAa6zn_otA_y1932IyW8fSuf8XOehzarvxZBpleu0/edit?usp=sharing"

@st.cache_data(ttl=60)
def load_data():
    inv = conn.read(spreadsheet=URL, worksheet="Inventario")
    usr = conn.read(spreadsheet=URL, worksheet="Usuarios")
    age = conn.read(spreadsheet=URL, worksheet="Agencias")
    movs = conn.read(spreadsheet=URL, worksheet="Movimientos_Apartados")
    return inv, usr, age, movs

df_inv, df_usr, df_age, df_movs = load_data()

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
df_inv['Apartado'] = df_inv['Disponible Inicial'] - df_inv['Disponible Restante']

# ============================================
# 🔍 BUSCADOR + FILTROS (ARRIBA)
# ============================================
st.markdown("## 🔍 Búsqueda y filtros")

colf1, colf2, colf3, colf4 = st.columns(4)

with colf1:
    busqueda = st.text_input("Buscar modelo")

with colf2:
    filtro_modelo = st.multiselect("Modelo", sorted(df_inv['Modelo'].unique()))

with colf3:
    filtro_color = st.multiselect("Color", sorted(df_inv['Color'].unique()))

with colf4:
    filtro_año = st.multiselect("Año", sorted(df_inv['Año Modelo'].unique()))

df_filtrado = df_inv.copy()

if busqueda:
    df_filtrado = df_filtrado[df_filtrado['Modelo'].str.contains(busqueda, case=False, na=False)]

if filtro_modelo:
    df_filtrado = df_filtrado[df_filtrado['Modelo'].isin(filtro_modelo)]

if filtro_color:
    df_filtrado = df_filtrado[df_filtrado['Color'].isin(filtro_color)]

if filtro_año:
    df_filtrado = df_filtrado[df_filtrado['Año Modelo'].isin(filtro_año)]

# ============================================
# HEADER
# ============================================
st.title(f"🏍️ {nombre_regional}")

# ============================================
# KPIs
# ============================================
total_inicial = int(df_inv['Disponible Inicial'].sum())
total_restante = int(df_inv['Disponible Restante'].sum())
apartados_usuario = int(df_inv[nombre_regional].sum())

c1, c2, c3 = st.columns(3)
c1.metric("Disponible Inicial", total_inicial)
c2.metric("Disponible Restante", total_restante)
c3.metric("Tus Apartados", apartados_usuario)

# ============================================
# 📂 HISTORIAL LATERAL
# ============================================
with st.sidebar:
    st.subheader("📂 Historial")

    col_valida = None
    for col in ["Nombre Regional", "Regional"]:
        if col in df_movs.columns:
            col_valida = col

    if col_valida:
        hist = df_movs[df_movs[col_valida] == nombre_regional]
        st.dataframe(hist, use_container_width=True)
    else:
        st.warning("Sin columna válida")

# ============================================
# 🧩 MODELOS
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
# FORMULARIO
# ============================================
if "modelo" in st.session_state:
    row = df_inv[df_inv['Item Number'] == st.session_state.modelo].iloc[0]
    disp = int(row['Disponible Restante'])

    st.markdown("---")
    st.subheader(f"Apartar {row['Modelo']}")

    if disp > 0:
        suc = st.selectbox("Sucursal", df_age.iloc[:,0].dropna())
        cant = st.number_input("Cantidad", 1, disp)

        if st.button("Confirmar"):
            idx = df_inv.index[df_inv['Item Number'] == row['Item Number']][0]
            df_inv.at[idx, nombre_regional] += cant
            conn.update(spreadsheet=URL, worksheet="Inventario", data=df_inv)

            nuevo = pd.DataFrame([{
                "ID": str(uuid.uuid4())[:8],
                "Fecha": datetime.now().strftime("%d/%m/%Y"),
                "Modelo": row['Modelo'],
                "Cantidad": cant,
                "Nombre Regional": nombre_regional
            }])

            df_movs = pd.concat([df_movs, nuevo])
            conn.update(spreadsheet=URL, worksheet="Movimientos_Apartados", data=df_movs)

            st.success("Registrado")
            del st.session_state.modelo
            st.cache_data.clear()
            st.rerun()
    else:
        st.error("Sin stock")

# ============================================
# 📊 DASHBOARD
# ============================================
st.markdown("---")
st.header("📊 Dashboard")

c1, c2 = st.columns(2)

with c1:
    st.subheader("Disponible Inicial")
    chart1 = df_inv.groupby("Modelo")["Disponible Inicial"].sum()
    st.bar_chart(chart1)

with c2:
    st.subheader("Apartados")
    chart2 = df_inv.groupby("Modelo")["Apartado"].sum()
    st.bar_chart(chart2)

# ============================================
# 📋 TABLA
# ============================================
st.markdown("---")
st.subheader("Inventario")
st.dataframe(df_inv, use_container_width=True)
