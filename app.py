import streamlit as st
import pandas as pd
import json

st.set_page_config(page_title="Dashboard Ventas", layout="wide")

st.title("📊 Dashboard de Ventas - Botillería")

# --- Leer configuración JSON ---
try:
    with open("report.json", "r", encoding="utf-8") as f:
        config = json.load(f)
except Exception as e:
    st.error(f"Error al leer el archivo JSON: {e}")
    st.stop()

# --- Obtener URL del CSV ---
csv_url = config.get("dataSource", {}).get("filename", "")
if not csv_url:
    st.error("No se encontró la URL del archivo CSV en el JSON.")
    st.stop()

# --- Cargar datos desde CSV remoto ---
@st.cache_data
def cargar_datos(url):
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()  # Eliminar espacios en los nombres de columnas
        return df
    except Exception as e:
        st.error(f"Error al cargar CSV: {e}")
        return pd.DataFrame()

df = cargar_datos(csv_url)

if df.empty:
    st.warning("No se pudo cargar el archivo CSV o está vacío.")
    st.stop()

# --- Mostrar columnas disponibles por si hay problemas ---
st.sidebar.markdown("### Columnas disponibles:")
st.sidebar.write(df.columns.tolist())

# --- Filtrar por sucursal si config lo indica ---
try:
    expands = config["slice"]["expands"]["rows"]
    for item in expands:
        for value in item["tuple"]:
            sucursal = value.split(".[")[1].replace("]", "").strip().lower()
            col_match = [col for col in df.columns if col.strip().lower() == "sucursal"]
            if col_match:
                col_name = col_match[0]
                df = df[df[col_name].str.lower() == sucursal]
            else:
                st.warning("No se encontró la columna 'Sucursal'.")
except Exception as e:
    st.warning(f"No se pudo aplicar el filtro de sucursal: {e}")

# --- Agrupación de datos ---
agrupado = df.copy()

try:
    agrupado = df.groupby(
        ["Sucursal", "Producto / Servicio + Variante", "Mes"]
    ).agg({
        "Subtotal Neto": "sum",
        "Subtotal Bruto": "sum",
        "Margen Neto": "sum",
        "Costo Neto": "sum",
        "Impuestos": "sum",
        "Cantidad": "sum"
    }).reset_index()
except Exception as e:
    st.warning(f"No se pudo agrupar la información correctamente: {e}")

# --- Mostrar resultado ---
st.markdown("### 📋 Tabla de Ventas Agrupadas")
st.dataframe(agrupado, use_container_width=True)

# --- Gráfico opcional por mes ---
if "Mes" in agrupado.columns and "Subtotal Neto" in agrupado.columns:
    st.markdown("### 📈 Ventas por Mes (Subtotal Neto)")
    chart_data = agrupado.groupby("Mes")["Subtotal Neto"].sum().sort_index()
    st.bar_chart(chart_data)

