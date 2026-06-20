import streamlit as st
import pandas as pd
from supabase import create_client, Client

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

# Función para traer los datos desde la nube
def fetch_data():
    # Traemos los últimos 100 registros ordenados por ID descendente
    response = supabase.table("weather_data") \
        .select("*") \
        .order("id", desc=True) \
        .limit(100) \
        .execute()
    
    if response.data:
        df = pd.DataFrame(response.data)
        # Convertir la columna de tiempo a formato legible
        df["created_at"] = pd.to_datetime(df["created_at"])
        # Ordenar cronológicamente para los gráficos
        return df.sort_values(by="created_at")
    return pd.DataFrame()

# Título de la aplicación
st.title("🌤️ Panel de Monitoreo - Estación Meteorológica")
st.markdown("Datos medidos en tiempo real e independientes desde la ESP32.")

# Botón manual de actualización
if st.button("🔄 Actualizar Datos"):
    st.rerun()

# Obtener datos
df = fetch_data()

if not df.empty:
    # 1. OBTENER LAS ÚLTIMAS LECTURAS (El último registro del DataFrame)
    ultima_lectura = df.iloc[-1]
    
    # Formatear la fecha para mostrarla
    fecha_local = ultima_lectura["created_at"].strftime("%d/%m/%Y %H:%M:%S")
    st.caption(f"Última actualización recibida: {fecha_local}")
    
    # 2. BLOQUE DE TARJETAS (Métricas principales)
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        temp = ultima_lectura["temperature"]
        st.metric(
            label="🌡️ Temperatura", 
            value=f"{temp:.1f} °C" if pd.notna(temp) else "N/A"
        )
        
    with col2:
        hum = ultima_lectura["humidity"]
        st.metric(
            label="💧 Humedad", 
            value=f"{hum:.1f} %" if pd.notna(hum) else "N/A"
        )
        
    with col3:
        viento = ultima_lectura["wind_speed"]
        st.metric(
            label="💨 Velocidad del Viento", 
            value=f"{viento:.1f} m/s" if pd.notna(viento) else "0.0 m/s"
        )
        
    with col4:
        pres = ultima_lectura["pressure"]
        st.metric(
            label="📉 Presión Atmosférica", 
            value=f"{pres:.1f} hPa" if pd.notna(pres) else "N/A"
        )

    st.divider()

    # 3. BLOQUE DE GRÁFICOS HISTÓRICOS
    st.subheader("📈 Historial de las últimas horas")
    
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

    # 4. TABLA DE DATOS CRUDA (Opcional, al final)
    with st.expander("📄 Ver registros históricos completos"):
        st.dataframe(
            df[["created_at", "temperature", "humidity", "pressure", "wind_speed"]]
            .sort_values(by="created_at", ascending=False),
            use_container_width=True
        )
else:
    st.warning("Aún no hay datos registrados en tu tabla de Supabase.")