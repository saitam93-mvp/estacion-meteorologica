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
        
        # Agregamos TODAS las columnas nuevas a la lista de numéricas si existen
        cols_esperadas = ["temperature", "humidity", "pressure", "wind_speed", "co2", "pm1_0", "pm25", "pm10", "particulas_03um"]
        cols_numericas = [col for col in cols_esperadas if col in df.columns]
            
        df_num = df[cols_numericas]
        
        if total_filas > 10000:
            df = df_num.resample("1h").mean().dropna().reset_index()
        elif total_filas > 2000:
            df = df_num.resample("10min").mean().dropna().reset_index()
        else:
            df = df_num.resample("2min").mean().dropna().reset_index()
            
        return df, cols_numericas

    return pd.DataFrame(), []

# --- INTERFAZ PRINCIPAL ---
df, columnas_activas = fetch_data(filtro_tiempo, start_date, end_date)

if not df.empty:
    # 1. TARJETAS DE MÉTRICAS (Clima + Calidad del Aire)
    ultima_lectura = df.iloc[-1]
    fecha_local = ultima_lectura["created_at"].strftime("%d/%m/%Y %H:%M:%S")
    st.caption(f"Última actualización (Datos promediados de la franja horaria): {fecha_local}")
    
    st.subheader("Condiciones Meteorológicas")
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
    
    st.subheader("Calidad del Aire 🌬️")
    col5, col6, col7, col8, col9 = st.columns(5)
    with col5:
        if "co2" in df.columns: st.metric("😶‍🌫️ CO2", f"{ultima_lectura['co2']:.0f} ppm")
    with col6:
        if "pm1_0" in df.columns: st.metric("🦠 PM 1.0", f"{ultima_lectura['pm1_0']:.0f} µg/m³")
    with col7:
        if "pm25" in df.columns: st.metric("😷 PM 2.5", f"{ultima_lectura['pm25']:.0f} µg/m³")
    with col8:
        if "pm10" in df.columns: st.metric("🪨 PM 10", f"{ultima_lectura['pm10']:.0f} µg/m³")
    with col9:
        if "particulas_03um" in df.columns: st.metric("🔬 P >0.3µm", f"{ultima_lectura['particulas_03um']:.0f}")

    st.divider()

    # 2. GRÁFICOS REORGANIZADOS CON NUEVAS PESTAÑAS
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Temperatura", "Humedad y Presión", "Viento", "Material Particulado", "CO2"])
    
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
        grafico_viento = alt.Chart(df).encode(
            x=alt.X("created_at:T", title="Hora"),
            y=alt.Y("wind_speed:Q", title="Velocidad (m/s)"),
            tooltip=[
                alt.Tooltip("created_at:T", title="Hora", format="%d/%m %H:%M"),
                alt.Tooltip("wind_speed:Q", title="Velocidad (m/s)", format=".1f")
            ]
        ).mark_bar(color="#778899", opacity=0.8).interactive()
        
        st.altair_chart(grafico_viento, use_container_width=True)
        
    with tab4:
        st.markdown("<h5 style='text-align: center;'>Evolución de Material Particulado (µg/m³)</h5>", unsafe_allow_html=True)
        if all(col in df.columns for col in ["pm1_0", "pm25", "pm10"]):
            # Preparamos el DataFrame para st.line_chart usando la fecha como índice
            df_pm = df[["created_at", "pm1_0", "pm25", "pm10"]].set_index("created_at")
            df_pm = df_pm.rename(columns={"pm1_0": "PM 1.0 (Ultrafino)", "pm25": "PM 2.5 (Fino)", "pm10": "PM 10 (Grueso)"})
            st.line_chart(df_pm, color=["#FF4B4B", "#FFA15A", "#FFE24B"])
            
            st.markdown("<br><h5 style='text-align: center;'>Densidad de Partículas (>0.3µm)</h5>", unsafe_allow_html=True)
            df_part = df[["created_at", "particulas_03um"]].set_index("created_at")
            st.area_chart(df_part, color="#636EFA")
        else:
            st.info("Esperando datos de Material Particulado...")

    with tab5:
        st.markdown("<h5 style='text-align: center;'>Niveles de CO2 (ppm)</h5>", unsafe_allow_html=True)
        if "co2" in df.columns:
            df_co2 = df[["created_at", "co2"]].set_index("created_at")
            st.line_chart(df_co2, color="#00C853")
        else:
            st.info("Esperando datos de CO2...")

    # 3. TABLA CRUDA
    with st.expander("📄 Ver registros del periodo seleccionado"):
        columnas_a_mostrar = ["created_at"] + columnas_activas
        st.dataframe(
            df[columnas_a_mostrar].sort_values(by="created_at", ascending=False),
            use_container_width=True
        )
else:
    st.warning("No hay datos registrados para el periodo seleccionado.")