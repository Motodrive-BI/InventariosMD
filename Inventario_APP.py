import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import uuid

# ============================================
# CONFIGURACIÓN
# ============================================
st.set_page_config(page_title="Inventario Motodrive", layout="wide")

conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1mbzAa6zn_otA_y1932IyW8fSuf8XOehzarvxZBpleu0/edit?usp=sharing"

@st.cache_data(ttl=60)
def load_data():
    inv = conn.read(spreadsheet=URL, worksheet="Inventario")
    usr = conn.read(spreadsheet=URL, worksheet="Usuarios")
    age = conn.read(spreadsheet=URL, worksheet="Agencias")
    return inv, usr, age

df_inv, df_usr, df_age = load_data()

# ============================================
# LOGIN
# ============================================
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.subheader("Inicio de Sesión")
        email_input = st.text_input("Correo")

        if st.button("Iniciar Sesión", use_container_width=True):
            email_clean = email_input.strip().lower()
            df_usr['Correo'] = df_usr['Correo'].str.strip().str.lower()

            if email_clean in df_usr['Correo'].values:
                st.session_state.autenticado = True
                st.session_state.user_email = email_clean
                st.rerun()
            else:
                st.error("Correo no autorizado.")
    st.stop()

# ============================================
# USUARIO
# ============================================
user_email = st.session_state.user_email
datos_usuario = df_usr[df_usr['Correo'] == user_email].iloc[0]
nombre_regional = datos_usuario.iloc[0]

gerentes = [g for g in df_usr.iloc[:, 0].dropna().tolist() if g in df_inv.columns]

for g in gerentes:
    df_inv[g] = pd.to_numeric(df_inv[g], errors='coerce').fillna(0).astype(int)

df_inv['Disponible Inicial'] = pd.to_numeric(df_inv['Disponible Inicial'], errors='coerce').fillna(0).astype(int)
df_inv['Disponible Restante'] = (df_inv['Disponible Inicial'] - df_inv[gerentes].sum(axis=1)).astype(int)

# ============================================
# HEADER
# ============================================
col1, col2 = st.columns([4, 1])
with col1:
    st.title(f"🏍️ {nombre_regional}")
with col2:
    if st.button("🔄 Actualizar"):
        st.cache_data.clear()
        st.rerun()

st.sidebar.metric("Tus Apartados", int(df_inv[nombre_regional].sum()))
if st.sidebar.button("Cerrar Sesión"):
    st.session_state.clear()
    st.rerun()

# ============================================
# 🧾 FORMULARIO (ARRIBA)
# ============================================
if "modelo_seleccionado" in st.session_state:
    item_id = st.session_state.modelo_seleccionado
    row = df_inv[df_inv['Item Number'] == item_id].iloc[0]
    disp_real = int(row['Disponible Restante'])

    st.success(f"Modelo seleccionado: {row['Modelo']} ({row['Color']})")

    colA, colB = st.columns([3, 1])
    with colA:
        st.subheader(f"Apartar unidad {row['Modelo']} - {row['Año Modelo']}")
    with colB:
        if st.button("❌ Cancelar selección"):
            del st.session_state.modelo_seleccionado
            st.rerun()

    if disp_real <= 0:
        st.error("Sin stock disponible")
    else:
        c1, c2 = st.columns(2)

        with c1:
            sucursal = st.selectbox(
                "Sucursal destino",
                df_age.iloc[:, 0].dropna().tolist()
            )

        with c2:
            cant = st.number_input(
                "Cantidad",
                min_value=1,
                max_value=disp_real,
                step=1
            )

        if st.button("Confirmar Apartado", use_container_width=True):
            idx = df_inv.index[df_inv['Item Number'] == item_id][0]
            df_inv.at[idx, nombre_regional] += cant

            conn.update(spreadsheet=URL, worksheet="Inventario", data=df_inv)

            df_movs = conn.read(spreadsheet=URL, worksheet="Movimientos_Apartados")

            nuevo = pd.DataFrame([{
                "ID_Apartado": str(uuid.uuid4())[:8].upper(),
                "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "Item_Number": row['Item Number'],
                "Modelo": row['Modelo'],
                "Color": row['Color'],
                "Año Modelo": row['Año Modelo'],
                "Sucursal_Destino": sucursal,
                "Cantidad": int(cant),
                "Nombre Regional": nombre_regional
            }])

            df_movs = pd.concat([df_movs, nuevo], ignore_index=True)
            conn.update(spreadsheet=URL, worksheet="Movimientos_Apartados", data=df_movs)

            st.success("Registro exitoso")
            del st.session_state.modelo_seleccionado
            st.cache_data.clear()
            st.rerun()

st.markdown("---")

# ============================================
# 🔎 FILTRO SIMPLE (PLUS PRO)
# ============================================
busqueda = st.text_input("Buscar modelo")

df_filtrado = df_inv.copy()
if busqueda:
    df_filtrado = df_filtrado[
        df_filtrado['Modelo'].str.contains(busqueda, case=False, na=False)
    ]

# ============================================
# 🧩 LISTA DE MODELOS
# ============================================
st.subheader("Modelos disponibles")

for i, row in df_filtrado.iterrows():
    stock = int(row['Disponible Restante'])
    color = "🔴" if stock <= 0 else "🟢"

    seleccionado = (
        "modelo_seleccionado" in st.session_state and
        st.session_state.modelo_seleccionado == row['Item Number']
    )

    fondo = "background-color: #e8f0fe; padding:10px; border-radius:10px;" if seleccionado else ""

    col1, col2 = st.columns([5, 1])

    with col1:
        st.markdown(f"""
        <div style="{fondo}">
        <b>{row['Modelo']}</b> ({row['Color']})<br>
        Año: {row['Año Modelo']}<br>
        Stock: {color} <b>{stock}</b>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        if st.button("Seleccionar", key=f"btn_{i}"):
            st.session_state.modelo_seleccionado = row['Item Number']
            st.rerun()

# ============================================
# 📊 TABLA FINAL
# ============================================
st.markdown("---")

cols = ['Item Number', 'Modelo', 'Color', 'Año Modelo', 'Disponible Inicial', 'Disponible Restante']

st.dataframe(
    df_inv[cols],
    use_container_width=True,
    hide_index=True
)
