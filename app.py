import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import date, timedelta

# Configuración de la página del navegador
st.set_page_config(
    page_title="Estación Meteorológica",
    page_icon="🌤️",
    layout="wide"
)

# Credenciales de Supabase
SUPABASE_URL = "https://qtzckgfxdbuudokoobim.supabase.co"
SUPABASE_KEY = "sb_publishable_k3bPaqbhMmhUnY8XaqaLKg_lq8tI-RE"

# Inicializar cliente de Supabase
@st.cache_resource
def init_connection():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_connection()

# --- BARRA LATERAL (FILTROS) ---
st.sidebar.title("⚙️ Filtros de Tiempo")
filtro_tiempo = st.sidebar.radio(
    "Selecciona qué datos visualizar:",
    ("Últimos datos (Tiempo Real)", "Historial Completo", "Rango de Fechas")
)

# Variables para el calendario
start_date = None
end_date = None

if filtro_tiempo == "Rango de Fechas":
    fechas = st.sidebar.date_input(
        "Selecciona el rango en el calendario:",
        value=(date.today() - timedelta(days=7), date.today()), # Por defecto los últimos 7 días
        max_value=date.today()
    )
    
    # Validar que el usuario haya seleccionado inicio y fin
    if len(fechas) == 2:
        start_date, end_date = fechas
    else:
        st.sidebar.warning("Por favor, selecciona también una fecha de término.")
        st.stop() # Detiene la ejecución hasta que se seleccione la segunda fecha

# --- FUNCIÓN DE EXTRACCIÓN DE DATOS ---
def fetch_data(filtro, start=None, end=None):
    query = supabase.table("weather_data").select("*")
    
    if filtro == "Rango de Fechas" and start and end:
        # Filtramos desde las 00:00:00 del día de inicio hasta las 23:59:59 del día de fin
        query = query.gte("created_at", f"{start}T00:00:00").lte("created_at", f"{end}T23:59:59")
        query = query.order("created_at", desc=False)
    
    elif filtro == "Últimos datos (Tiempo Real)":
        query = query.order("id", desc=True).limit(100)
    
    else: # Historial Completo
        # Limitamos a 10.000 registros para evitar que el navegador colapse si tienes meses de datos
        query = query.order("created_at", desc=False).limit(10000) 
        
    response = query.execute()
    
    if response.data:
        df = pd.DataFrame(response.data)
        df["created_at"] = pd.to_datetime(df["created_at"])
        # Para "Últimos datos", invertimos el orden para que los gráficos se lean de izquierda a derecha
        if filtro == "Últimos datos (Tiempo Real)":
            df = df.sort_values(by="created_at")
        return df
    return pd.DataFrame()

# --- INTERFAZ PRINCIPAL ---
st.title("🌤️ Panel de Monitoreo - Estación Meteorológica")

col_titulo, col_boton = st.columns([8, 2])
with col_boton:
    st.write("") # Espaciado
    if st.button("🔄 Actualizar Datos", use_container_width=True):
        st.rerun()

# Obtener datos según el filtro
df = fetch_data(filtro_tiempo, start_date, end_date)

if not df.empty:
    # 1. TARJETAS DE MÉTRICAS (Muestra el último valor del DataFrame)
    ultima_lectura = df.iloc[-1]
    fecha_local = ultima_lectura["created_at"].strftime("%d/%m/%Y %H:%M:%S")
    st.caption(f"Última lectura del rango seleccionado: {fecha_local}")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🌡️ Temperatura", f"{ultima_lectura['temperature']:.1f} °C" if pd.notna(ultima_lectura['temperature']) else "N/A")
    with col2:
        st.metric("💧 Humedad", f"{ultima_lectura['humidity']:.1f} %" if pd.notna(ultima_lectura['humidity']) else "N/A")
    with col3:
        st.metric("💨 Viento", f"{ultima_lectura['wind_speed']:.1f} m/s" if pd.notna(ultima_lectura['wind_speed']) else "0.0 m/s")
    with col4:
        st.metric("📉 Presión", f"{ultima_lectura['pressure']:.1f} hPa" if pd.notna(ultima_lectura['pressure']) else "N/A")

    st.divider()

    # 2. GRÁFICOS
    st.subheader(f"📈 Visualización: {filtro_tiempo}")
    
    tab1, tab2, tab3 = st.tabs(["Temperatura y Humedad", "Presión", "Viento"])
    
    with tab1:
        st.markdown("**Evolución de la Temperatura (°C)**")
        st.line_chart(data=df, x="created_at", y="temperature", color="#FF4B4B")
        st.markdown("**Evolución de la Humedad (%)**")
        st.line_chart(data=df, x="created_at", y="humidity", color="#0083B0")
        
    with tab2:
        st.markdown("**Presión Atmosférica (hPa)**")
        st.line_chart(data=df, x="created_at", y="pressure", color="#00D2FF")
        
    with tab3:
        st.markdown("**Comportamiento del Viento (m/s)**")
        st.bar_chart(data=df, x="created_at", y="wind_speed", color="#778899")

    # 3. TABLA CRUDA
    with st.expander("📄 Ver registros del periodo seleccionado"):
        st.dataframe(
            df[["created_at", "temperature", "humidity", "pressure", "wind_speed"]].sort_values(by="created_at", ascending=False),
            use_container_width=True
        )
else:
    st.warning("No hay datos registrados para el periodo seleccionado.")