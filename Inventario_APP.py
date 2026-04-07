import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import uuid

# 1. Configuración y Conexión
conn = st.connection("gsheets", type=GSheetsConnection)
URL = "https://docs.google.com/spreadsheets/d/1mbzAa6zn_otA_y1932IyW8fSuf8XOehzarvxZBpleu0/edit?usp=sharing"

# --- FUNCIÓN DE CÁLCULO (Ponla aquí, al principio) ---
def recalcular_disponibles(df, lista_gerentes):
    """Suma horizontalmente los apartados y resta del inicial"""
    # Llenar vacíos con 0 para poder sumar
    for g in lista_gerentes:
        df[g] = pd.to_numeric(df[g], errors='coerce').fillna(0)
    
    df['Disponible Inicial'] = pd.to_numeric(df['Disponible Inicial'], errors='coerce').fillna(0)
    
    # Calcular: Disponible Restante = Inicial - (Suma de todos los gerentes)
    df['Disponible Restante'] = df['Disponible Inicial'] - df[lista_gerentes].sum(axis=1)
    return df

# 2. Carga de datos
@st.cache_data(ttl=300)
def load_all_data():
    inv = conn.read(spreadsheet=URL, worksheet="Inventario")
    usr = conn.read(spreadsheet=URL, worksheet="Usuarios")
    age = conn.read(spreadsheet=URL, worksheet="Agencias")
    return inv, usr, age

df_inv, df_usr, df_age = load_all_data()
gerentes = df_usr.iloc[:, 0].dropna().tolist()
sucursales = df_age.iloc[:, 0].dropna().tolist()

# --- RECALCULAR AL CARGAR (Para que el usuario vea datos reales) ---
df_inv = recalcular_disponibles(df_inv, gerentes)

# 3. Interfaz Principal
st.title("Sistema de Apartados y Logística")
# Coloca esto justo después de st.title("...")
if st.button("🔄 Sincronizar con Google Sheets"):
    st.cache_data.clear()
    st.rerun()
gerente_sel = st.sidebar.selectbox("Gerente Regional", gerentes)

# --- FORMULARIO DE APARTADO ---
with st.sidebar.form("Registro_Movimiento"):
    st.subheader("📝 Nuevo Apartado")
    modelo_sel = st.selectbox("Modelo / Artículo", df_inv['Descripción del artículo'])
    sucursal_dest = st.selectbox("Sucursal Destino", sucursales)
    cantidad = st.number_input("Cantidad", min_value=1, step=1)
    
    if st.form_submit_button("Confirmar y Registrar"):
        # Localizar datos
        idx = df_inv.index[df_inv['Descripción del artículo'] == modelo_sel][0]
        
        # 1. Actualizar cantidad del gerente en el DataFrame
        valor_previo = df_inv.at[idx, gerente_sel]
        df_inv.at[idx, gerente_sel] = valor_previo + cantidad
        
        # 2. RECALCULAR ANTES DE GUARDAR (Esto asegura que el 'Disponible Restante' se suba a Google)
        df_inv = recalcular_disponibles(df_inv, gerentes)
        
        # 3. Verificar si el stock quedó en negativo
        if df_inv.at[idx, 'Disponible Restante'] < 0:
            st.error(f"❌ Error: No hay suficiente stock. Quedarían {df_inv.at[idx, 'Disponible Restante']} unidades.")
        else:
            # GUARDAR EN INVENTARIO
            conn.update(spreadsheet=URL, worksheet="Inventario", data=df_inv)
            
            # GUARDAR EN MOVIMIENTOS (Historial)
            df_movs = conn.read(spreadsheet=URL, worksheet="Movimientos_Apartados")
            fila_data = df_inv.loc[idx]
            
            nuevo_mov = {
                "ID_Apartado": str(uuid.uuid4())[:8],
                "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "Item_Number": fila_data['Item Number'],
                "Modelo": fila_data['Modelo'],
                "Color": fila_data['Color'],
                "Año Modelo": fila_data['Año Modelo'],
                "Sucursal_Destino": sucursal_dest,
                "Cantidad": cantidad,
                "Nombre Regional": gerente_sel
            }
            
            df_movs = pd.concat([df_movs, pd.DataFrame([nuevo_mov])], ignore_index=True)
            conn.update(spreadsheet=URL, worksheet="Movimientos_Apartados", data=df_movs)
            
            st.success("✅ Registrado con éxito")
            st.cache_data.clear()
            st.rerun()

# 4. Visualización (La tabla ya sale con el cálculo hecho)
st.subheader(f"Inventario Actual - Vista {gerente_sel}")
cols_vista = ['Item Number', 'Modelo', 'Color', 'Año Modelo', 'Disponible Inicial', gerente_sel, 'Disponible Restante']
st.dataframe(df_inv[cols_vista], use_container_width=True, hide_index=True)
