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

# --- Conversión de medidas a float ---
for col in medidas:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

# --- Detectar sucursales únicas para lógica de filtros ---
sucursales_disponibles = sorted(df[col_sucursal].dropna().unique().tolist())

# --- Sidebar filtros ---
st.sidebar.header("Filtros")

if len(sucursales_disponibles) == 1:
    seleccion_sucursal = sucursales_disponibles[0]
    st.sidebar.markdown(f"**Sucursal:** {seleccion_sucursal}")
else:
    sucursales = ["Todas"] + sucursales_disponibles
    seleccion_sucursal = st.sidebar.selectbox("Seleccionar Sucursal", sucursales)

# Filtro tipo producto
if col_tipo_producto:
    tipos_producto = ["Todos"] + sorted(df[col_tipo_producto].dropna().unique().tolist())
    seleccion_tipo_producto = st.sidebar.selectbox("Seleccionar Tipo de Producto / Servicio", tipos_producto)
else:
    seleccion_tipo_producto = None

# Filtro productos dependiente de tipo
df_para_productos = df.copy()
if seleccion_tipo_producto and seleccion_tipo_producto != "Todos" and col_tipo_producto:
    df_para_productos = df_para_productos[df_para_productos[col_tipo_producto] == seleccion_tipo_producto]

productos = ["Todos"] + sorted(df_para_productos[col_producto].dropna().unique().tolist())
seleccion_producto = st.sidebar.selectbox("Seleccionar Producto", productos)

# Filtro mes
meses = ["Todos"] + sorted(df[col_mes].dropna().unique().tolist())
seleccion_mes = st.sidebar.selectbox("Seleccionar Mes", meses)

# --- Aplicar filtros ---
df_filtrado = df.copy()

if len(sucursales_disponibles) > 1 and seleccion_sucursal != "Todas":
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

# --- Función formato moneda robusta ---
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

# --- Gráficos con Altair ---

st.markdown("## 📈 Subtotal Neto por Mes")
graf1 = alt.Chart(df_filtrado).mark_bar().encode(
    x=alt.X(col_mes, sort="ascending"),
    y=alt.Y("sum(Subtotal Neto)", title="Subtotal Neto"),
    tooltip=[
        alt.Tooltip("sum(Subtotal Neto)", title="Subtotal CLP", format=",.0f"),
        alt.Tooltip("sum(Margen Neto)", title="Margen CLP", format=",.0f"),
        alt.Tooltip("sum(Cantidad)", title="Cantidad", format=",.0f")
    ]
).properties(height=400)
st.altair_chart(graf1, use_container_width=True)

st.markdown("## 📉 Margen Neto por Mes")
graf2 = alt.Chart(df_filtrado).mark_line(point=True).encode(
    x=alt.X(col_mes, sort="ascending"),
    y=alt.Y("sum(Margen Neto)", title="Margen Neto"),
    tooltip=[
        alt.Tooltip("sum(Margen Neto)", format=",.0f"),
        alt.Tooltip("sum(Subtotal Neto)", format=",.0f")
    ]
).properties(height=400)
st.altair_chart(graf2, use_container_width=True)

if len(sucursales_disponibles) > 1:
    st.markdown("## 🏪 Ventas por Sucursal")
    ventas_suc = df_filtrado.groupby(col_sucursal)["Subtotal Neto"].sum().sort_values(ascending=False).reset_index()
    graf3 = alt.Chart(ventas_suc).mark_bar().encode(
        x=alt.X("Subtotal Neto:Q", title="Subtotal CLP"),
        y=alt.Y(f"{col_sucursal}:N", sort="-x"),
        tooltip=[alt.Tooltip("Subtotal Neto", format=",.0f")]
    ).properties(height=400)
    st.altair_chart(graf3, use_container_width=True)

st.markdown("## 🛒 Top 10 Productos por Subtotal Neto")
top_prod = df_filtrado.groupby(col_producto)["Subtotal Neto"].sum().sort_values(ascending=False).head(10).reset_index()
graf4 = alt.Chart(top_prod).mark_bar().encode(
    x=alt.X("Subtotal Neto:Q", title="Subtotal CLP"),
    y=alt.Y(f"{col_producto}:N", sort="-x"),
    tooltip=[alt.Tooltip("Subtotal Neto", format=",.0f")]
).properties(height=400)
st.altair_chart(graf4, use_container_width=True)

if col_tipo_producto:
    st.markdown(f"## 📊 Subtotal por Tipo de Producto / Servicio ({seleccion_tipo_producto or 'Todos'})")
    ventas_tipo = df_filtrado.groupby(col_tipo_producto)["Subtotal Neto"].sum().sort_values(ascending=False).reset_index()
    graf5 = alt.Chart(ventas_tipo).mark_bar().encode(
        x=alt.X("Subtotal Neto:Q", title="Subtotal CLP"),
        y=alt.Y(f"{col_tipo_producto}:N", sort="-x"),
        tooltip=[alt.Tooltip("Subtotal Neto", format=",.0f")]
    ).properties(height=400)
    st.altair_chart(graf5, use_container_width=True)

# --- Tabla final ---
st.markdown("## 📋 Detalle de Ventas")
st.dataframe(df_filtrado.sort_values(by="Subtotal Neto", ascending=False), use_container_width=True)

