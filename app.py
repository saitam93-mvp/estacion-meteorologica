import streamlit as st
import pandas as pd
import altair as alt
from supabase import create_client, Client
from datetime import date, timedelta, datetime

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="Estación Meteorológica",
    page_icon="🌤️",
    layout="wide"
)

# --- CREDENCIALES DE SUPABASE ---
SUPABASE_URL = "https://qtzckgfxdbuudokoobim.supabase.co"
SUPABASE_KEY = "sb_publishable_k3bPaqbhMmhUnY8XaqaLKg_lq8tI-RE"

@st.cache_resource
def init_connection():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_connection()

# --- BARRA LATERAL (FILTROS Y CONTROLES) ---
st.sidebar.title("⚙️ Controles")

if st.sidebar.button("🔄 Actualizar Datos", use_container_width=True):
    st.rerun()

st.sidebar.divider()

st.sidebar.subheader("Filtros de Tiempo")
filtro_tiempo = st.sidebar.radio(
    "Selecciona qué datos visualizar:",
    ("Últimos datos (Tiempo Real)", "Historial Completo", "Rango de Fechas")
)

start_date = None
end_date = None

if filtro_tiempo == "Rango de Fechas":
    fechas = st.sidebar.date_input(
        "Selecciona el rango en el calendario:",
        value=(date.today() - timedelta(days=1), date.today()), 
        max_value=date.today()
    )
    
    if len(fechas) == 2:
        start_date, end_date = fechas
    else:
        st.sidebar.warning("Por favor, selecciona también una fecha de término.")
        st.stop() 

# --- FUNCIÓN DE EXTRACCIÓN Y COMPRESIÓN DE DATOS ---
def fetch_data(filtro, start=None, end=None):
    query = supabase.table("weather_data").select("*")
    
    # 1. Filtros de Tiempo
    if filtro == "Rango de Fechas" and start and end:
        query = query.gte("created_at", f"{start}T00:00:00").lte("created_at", f"{end}T23:59:59")
    elif filtro == "Últimos datos (Tiempo Real)":
        hace_24_hrs = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        query = query.gte("created_at", hace_24_hrs)
    
    # Siempre ordenamos ascendente para la paginación
    query = query.order("created_at", desc=False)
    
    # 2. Paginación: Burlar el límite de 1000 filas de Supabase
    all_data = []
    chunk_size = 1000
    offset = 0
    
    # Límite de seguridad: máximo 50.000 filas por consulta
    while offset < 50000:
        res = query.range(offset, offset + chunk_size - 1).execute()
        if not res.data:
            break
        all_data.extend(res.data)
        if len(res.data) < chunk_size:
            break
        offset += chunk_size

    # 3. Procesamiento
    if all_data:
        df = pd.DataFrame(all_data)
        
        # Ajuste de Zona Horaria
        df["created_at"] = pd.to_datetime(df["created_at"])
        if df["created_at"].dt.tz is None:
            df["created_at"] = df["created_at"].dt.tz_localize("UTC")
        df["created_at"] = df["created_at"].dt.tz_convert("America/Santiago").dt.tz_localize(None)
        
        df = df.sort_values(by="created_at")
        
        # 4. COMPRESIÓN INTELIGENTE
        df.set_index("created_at", inplace=True)
        total_filas = len(df)
        
        cols_numericas = ["temperature", "humidity", "pressure", "wind_speed"]
        if "co2" in df.columns:
            cols_numericas.append("co2")
            
        df_num = df[cols_numericas]
        
        if total_filas > 10000:
            df = df_num.resample("1h").mean().dropna().reset_index()
        elif total_filas > 2000:
            df = df_num.resample("10min").mean().dropna().reset_index()
        else:
            df = df_num.resample("2min").mean().dropna().reset_index()
            
        return df

    return pd.DataFrame()

# --- INTERFAZ PRINCIPAL ---
# (Título principal eliminado)

# Obtener datos
df = fetch_data(filtro_tiempo, start_date, end_date)

if not df.empty:
    # 1. TARJETAS DE MÉTRICAS
    ultima_lectura = df.iloc[-1]
    fecha_local = ultima_lectura["created_at"].strftime("%d/%m/%Y %H:%M:%S")
    st.caption(f"Última actualización (Datos promediados de la franja horaria): {fecha_local}")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🌡️ Temperatura", f"{ultima_lectura['temperature']:.1f} °C")
    with col2:
        st.metric("💧 Humedad", f"{ultima_lectura['humidity']:.1f} %")
    with col3:
        st.metric("💨 Viento", f"{ultima_lectura['wind_speed']:.1f} m/s")
    with col4:
        st.metric("📉 Presión", f"{ultima_lectura['pressure']:.1f} hPa")

    st.divider()

    # 2. GRÁFICOS REORGANIZADOS
    tab1, tab2, tab3 = st.tabs(["Temperatura", "Humedad y Presión", "Viento"])
    
    with tab1:
        st.line_chart(data=df, x="created_at", y="temperature", color="#FF4B4B")
        
    with tab2:
        st.markdown("<h5 style='text-align: center;'><span style='color: #0083B0;'>Humedad (%)</span> &nbsp;&nbsp;|&nbsp;&nbsp; <span style='color: #FF8C00;'>Presión (hPa)</span></h5>", unsafe_allow_html=True)
        
        base = alt.Chart(df).encode(
            x=alt.X("created_at:T", title="Hora")
        )

        linea_humedad = base.mark_line(color="#0083B0", size=3).encode(
            y=alt.Y("humidity:Q", title="Humedad (%)", scale=alt.Scale(zero=False)),
            tooltip=[
                alt.Tooltip("created_at:T", title="Hora", format="%d/%m %H:%M"), 
                alt.Tooltip("humidity:Q", title="Humedad (%)", format=".1f")
            ]
        )

        linea_presion = base.mark_line(color="#FF8C00", size=3).encode(
            y=alt.Y("pressure:Q", title="Presión (hPa)", scale=alt.Scale(zero=False)),
            tooltip=[
                alt.Tooltip("created_at:T", title="Hora", format="%d/%m %H:%M"), 
                alt.Tooltip("pressure:Q", title="Presión (hPa)", format=".1f")
            ]
        )

        grafico_mixto = alt.layer(linea_humedad, linea_presion).resolve_scale(
            y='independent'
        ).interactive()

        st.altair_chart(grafico_mixto, use_container_width=True)
        
    with tab3:
        espacio_grafico = st.empty()
        
        ventana = st.slider("Suavizado del Promedio Móvil (N° de lecturas grupales)", min_value=2, max_value=60, value=15)
        
        df["Promedio Móvil"] = df["wind_speed"].rolling(window=ventana, min_periods=1).mean()
        
        base_viento = alt.Chart(df).encode(x=alt.X("created_at:T", title="Hora"))
        barras = base_viento.mark_bar(color="#778899", opacity=0.6).encode(y=alt.Y("wind_speed:Q", title="Velocidad (m/s)"))
        linea = base_viento.mark_line(color="#FF4B4B", size=3).encode(y=alt.Y("Promedio Móvil:Q"))
        
        grafico_viento = alt.layer(barras, linea).interactive()
        
        espacio_grafico.altair_chart(grafico_viento, use_container_width=True)

    # 3. TABLA CRUDA
    with st.expander("📄 Ver registros del periodo seleccionado"):
        st.dataframe(
            df[["created_at", "temperature", "humidity", "pressure", "wind_speed"]].sort_values(by="created_at", ascending=False),
            use_container_width=True
        )
else:
    st.warning("No hay datos registrados para el periodo seleccionado.")