import streamlit as st
import pandas as pd
import json

st.set_page_config(page_title="Dashboard Ventas", layout="wide")
st.title("📊 Dashboard de Ventas - Botillería")

# --- Leer JSON de configuración ---
try:
    with open("report.json", "r", encoding="utf-8") as f:
        config = json.load(f)
except Exception as e:
    st.error(f"❌ Error al leer el archivo JSON: {e}")
    st.stop()

# --- Obtener URL del CSV ---
csv_url = config.get("dataSource", {}).get("filename", "")
if not csv_url:
    st.error("❌ No se encontró la URL del CSV en el JSON.")
    st.stop()

# --- Cargar CSV desde la URL ---
@st.cache_data
def cargar_datos(url):
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()  # Limpia nombres de columnas
        return df
    except Exception as e:
        st.error(f"❌ Error al cargar CSV: {e}")
        return pd.DataFrame()

df = cargar_datos(csv_url)

if df.empty:
    st.warning("⚠️ No se pudo cargar el archivo CSV o está vacío.")
    st.stop()

# --- Mostrar columnas disponibles en el sidebar ---
st.sidebar.markdown("### 🧾 Columnas disponibles:")
st.sidebar.write(df.columns.tolist())

# --- Mapear nombres de columnas esperadas (según el JSON) ---
nombres_esperados = {
    "Sucursal": None,
    "Producto / Servicio + Variante": None,
    "Mes": None
}

for col in df.columns:
    col_limpio = col.strip().lower()
    if col_limpio == "sucursal":
        nombres_esperados["Sucursal"] = col
    elif "producto" in col_limpio or "variante" in col_limpio:
        nombres_esperados["Producto / Servicio + Variante"] = col
    elif col_limpio == "mes":
        nombres_esperados["Mes"] = col

# --- Filtro: Expand por sucursal (si existe) ---
try:
    expands = config.get("slice", {}).get("expands", {}).get("rows", [])
    for item in expands:
        for value in item["tuple"]:
            sucursal = value.split(".[")[1].replace("]", "").strip().lower()
            col_sucursal = nombres_esperados["Sucursal"]
            if col_sucursal:
                df = df[df[col_sucursal].str.lower() == sucursal]
except Exception as e:
    st.warning(f"⚠️ No se pudo aplicar el filtro por sucursal: {e}")

# --- Agrupación ---
if all(nombres_esperados.values()):
    try:
        columnas = [
            nombres_esperados["Sucursal"],
            nombres_esperados["Producto / Servicio + Variante"],
            nombres_esperados["Mes"]
        ]

        medidas = {
            "Subtotal Neto": "sum",
            "Subtotal Bruto": "sum",
            "Margen Neto": "sum",
            "Costo Neto": "sum",
            "Impuestos": "sum",
            "Cantidad": "sum"
        }

        columnas_existentes = [col for col in medidas if col in df.columns]
        medidas_validas = {col: medidas[col] for col in columnas_existentes}

        agrupado = df.groupby(columnas).agg(medidas_validas).reset_index()

        st.markdown("### 📋 Tabla de Ventas Agrupadas")
        st.dataframe(agrupado, use_container_width=True)

        # --- Gráfico: Ventas por Mes ---
        if nombres_esperados["Mes"] and "Subtotal Neto" in agrupado.columns:
            st.markdown("### 📈 Subtotal Neto por Mes")
            chart = agrupado.groupby(nombres_esperados["Mes"])["Subtotal Neto"].sum().sort_index()
            st.bar_chart(chart)

    except Exception as e:
        st.error(f"❌ Error al agrupar datos: {e}")
else:
    st.warning("⚠️ No se encontraron todas las columnas necesarias para agrupar.")
    st.write("Columnas mapeadas:")
    st.json(nombres_esperados)
