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

# ============================================
# HEADER
# ============================================
st.title(f"🏍️ {nombre_regional}")

# ============================================
# 🟢 KPIs USUARIO
# ============================================
total_inicial = int(df_inv['Disponible Inicial'].sum())
total_restante = int(df_inv['Disponible Restante'].sum())
apartados_usuario = int(df_inv[nombre_regional].sum())

c1, c2, c3 = st.columns(3)
c1.metric("Disponible Inicial", total_inicial)
c2.metric("Disponible Restante", total_restante)
c3.metric("Tus Apartados", apartados_usuario)

st.markdown("---")

# ============================================
# 🧩 MODELOS DISPONIBLES
# ============================================
st.subheader("Modelos disponibles")

for i, row in df_inv.iterrows():
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
                "Regional": nombre_regional
            }])

            df_movs = pd.concat([df_movs, nuevo])
            conn.update(spreadsheet=URL, worksheet="Movimientos_Apartados", data=df_movs)

            st.success("Registrado")
            del st.session_state.modelo
            st.rerun()
    else:
        st.error("Sin stock")

# ============================================
# 📊 DASHBOARD
# ============================================
st.markdown("---")
st.header("📊 Dashboard")

# Datos para gráfica
df_chart = df_inv.copy()
df_chart["Apartado"] = df_chart['Disponible Inicial'] - df_chart['Disponible Restante']

chart = df_chart.set_index("Modelo")[["Disponible Restante", "Apartado"]]
st.bar_chart(chart)

# ============================================
# 📊 APARTADOS POR REGIONAL
# ============================================
st.subheader("Apartados por regional")

regional_data = df_inv[gerentes].sum()
st.bar_chart(regional_data)

# ============================================
# 📋 TABLA INVENTARIO
# ============================================
st.markdown("---")
st.subheader("Inventario")

st.dataframe(df_inv, use_container_width=True)

# ============================================
# 📂 HISTORIAL USUARIO
# ============================================
with st.expander("📂 Historial de tus apartados"):
    hist = df_movs[df_movs["Regional"] == nombre_regional]
    st.dataframe(hist, use_container_width=True)
