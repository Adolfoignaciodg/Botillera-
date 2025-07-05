import streamlit as st
import pandas as pd
import json
import altair as alt

st.set_page_config(page_title="Dashboard Botillería", layout="wide")
st.title("📊 Dashboard de Ventas - Visión Propietario")

# --- Leer JSON config ---
try:
    with open("report.json", "r", encoding="utf-8") as f:
        config = json.load(f)
except Exception as e:
    st.error(f"Error leyendo JSON: {e}")
    st.stop()

# --- Obtener URL CSV ---
csv_url = config.get("dataSource", {}).get("filename", "")
if not csv_url:
    st.error("No se encontró URL CSV en JSON.")
    st.stop()

# --- Cargar datos CSV ---
@st.cache_data
def cargar_datos(url):
    try:
        df = pd.read_csv(url, sep=None, engine='python')
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"Error cargando CSV: {e}")
        return pd.DataFrame()

df = cargar_datos(csv_url)
if df.empty:
    st.warning("Archivo CSV vacío o no cargado.")
    st.stop()

# --- Detectar columnas clave ---
cols = df.columns.tolist()
def encontrar_col(busqueda):
    busqueda = busqueda.lower()
    for c in cols:
        if busqueda in c.lower():
            return c
    return None

col_sucursal = encontrar_col("sucursal")
col_producto = encontrar_col("producto / servicio + variante")
col_mes = encontrar_col("mes")
col_tipo_producto = encontrar_col("tipo de producto / servicio")

medidas_esperadas = ["Subtotal Neto", "Subtotal Bruto", "Margen Neto", "Costo Neto", "Impuestos", "Cantidad"]
medidas = [m for m in medidas_esperadas if m in cols]

if not col_sucursal or not col_producto or not col_mes:
    st.error("No se encontraron columnas clave para sucursal, producto o mes en el CSV.")
    st.write("Columnas encontradas:", cols)
    st.stop()

if not medidas:
    st.error("No se encontraron columnas de medidas importantes en el CSV.")
    st.stop()

# --- Convertir medidas a float ---
for col in medidas:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

# --- Sidebar filtros ---
sucursales_disponibles = sorted(df[col_sucursal].dropna().unique().tolist())
st.sidebar.header("Filtros")

if len(sucursales_disponibles) == 1:
    seleccion_sucursal = sucursales_disponibles[0]
    st.sidebar.markdown(f"**Sucursal:** {seleccion_sucursal}")
else:
    sucursales = ["Todas"] + sucursales_disponibles
    seleccion_sucursal = st.sidebar.selectbox("Seleccionar Sucursal", sucursales)

if col_tipo_producto:
    tipos_producto = ["Todos"] + sorted(df[col_tipo_producto].dropna().unique().tolist())
    seleccion_tipo_producto = st.sidebar.selectbox("Tipo de Producto / Servicio", tipos_producto)
else:
    seleccion_tipo_producto = None

df_para_productos = df.copy()
if seleccion_tipo_producto and seleccion_tipo_producto != "Todos":
    df_para_productos = df_para_productos[df_para_productos[col_tipo_producto] == seleccion_tipo_producto]

productos = ["Todos"] + sorted(df_para_productos[col_producto].dropna().unique().tolist())
seleccion_producto = st.sidebar.selectbox("Producto", productos)

meses = ["Todos"] + sorted(df[col_mes].dropna().unique().tolist())
seleccion_mes = st.sidebar.selectbox("Mes", meses)

# --- Aplicar filtros ---
df_filtrado = df.copy()
if seleccion_sucursal != "Todas":
    df_filtrado = df_filtrado[df_filtrado[col_sucursal] == seleccion_sucursal]

if seleccion_tipo_producto and seleccion_tipo_producto != "Todos":
    df_filtrado = df_filtrado[df_filtrado[col_tipo_producto] == seleccion_tipo_producto]

if seleccion_producto != "Todos":
    df_filtrado = df_filtrado[df_filtrado[col_producto] == seleccion_producto]

if seleccion_mes != "Todos":
    df_filtrado = df_filtrado[df_filtrado[col_mes] == seleccion_mes]

if df_filtrado.empty:
    st.warning("No hay datos para los filtros seleccionados.")
    st.stop()

# --- Función formato CLP ---
def formato_moneda(x):
    try:
        val = float(x)
        return f"${val:,.0f}".replace(",", ".")
    except:
        return "$0"

# --- Resumen General ---
st.markdown("## 📌 Resumen General")
resumen = {m: df_filtrado[m].sum() for m in medidas}

col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("Subtotal Neto", formato_moneda(resumen.get("Subtotal Neto", 0)))
col2.metric("Subtotal Bruto", formato_moneda(resumen.get("Subtotal Bruto", 0)))
col3.metric("Margen Neto", formato_moneda(resumen.get("Margen Neto", 0)))
col4.metric("Costo Neto", formato_moneda(resumen.get("Costo Neto", 0)))
col5.metric("Impuestos", formato_moneda(resumen.get("Impuestos", 0)))
col6.metric("Cantidad Vendida", f"{int(resumen.get('Cantidad', 0)):,}".replace(",", "."))

# --- Gráficos con ALTair y tooltips ---
st.markdown("## 📈 Análisis por Mes")

df_grafico = df_filtrado.groupby(col_mes).agg({
    "Subtotal Neto": "sum",
    "Margen Neto": "sum",
    "Cantidad": "sum"
}).reset_index()

# Formato CLP para tooltip
df_grafico["Subtotal Neto CLP"] = df_grafico["Subtotal Neto"].apply(formato_moneda)
df_grafico["Margen Neto CLP"] = df_grafico["Margen Neto"].apply(formato_moneda)

# --- Gráfico Altair con tooltips ---
bar = alt.Chart(df_grafico).mark_bar().encode(
    x=alt.X(f"{col_mes}:O", title="Mes"),
    y=alt.Y("Subtotal Neto:Q", title="Subtotal Neto (CLP)"),
    tooltip=[
        alt.Tooltip(f"{col_mes}:O", title="Mes"),
        alt.Tooltip("Subtotal Neto CLP:N", title="Subtotal Neto"),
        alt.Tooltip("Margen Neto CLP:N", title="Margen Neto"),
        alt.Tooltip("Cantidad:Q", title="Cantidad Vendida")
    ]
).properties(
    width=700,
    height=400,
    title="🟦 Subtotal Neto por Mes"
)

st.altair_chart(bar, use_container_width=True)

# --- Tabla de detalle ---
st.markdown("## 📋 Detalle de Ventas")
st.dataframe(df_filtrado.sort_values(by="Subtotal Neto", ascending=False), use_container_width=True)
