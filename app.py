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

# --- ESTADO DE LA SESIÓN ---
if "filtro_tiempo_estacion" not in st.session_state:
    st.session_state["filtro_tiempo_estacion"] = "Último Día"
if "rango_fechas_estacion" not in st.session_state:
    st.session_state["rango_fechas_estacion"] = (date.today() - timedelta(days=1), date.today())

# --- BARRA LATERAL (FILTROS Y CONTROLES) ---
st.sidebar.title("⚙️ Controles")

if st.sidebar.button("🔄 Actualizar Datos", use_container_width=True):
    st.session_state["filtro_tiempo_estacion"] = "Último Día"
    st.session_state["rango_fechas_estacion"] = (date.today() - timedelta(days=1), date.today())
    st.rerun()

st.sidebar.divider()

st.sidebar.subheader("Filtros de Tiempo")

filtro_tiempo = st.sidebar.radio(
    "Selecciona qué datos visualizar:",
    ("Último Día", "Última Semana", "Historial Completo", "Rango de Fechas"),
    key="filtro_tiempo_estacion"
)

start_date = None
end_date = None

if filtro_tiempo == "Rango de Fechas":
    fechas = st.sidebar.date_input(
        "Selecciona el rango en el calendario:",
        max_value=date.today(),
        key="rango_fechas_estacion"
    )
    
    if isinstance(fechas, tuple) and len(fechas) == 2:
        start_date, end_date = fechas
    else:
        st.sidebar.warning("Por favor, selecciona también una fecha de término.")
        st.stop() 

# --- FUNCIÓN DE EXTRACCIÓN Y COMPRESIÓN DE DATOS ---
def fetch_data(filtro, start=None, end=None):
    query = supabase.table("weather_data").select("*")
    
    if filtro == "Rango de Fechas" and start and end:
        query = query.gte("created_at", f"{start}T00:00:00").lte("created_at", f"{end}T23:59:59")
    elif filtro == "Último Día":
        hace_24_hrs = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        query = query.gte("created_at", hace_24_hrs)
    elif filtro == "Última Semana":
        hace_7_dias = (datetime.utcnow() - timedelta(days=7)).isoformat()
        query = query.gte("created_at", hace_7_dias)
    
    query = query.order("created_at", desc=False)
    
    all_data = []
    chunk_size = 1000
    offset = 0
    
    while offset < 50000:
        res = query.range(offset, offset + chunk_size - 1).execute()
        if not res.data:
            break
        all_data.extend(res.data)
        if len(res.data) < chunk_size:
            break
        offset += chunk_size

    if all_data:
        df = pd.DataFrame(all_data)
        
        df["created_at"] = pd.to_datetime(df["created_at"])
        if df["created_at"].dt.tz is None:
            df["created_at"] = df["created_at"].dt.tz_localize("UTC")
        df["created_at"] = df["created_at"].dt.tz_convert("America/Santiago").dt.tz_localize(None)
        
        df = df.sort_values(by="created_at")
        df.set_index("created_at", inplace=True)
        total_filas = len(df)
        
        cols_esperadas = ["temperature", "humidity", "pressure", "wind_speed", "co2", "pm1_0", "pm25", "pm10", "particulas_03um"]
        cols_numericas = [col for col in cols_esperadas if col in df.columns]
            
        df_num = df[cols_numericas]
        
        if total_filas > 10000:
            df = df_num.resample("1h").mean().dropna(how="all").reset_index()
        elif total_filas > 2000:
            df = df_num.resample("10min").mean().dropna(how="all").reset_index()
        else:
            df = df_num.resample("2min").mean().dropna(how="all").reset_index()
            
        return df, cols_numericas

    return pd.DataFrame(), []

# --- INTERFAZ PRINCIPAL ---
df, columnas_activas = fetch_data(filtro_tiempo, start_date, end_date)

if not df.empty:
    ultima_lectura = df.iloc[-1]
    fecha_local = ultima_lectura["created_at"].strftime("%d/%m/%Y %H:%M:%S")
    st.caption(f"Última actualización (Datos promediados de la franja horaria): {fecha_local}")
    
    st.subheader("Condiciones Meteorológicas")
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("🌡️ Temperatura", f"{ultima_lectura['temperature']:.1f} °C")
    with col2: st.metric("💧 Humedad", f"{ultima_lectura['humidity']:.1f} %")
    with col3: st.metric("💨 Viento", f"{ultima_lectura['wind_speed']:.1f} m/s")
    with col4: st.metric("📉 Presión", f"{ultima_lectura['pressure']:.1f} hPa")

    st.divider()
    
    # --- LÓGICA DE ESTADO PM 2.5 ---
    titulo_pm25 = "😷 PM 2.5"
    if "pm25" in df.columns and pd.notna(ultima_lectura['pm25']):
        val_pm25 = ultima_lectura['pm25']
        if val_pm25 <= 50: titulo_pm25 = "😷 PM 2.5 (Bueno 🟢)"
        elif val_pm25 <= 80: titulo_pm25 = "😷 PM 2.5 (Regular 🟡)"
        elif val_pm25 <= 110: titulo_pm25 = "😷 PM 2.5 (Alerta 🟠)"
        elif val_pm25 <= 170: titulo_pm25 = "😷 PM 2.5 (Preemergencia 🔴)"
        else: titulo_pm25 = "😷 PM 2.5 (Emergencia 🟣)"

    # --- LÓGICA DE ESTADO PM 10 (Norma Chilena de Calidad del Aire) ---
    titulo_pm10 = "🪨 PM 10"
    if "pm10" in df.columns and pd.notna(ultima_lectura['pm10']):
        val_pm10 = ultima_lectura['pm10']
        if val_pm10 <= 150: titulo_pm10 = "🪨 PM 10 (Bueno 🟢)"
        elif val_pm10 <= 199: titulo_pm10 = "🪨 PM 10 (Regular 🟡)"
        elif val_pm10 <= 299: titulo_pm10 = "🪨 PM 10 (Alerta 🟠)"
        elif val_pm10 <= 399: titulo_pm10 = "🪨 PM 10 (Preemergencia 🔴)"
        else: titulo_pm10 = "🪨 PM 10 (Emergencia 🟣)"

    st.subheader("Calidad del Aire 🌬️")
    col5, col6, col7, col8, col9 = st.columns(5)
    with col5:
        if "co2" in df.columns and pd.notna(ultima_lectura['co2']): st.metric("😶‍🌫️ CO2", f"{ultima_lectura['co2']:.0f} ppm")
    with col6:
        if "pm1_0" in df.columns and pd.notna(ultima_lectura['pm1_0']): st.metric("🦠 PM 1.0", f"{ultima_lectura['pm1_0']:.0f} µg/m³")
    with col7:
        if "pm25" in df.columns and pd.notna(ultima_lectura['pm25']): st.metric(titulo_pm25, f"{ultima_lectura['pm25']:.0f} µg/m³")
    with col8:
        if "pm10" in df.columns and pd.notna(ultima_lectura['pm10']): st.metric(titulo_pm10, f"{ultima_lectura['pm10']:.0f} µg/m³")
    with col9:
        if "particulas_03um" in df.columns and pd.notna(ultima_lectura['particulas_03um']): st.metric("🔬 P >0.3µm", f"{ultima_lectura['particulas_03um']:.0f}")

    st.divider()

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Temperatura", "Humedad y Presión", "Viento", "Material Particulado", "CO2", "Comparador Dinámico"])
    
    with tab1:
        st.line_chart(data=df, x="created_at", y="temperature", color="#FF4B4B")
        
    with tab2:
        st.markdown("<h5 style='text-align: center;'><span style='color: #0083B0;'>Humedad (%)</span> &nbsp;&nbsp;|&nbsp;&nbsp; <span style='color: #FF8C00;'>Presión (hPa)</span></h5>", unsafe_allow_html=True)
        base_fija = alt.Chart(df).encode(x=alt.X("created_at:T", title="Hora"))
        linea_hum_fija = base_fija.mark_line(color="#0083B0", size=3).encode(
            y=alt.Y("humidity:Q", title="Humedad (%)", scale=alt.Scale(zero=False)),
            tooltip=[alt.Tooltip("created_at:T", title="Hora", format="%d/%m %H:%M"), alt.Tooltip("humidity:Q", title="Humedad (%)", format=".1f")]
        )
        linea_pres_fija = base_fija.mark_line(color="#FF8C00", size=3).encode(
            y=alt.Y("pressure:Q", title="Presión (hPa)", scale=alt.Scale(zero=False)),
            tooltip=[alt.Tooltip("created_at:T", title="Hora", format="%d/%m %H:%M"), alt.Tooltip("pressure:Q", title="Presión (hPa)", format=".1f")]
        )
        grafico_fijo_mixto = alt.layer(linea_hum_fija, linea_pres_fija).resolve_scale(y='independent').interactive()
        st.altair_chart(grafico_fijo_mixto, use_container_width=True)
        
    with tab3:
        grafico_viento = alt.Chart(df).encode(
            x=alt.X("created_at:T", title="Hora"),
            y=alt.Y("wind_speed:Q", title="Velocidad (m/s)"),
            tooltip=[alt.Tooltip("created_at:T", title="Hora", format="%d/%m %H:%M"), alt.Tooltip("wind_speed:Q", title="Velocidad (m/s)", format=".1f")]
        ).mark_bar(color="#778899", opacity=0.8).interactive()
        st.altair_chart(grafico_viento, use_container_width=True)

    with tab4:
        if all(col in df.columns for col in ["pm1_0", "pm25", "pm10"]):
            
            df_pm = df.dropna(subset=["pm1_0", "pm25", "pm10"], how="all")[["created_at", "pm1_0", "pm25", "pm10"]]
            df_pm = df_pm.rename(columns={"pm1_0": "PM 1.0", "pm25": "PM 2.5", "pm10": "PM 10"})
            df_pm_melted = df_pm.melt(id_vars="created_at", var_name="Partícula", value_name="Concentración")

            # NUEVO: Orientamos la leyenda hacia abajo (orient='bottom') para que no estorbe en celulares
            lineas_pm = alt.Chart(df_pm_melted).mark_line(size=2).encode(
                x=alt.X("created_at:T", title="Hora"),
                y=alt.Y("Concentración:Q", title="µg/m³"),
                color=alt.Color("Partícula:N", title=None, scale=alt.Scale(
                    domain=["PM 10", "PM 2.5", "PM 1.0"],
                    range=["#E0E0E0", "#00E676", "#00E5FF"]
                ), legend=alt.Legend(
                    orient="bottom",
                    direction="horizontal",
                    titlePadding=10,
                    padding=10
                )),
                tooltip=[
                    alt.Tooltip("created_at:T", title="Hora", format="%d/%m %H:%M"),
                    alt.Tooltip("Partícula:N", title="Tipo"),
                    alt.Tooltip("Concentración:Q", title="µg/m³", format=".0f")
                ]
            )

            rangos_df = pd.DataFrame({
                'Nivel': ['Regular (>50)', 'Alerta (>80)', 'Preemergencia (>110)', 'Emergencia (>170)'],
                'Valor': [50, 80, 110, 170],
                'Color': ['#F1C40F', '#E67E22', '#E74C3C', '#8E44AD']
            })

            reglas = alt.Chart(rangos_df).mark_rule(strokeDash=[5, 5], opacity=0.5).encode(
                y='Valor:Q',
                color=alt.Color('Color:N', scale=None)
            )

            textos_sombra = alt.Chart(rangos_df).mark_text(
                align='left', baseline='bottom', dx=5, dy=-4, fontSize=12, fontWeight='bold',
                stroke='#0E1117', strokeWidth=3 
            ).encode(
                x=alt.value(10),
                y='Valor:Q',
                text='Nivel:N'
            )

            textos_frente = alt.Chart(rangos_df).mark_text(
                align='left', baseline='bottom', dx=5, dy=-4, fontSize=12, fontWeight='bold'
            ).encode(
                x=alt.value(10),
                y='Valor:Q',
                text='Nivel:N',
                color=alt.Color('Color:N', scale=None)
            )

            grafico_pm_final = alt.layer(lineas_pm, reglas, textos_sombra, textos_frente).interactive()
            st.altair_chart(grafico_pm_final, use_container_width=True)
            
            st.markdown("<br><h5 style='text-align: center;'>Densidad de Partículas (>0.3µm)</h5>", unsafe_allow_html=True)
            df_part = df.dropna(subset=["particulas_03um"])[["created_at", "particulas_03um"]].set_index("created_at")
            st.area_chart(df_part, color="#636EFA")
        else:
            st.info("Esperando datos de Material Particulado...")

    with tab5:
        if "co2" in df.columns:
            df_co2 = df.dropna(subset=["co2"])[["created_at", "co2"]].set_index("created_at")
            st.line_chart(df_co2, color="#00C853")
        else:
            st.info("Esperando datos de CO2...")

    with tab6:
        opciones_metricas = {
            "Temperatura (°C)": {"col": "temperature", "color": "#FF4B4B"},
            "Humedad (%)": {"col": "humidity", "color": "#0083B0"},
            "Presión (hPa)": {"col": "pressure", "color": "#FF8C00"},
            "Viento (m/s)": {"col": "wind_speed", "color": "#778899"}
        }
        if "co2" in df.columns: opciones_metricas["CO2 (ppm)"] = {"col": "co2", "color": "#00C853"}
        if "pm25" in df.columns: opciones_metricas["PM 2.5 (µg/m³)"] = {"col": "pm25", "color": "#00E676"}

        col_sel1, col_sel2 = st.columns(2)
        with col_sel1: eje_izq = st.selectbox("Eje Izquierdo:", list(opciones_metricas.keys()), index=0)
        with col_sel2:
            opciones_der = ["Ninguna"] + [m for m in opciones_metricas.keys() if m != eje_izq]
            eje_der = st.selectbox("Eje Derecho:", opciones_der, index=1)
            
        st.write("") 
        base_dinamica = alt.Chart(df).encode(x=alt.X("created_at:T", title="Hora"))
        col_1, color_1 = opciones_metricas[eje_izq]["col"], opciones_metricas[eje_izq]["color"]
        
        linea_1 = base_dinamica.mark_line(color=color_1, size=3).encode(
            y=alt.Y(f"{col_1}:Q", title=eje_izq, scale=alt.Scale(zero=False)),
            tooltip=[alt.Tooltip("created_at:T", title="Hora", format="%d/%m %H:%M"), alt.Tooltip(f"{col_1}:Q", title=eje_izq, format=".1f")]
        )

        if eje_der != "Ninguna":
            col_2, color_2 = opciones_metricas[eje_der]["col"], opciones_metricas[eje_der]["color"]
            linea_2 = base_dinamica.mark_line(color=color_2, size=3).encode(
                y=alt.Y(f"{col_2}:Q", title=eje_der, scale=alt.Scale(zero=False)),
                tooltip=[alt.Tooltip("created_at:T", title="Hora", format="%d/%m %H:%M"), alt.Tooltip(f"{col_2}:Q", title=eje_der, format=".1f")]
            )
            grafico_mixto = alt.layer(linea_1, linea_2).resolve_scale(y='independent').interactive()
            st.markdown(f"<h5 style='text-align: center;'><span style='color: {color_1};'>{eje_izq}</span> &nbsp;&nbsp;|&nbsp;&nbsp; <span style='color: {color_2};'>{eje_der}</span></h5>", unsafe_allow_html=True)
            st.altair_chart(grafico_mixto, use_container_width=True)
        else:
            st.markdown(f"<h5 style='text-align: center;'><span style='color: {color_1};'>{eje_izq}</span></h5>", unsafe_allow_html=True)
            st.altair_chart(linea_1.interactive(), use_container_width=True)

    with st.expander("📄 Ver registros del periodo seleccionado"):
        columnas_a_mostrar = ["created_at"] + columnas_activas
        st.dataframe(df[columnas_a_mostrar].sort_values(by="created_at", ascending=False), use_container_width=True)
else:
    st.warning("No hay datos registrados para el periodo seleccionado.")