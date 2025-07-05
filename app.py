import streamlit as st
import pandas as pd
import json

st.set_page_config(page_title="Dashboard Ventas", layout="wide")
st.title("📊 Dashboard de Ventas - Botillería")

# --- Leer JSON ---
try:
    with open("report.json", "r", encoding="utf-8") as f:
        config = json.load(f)
except Exception as e:
    st.error(f"❌ Error leyendo JSON: {e}")
    st.stop()

# --- URL CSV ---
csv_url = config.get("dataSource", {}).get("filename", "")
if not csv_url:
    st.error("❌ No se encontró URL CSV en JSON.")
    st.stop()

# --- Cargar CSV ---
@st.cache_data
def cargar_datos(url):
    try:
        df = pd.read_csv(url, sep=None, engine='python')  # auto detecta sep
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"❌ Error cargando CSV: {e}")
        return pd.DataFrame()

df = cargar_datos(csv_url)
if df.empty:
    st.warning("⚠️ CSV vacío o no cargado.")
    st.stop()

# --- Mostrar columnas en sidebar ---
st.sidebar.markdown("### 🧾 Columnas en CSV:")
st.sidebar.write(df.columns.tolist())

# --- Detectar columnas con + ---
nombres_esperados = {
    "Sucursal": "+Sucursal",
    "Producto / Servicio + Variante": "+Producto / Servicio + Variante",
    "Mes": "+Mes"
}

# --- Aplicar filtro sucursal (si existe en config y en df) ---
try:
    expands = config.get("slice", {}).get("expands", {}).get("rows", [])
    for item in expands:
        for value in item.get("tuple", []):
            sucursal_filtrar = value.split(".[")[1].replace("]", "").strip().lower()
            col_sucursal = nombres_esperados["Sucursal"]
            if col_sucursal in df.columns:
                df = df[df[col_sucursal].str.lower() == sucursal_filtrar]
except Exception as e:
    st.warning(f"⚠️ No se pudo filtrar sucursal: {e}")

# --- Medidas (sin +) que existen en df ---
medidas = ["Subtotal Neto", "Subtotal Bruto", "Margen Neto", "Costo Neto", "Impuestos", "Cantidad"]
medidas_validas = [m for m in medidas if m in df.columns]

# --- Columnas para agrupar ---
columnas_agrupacion = [col for col in nombres_esperados.values() if col in df.columns]

if not columnas_agrupacion:
    st.warning("⚠️ No hay columnas para agrupar.")
    st.stop()

if not medidas_validas:
    st.warning("⚠️ No hay medidas para agregar.")
    st.stop()

# --- Agrupar ---
try:
    agrupado = df.groupby(columnas_agrupacion)[medidas_validas].sum().reset_index()
except Exception as e:
    st.error(f"❌ Error agrupando datos: {e}")
    st.stop()

# --- Mostrar tabla ---
st.markdown("### 📋 Tabla agrupada de ventas")
st.dataframe(agrupado, use_container_width=True)

# --- Gráfico subtotal neto por mes ---
if "+Mes" in agrupado.columns and "Subtotal Neto" in agrupado.columns:
    st.markdown("### 📈 Subtotal Neto por Mes")
    chart = agrupado.groupby("+Mes")["Subtotal Neto"].sum().sort_index()
    st.bar_chart(chart)
else:
    st.info("ℹ️ No hay datos para gráfico de mes.")

