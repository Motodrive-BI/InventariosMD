import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import uuid
import gspread
from google.oauth2.service_account import Credentials

# ============================================
# CONFIGURACIÓN INICIAL
# ============================================
st.set_page_config(page_title="Inventario Motodrive", layout="wide")

# Conexión estándar para lectura
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
# FUNCIONES DE UTILIDAD
# ============================================
def col_to_letter(col_idx):
    """Convierte índice de columna (0, 1, 2...) a letra de Excel (A, B, C...)"""
    letter = ""
    col_idx += 1 
    while col_idx > 0:
        col_idx, remainder = divmod(col_idx - 1, 26)
        letter = chr(65 + remainder) + letter
    return letter

# ============================================
# SISTEMA DE LOGIN
# ============================================
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔐 Acceso Inventario")
    email = st.text_input("Correo electrónico")
    if st.button("Ingresar"):
        if email.lower() in df_usr['Correo'].str.lower().values:
            st.session_state.autenticado = True
            st.session_state.user_email = email.lower()
            st.rerun()
        else:
            st.error("Usuario no autorizado.")
    st.stop()

# ============================================
# PROCESAMIENTO DE DATOS DEL USUARIO
# ============================================
user_email = st.session_state.user_email
datos_usuario = df_usr[df_usr['Correo'].str.lower() == user_email].iloc[0]
nombre_regional = datos_usuario.iloc[0]

# Identificar columnas de gerentes para cálculos locales
gerentes = [g for g in df_usr.iloc[:,0].dropna().tolist() if g in df_inv.columns]

for g in gerentes:
    df_inv[g] = pd.to_numeric(df_inv[g], errors='coerce').fillna(0).astype(int)

# Estos cálculos son solo para mostrar en la App, no se guardan (evita pisar fórmulas)
df_inv['Disponible Inicial'] = pd.to_numeric(df_inv['Disponible Inicial'], errors='coerce').fillna(0).astype(int)
df_inv['Disponible Restante'] = (df_inv['Disponible Inicial'] - df_inv[gerentes].sum(axis=1)).astype(int)

df_inv_calc = df_inv.copy()
df_inv_calc['Apartado'] = df_inv_calc['Disponible Inicial'] - df_inv_calc['Disponible Restante']

# ============================================
# BÚSQUEDA Y FILTROS
# ============================================
st.title(f"🏍️ Gestión: {nombre_regional}")
st.markdown("---")

colf1, colf2, colf3 = st.columns(3)
with colf1: busqueda = st.text_input("🔍 Buscar por modelo")
with colf2: filtro_modelo = st.multiselect("Modelo", sorted(df_inv['Modelo'].unique()))
with colf3: filtro_año = st.multiselect("Año", sorted(df_inv['Año Modelo'].unique()))

df_filtrado = df_inv.copy()
if busqueda: df_filtrado = df_filtrado[df_filtrado['Modelo'].str.contains(busqueda, case=False, na=False)]
if filtro_modelo: df_filtrado = df_filtrado[df_filtrado['Modelo'].isin(filtro_modelo)]
if filtro_año: df_filtrado = df_filtrado[df_filtrado['Año Modelo'].isin(filtro_año)]

# ============================================
# KPIs
# ============================================
c1, c2, c3 = st.columns(3)
c1.metric("Stock Total", int(df_inv['Disponible Inicial'].sum()))
c2.metric("Disponible Neto", int(df_inv['Disponible Restante'].sum()))
c3.metric("Tus Apartados", int(df_inv[nombre_regional].sum()))

# ============================================
# SIDEBAR: APARTADOS Y GUARDADO (MÉTODO SEGURO)
# ============================================
with st.sidebar:
    st.header("🛒 Panel de Apartado")
    
    if "modelo" in st.session_state:
        row = df_inv[df_inv['Item Number'] == st.session_state.modelo].iloc[0]
        disp = int(row['Disponible Restante'])

        st.info(f"Seleccionado: **{row['Modelo']}**")
        
        if disp > 0:
            suc = st.selectbox("Sucursal de destino", df_age.iloc[:, 0].dropna())
            cant = st.number_input("Cantidad a apartar", 1, disp)

            if st.button("Confirmar Movimiento", use_container_width=True):
                # 1. LOCALIZACIÓN DE LA CELDA
                idx_orig = df_inv.index[df_inv['Item Number'] == row['Item Number']][0]
                col_idx = df_inv.columns.get_loc(nombre_regional)
                
                # Excel/Sheets: Fila +2 (encabezado y base 1). Columna a letra.
                celda_a1 = f"{col_to_letter(col_idx)}{idx_orig + 2}"
                nuevo_valor_gerente = int(df_inv.at[idx_orig, nombre_regional] + cant)

                # 2. ESCRITURA MEDIANTE GSPREAD (SOLUCIÓN A FÓRMULAS BORRADAS)
                try:
                    # Extraer credenciales directamente de los secretos
                    creds_info = st.secrets["connections"]["gsheets"]
                    scope = ["https://www.googleapis.com/auth/spreadsheets"]
                    creds = Credentials.from_service_account_info(creds_info, scopes=scope)
                    client = gspread.authorize(creds)
                    sh = client.open_by_url(URL)
                    
                    # Actualizar solo la celda del Gerente en 'Inventario'
                    # Esto permite que las fórmulas de las otras columnas sigan funcionando
                    ws_inv = sh.worksheet("Inventario")
                    ws_inv.update_acell(celda_a1, nuevo_valor_gerente)

                    # Registrar el log en 'Movimientos_Apartados'
                    ws_movs = sh.worksheet("Movimientos_Apartados")
                    ws_movs.append_row([
                        str(uuid.uuid4())[:8].upper(),
                        datetime.now().strftime("%d/%m/%Y %H:%M"),
                        row['Item Number'], row['Modelo'], row['Color'],
                        row['Año Modelo'], suc, int(cant), nombre_regional
                    ])

                    st.success("✅ ¡Actualizado con éxito!")
                    st.cache_data.clear() # Forzar recarga de datos
                    del st.session_state.modelo
                    st.rerun()
                except Exception as e:
                    st.error(f"Error de escritura: {e}")
        else:
            st.error("Sin unidades disponibles.")
            
        if st.button("Cancelar"):
            del st.session_state.modelo
            st.rerun()
    else:
        st.write("Selecciona una unidad en la tabla principal para comenzar.")

# ============================================
# CUERPO PRINCIPAL: LISTADO Y GRÁFICOS
# ============================================
st.markdown("---")
st.subheader("Inventario Disponible")

# Mostrar modelos como tarjetas simples
for i, row in df_filtrado.iterrows():
    stock = int(row['Disponible Restante'])
    col_t, col_b = st.columns([4, 1])
    with col_t:
        color_bullet = "🟢" if stock > 0 else "🔴"
        st.write(f"{color_bullet} **{row['Modelo']}** | {row['Color']} | Año: {row['Año Modelo']} | **Disponible: {stock}**")
    with col_b:
        if st.button("Apartar", key=f"btn_{i}"):
            st.session_state.modelo = row['Item Number']
            st.rerun()

st.markdown("---")
st.header("📊 Resumen Ejecutivo")
c_graph1, c_graph2 = st.columns(2)
with c_graph1:
    st.write("**Stock Inicial**")
    st.bar_chart(df_inv.groupby("Modelo")["Disponible Inicial"].sum())
with c_graph2:
    st.write("**Unidades Apartadas**")
    st.bar_chart(df_inv_calc.groupby("Modelo")["Apartado"].sum())

st.markdown("---")
st.subheader("Detalle General (Solo lectura)")
st.dataframe(df_inv, use_container_width=True)
