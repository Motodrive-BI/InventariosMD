import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import uuid
import gspread # <--- Requerido: pip install gspread

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
# 🔤 FUNCIÓN PARA COLUMNAS EXCEL (A, B, C... AA, AB)
# ============================================
def col_to_letter(col_idx):
    letter = ""
    col_idx += 1 
    while col_idx > 0:
        col_idx, remainder = divmod(col_idx - 1, 26)
        letter = chr(65 + remainder) + letter
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
# PROCESAMIENTO DE DATOS
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
# 🔍 FILTROS
# ============================================
st.markdown("## 🔍 Búsqueda y filtros")
colf1, colf2, colf3, colf4 = st.columns(4)

with colf1: busqueda = st.text_input("Buscar modelo")
with colf2: filtro_modelo = st.multiselect("Modelo", sorted(df_inv['Modelo'].unique()))
with colf3: filtro_color = st.multiselect("Color", sorted(df_inv['Color'].unique()))
with colf4: filtro_año = st.multiselect("Año", sorted(df_inv['Año Modelo'].unique()))

df_filtrado = df_inv.copy()
if busqueda: df_filtrado = df_filtrado[df_filtrado['Modelo'].str.contains(busqueda, case=False, na=False)]
if filtro_modelo: df_filtrado = df_filtrado[df_filtrado['Modelo'].isin(filtro_modelo)]
if filtro_color: df_filtrado = df_filtrado[df_filtrado['Color'].isin(filtro_color)]
if filtro_año: df_filtrado = df_filtrado[df_filtrado['Año Modelo'].isin(filtro_año)]

# ============================================
# KPIs
# ============================================
st.title(f"🏍️ {nombre_regional}")
c1, c2, c3 = st.columns(3)
c1.metric("Disponible Inicial", int(df_inv['Disponible Inicial'].sum()))
c2.metric("Disponible Restante", int(df_inv['Disponible Restante'].sum()))
c3.metric("Tus Apartados", int(df_inv[nombre_regional].sum()))

# ============================================
# 📂 SIDEBAR Y LÓGICA DE GUARDADO
# ============================================
with st.sidebar:
    st.subheader("📂 Historial")
    col_valida = "Nombre Regional" if "Nombre Regional" in df_movs.columns else ("Regional" if "Regional" in df_movs.columns else None)
    if col_valida:
        hist = df_movs[df_movs[col_valida] == nombre_regional]
        st.dataframe(hist, use_container_width=True)

    st.markdown("---")
    st.subheader("🏍️ Apartar unidad")

    if "modelo" in st.session_state:
        row = df_inv[df_inv['Item Number'] == st.session_state.modelo].iloc[0]
        disp = int(row['Disponible Restante'])

        st.success(f"{row['Modelo']} ({row['Color']})")

        if st.button("❌ Cancelar selección"):
            del st.session_state.modelo
            st.rerun()

        if disp > 0:
            suc = st.selectbox("Sucursal", df_age.iloc[:, 0].dropna(), key="suc")
            cant = st.number_input("Cantidad", 1, disp, key="cant")

            if st.button("Confirmar Apartado", use_container_width=True):
                # 1. COORDENADAS DE CELDA
                idx_original = df_inv.index[df_inv['Item Number'] == row['Item Number']][0]
                col_idx = df_inv.columns.get_loc(nombre_regional)
                
                fila_sheet = idx_original + 2 
                col_letter = col_to_letter(col_idx)
                celda_a1 = f"{col_letter}{fila_sheet}"

                nuevo_valor = int(df_inv.at[idx_original, nombre_regional] + cant)

                # 2. CONEXIÓN DIRECTA CON GSPREAD (SOLUCIÓN AL ERROR)
                try:
                    # Extraemos las credenciales que ya configuraste para st.connection
                    creds = conn._instance._service.credentials
                    client = gspread.authorize(creds) # Autorización manual exitosa
                    sh = client.open_by_url(URL)
                    
                    # Actualizar celda sin tocar el resto de la hoja (Protege fórmulas)
                    ws_inv = sh.worksheet("Inventario")
                    ws_inv.update_acell(celda_a1, nuevo_valor)

                    # Registrar movimiento
                    ws_movs = sh.worksheet("Movimientos_Apartados")
                    ws_movs.append_row([
                        str(uuid.uuid4())[:8].upper(),
                        datetime.now().strftime("%d/%m/%Y %H:%M"),
                        row['Item Number'], row['Modelo'], row['Color'],
                        row['Año Modelo'], suc, int(cant), nombre_regional
                    ])

                    st.balloons()
                    st.success(f"✅ Apartado exitoso en celda {celda_a1}")
                    st.cache_data.clear()
                    del st.session_state.modelo
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"Error de conexión: {e}")
    else:
        st.info("Selecciona un modelo del inventario")

# ============================================
# VISTA DE MODELOS
# ============================================
st.markdown("---")
st.subheader("Modelos disponibles")

for i, row in df_filtrado.iterrows():
    stock = int(row['Disponible Restante'])
    color = "🔴" if stock <= 0 else "🟢"
    col1, col2 = st.columns([5,1])
    with col1:
        st.markdown(f"**{row['Modelo']}** ({row['Color']}) | Año: {row['Año Modelo']} | Stock: {color} {stock}")
    with col2:
        if st.button("Seleccionar", key=f"btn_{i}"):
            st.session_state.modelo = row['Item Number']
            st.rerun()

# ============================================
# DASHBOARD Y TABLA
# ============================================
st.markdown("---")
st.header("📊 Dashboard de Control")
c1, c2 = st.columns(2)
with c1:
    st.subheader("Inventario Inicial por Modelo")
    st.bar_chart(df_inv.groupby("Modelo")["Disponible Inicial"].sum())
with c2:
    st.subheader("Unidades Apartadas")
    st.bar_chart(df_inv_calc.groupby("Modelo")["Apartado"].sum())

st.markdown("---")
st.subheader("Vista General de Tabla")
st.dataframe(df_inv, use_container_width=True)
