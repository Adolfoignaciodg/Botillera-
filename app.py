import streamlit as st
import pandas as pd
import json
import altair as alt

# Configuración de la página
st.set_page_config(page_title="Dashboard Botillería", layout="wide")
st.title("📊 Dashboard de Ventas - Visión Propietario")

# --- Carga y validación del archivo JSON de configuración ---
@st.cache_data
def cargar_config(path="report.json"):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Error leyendo JSON: {e}")
        return None

config = cargar_config()
if not config:
    st.stop()

# --- Obtener URL CSV desde JSON ---
csv_url = config.get("dataSource", {}).get("filename", "")
if not csv_url:
    st.error("No se encontró URL CSV en JSON.")
    st.stop()

# --- Función para cargar datos CSV con cache ---
@st.cache_data(show_spinner=False)
def cargar_datos(url):
    try:
        # Intentar inferir separador con engine='python' y sep=None
        df = pd.read_csv(url, sep=None, engine='python')
        df.columns = df.columns.str.strip()  # Limpiar espacios en nombres columnas
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

def encontrar_col(busqueda, columnas=cols):
    busqueda = busqueda.lower()
    for c in columnas:
        if busqueda in c.lower():
            return c
    return None

col_sucursal = encontrar_col("sucursal")
col_producto = encontrar_col("producto / servicio + variante")
col_mes = encontrar_col("mes")
col_tipo_producto = encontrar_col("tipo de producto / servicio")

medidas_esperadas = ["Subtotal Neto", "Subtotal Bruto", "Margen Neto", "Costo Neto", "Impuestos", "Cantidad"]
medidas = [m for m in medidas_esperadas if m in cols]

# Validaciones básicas
if not all([col_sucursal, col_producto, col_mes]):
    st.error("No se encontraron columnas clave para sucursal, producto o mes en el CSV.")
    st.write("Columnas encontradas:", cols)
    st.stop()

if not medidas:
    st.error("No se encontraron columnas de medidas importantes en el CSV.")
    st.stop()

# --- Conversión de medidas a float ---
for col in medidas:
    df[col] = pd.to_numeric(df[col], errors="coerce")

# --- Crear columna Temporada ---
def mes_a_temporada(mes):
    mes = str(mes).lower()
    if mes in ['diciembre', 'enero', 'febrero']:
        return 'Verano'
    elif mes in ['marzo', 'abril', 'mayo']:
        return 'Otoño'
    elif mes in ['junio', 'julio', 'agosto']:
        return 'Invierno'
    elif mes in ['septiembre', 'octubre', 'noviembre']:
        return 'Primavera'
    else:
        return 'Desconocida'

df['Temporada'] = df[col_mes].apply(mes_a_temporada)

# --- Detectar sucursales únicas para filtros ---
sucursales_disponibles = sorted(df[col_sucursal].dropna().unique())

# --- Sidebar: filtros ---
st.sidebar.header("Filtros")

if len(sucursales_disponibles) == 1:
    seleccion_sucursal = sucursales_disponibles[0]
    st.sidebar.markdown(f"**Sucursal:** {seleccion_sucursal}")
else:
    opciones_suc = ["Todas"] + sucursales_disponibles
    seleccion_sucursal = st.sidebar.selectbox("Seleccionar Sucursal", opciones_suc)

# Tipo de producto (si existe)
if col_tipo_producto:
    tipos_producto = ["Todos"] + sorted(df[col_tipo_producto].dropna().unique())
    seleccion_tipo_producto = st.sidebar.selectbox("Seleccionar Tipo de Producto / Servicio", tipos_producto)
else:
    seleccion_tipo_producto = None

# Productos filtrados por tipo
df_productos = df.copy()
if seleccion_tipo_producto and seleccion_tipo_producto != "Todos" and col_tipo_producto:
    df_productos = df_productos[df_productos[col_tipo_producto] == seleccion_tipo_producto]

productos = ["Todos"] + sorted(df_productos[col_producto].dropna().unique())
seleccion_producto = st.sidebar.selectbox("Seleccionar Producto", productos)

# Mes
meses = ["Todos"] + sorted(df[col_mes].dropna().unique())
seleccion_mes = st.sidebar.selectbox("Seleccionar Mes", meses)

# Temporada
temporadas = ["Todas", "Verano", "Otoño", "Invierno", "Primavera"]
seleccion_temporada = st.sidebar.selectbox("Seleccionar Temporada", temporadas)

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

if seleccion_temporada != "Todas":
    df_filtrado = df_filtrado[df_filtrado['Temporada'] == seleccion_temporada]

if df_filtrado.empty:
    st.warning("No hay datos para los filtros seleccionados.")
    st.stop()

# --- Funciones auxiliares ---
def formato_moneda(x):
    try:
        val = float(x)
        # Reemplaza coma decimal por punto para formato chileno, separador miles punto
        return f"${val:,.0f}".replace(",", ".")
    except Exception:
        return "$0"

def calcular_abc(df_abc, valor_col='Subtotal Neto', grupo_col=col_producto):
    df_abc = df_abc.groupby(grupo_col)[valor_col].sum().reset_index()
    df_abc = df_abc.sort_values(by=valor_col, ascending=False)
    df_abc['Acumulado'] = df_abc[valor_col].cumsum()
    total = df_abc[valor_col].sum()
    df_abc['PorcAcum'] = df_abc['Acumulado'] / total
    # Categorizar ABC según % acumulado
    bins = [0, 0.7, 0.9, 1]
    labels = ['A', 'B', 'C']
    df_abc['Categoria'] = pd.cut(df_abc['PorcAcum'], bins=bins, labels=labels, include_lowest=True)
    return df_abc

# --- Pestañas ---
tab1, tab2, tab3 = st.tabs(["Resumen y Gráficos", "Análisis ABC", "Análisis por Temporada"])

with tab1:
    st.markdown("## 📌 Resumen General")
    resumen = {m: df_filtrado[m].sum() for m in medidas}
    cols_metrics = st.columns(len(medidas))
    for idx, m in enumerate(medidas):
        valor = resumen.get(m, 0)
        if m == 'Cantidad':
            display_val = f"{int(valor):,}".replace(",", ".")
        else:
            display_val = formato_moneda(valor)
        cols_metrics[idx].metric(m, display_val)

    # Gráfico Subtotal Neto por Mes
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

    # Gráfico Margen Neto por Mes
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

    # Ventas por sucursal (si hay más de una)
    if len(sucursales_disponibles) > 1:
        st.markdown("## 🏪 Ventas por Sucursal")
        ventas_suc = df_filtrado.groupby(col_sucursal)["Subtotal Neto"].sum().sort_values(ascending=False).reset_index()
        graf3 = alt.Chart(ventas_suc).mark_bar().encode(
            x=alt.X("Subtotal Neto:Q", title="Subtotal CLP"),
            y=alt.Y(f"{col_sucursal}:N", sort="-x"),
            tooltip=[alt.Tooltip("Subtotal Neto", format=",.0f")]
        ).properties(height=400)
        st.altair_chart(graf3, use_container_width=True)

    # Top 10 productos
    st.markdown("## 🛒 Top 10 Productos por Subtotal Neto")
    top_prod = df_filtrado.groupby(col_producto)["Subtotal Neto"].sum().sort_values(ascending=False).head(10).reset_index()
    graf4 = alt.Chart(top_prod).mark_bar().encode(
        x=alt.X("Subtotal Neto:Q", title="Subtotal CLP"),
        y=alt.Y(f"{col_producto}:N", sort="-x"),
        tooltip=[alt.Tooltip("Subtotal Neto", format=",.0f")]
    ).properties(height=400)
    st.altair_chart(graf4, use_container_width=True)

    # Ventas por tipo de producto (si existe)
    if col_tipo_producto:
        st.markdown(f"## 📊 Subtotal por Tipo de Producto / Servicio ({seleccion_tipo_producto or 'Todos'})")
        ventas_tipo = df_filtrado.groupby(col_tipo_producto)["Subtotal Neto"].sum().sort_values(ascending=False).reset_index()
        graf5 = alt.Chart(ventas_tipo).mark_bar().encode(
            x=alt.X("Subtotal Neto:Q", title="Subtotal CLP"),
            y=alt.Y(f"{col_tipo_producto}:N", sort="-x"),
            tooltip=[alt.Tooltip("Subtotal Neto", format=",.0f")]
        ).properties(height=400)
        st.altair_chart(graf5, use_container_width=True)

    # Tabla detalle ventas
    st.markdown("## 📋 Detalle de Ventas")
    st.dataframe(df_filtrado.sort_values(by="Subtotal Neto", ascending=False), use_container_width=True)

with tab2:
    st.markdown("## 🔍 Análisis ABC de Productos")

    opcion_abc = st.radio("Ver análisis ABC por:", ("Total", "Por Mes"))

    if opcion_abc == "Total":
        df_abc = df_filtrado.copy()
    else:
        mes_abc = st.selectbox("Seleccionar Mes para ABC", meses[1:])  # excluir "Todos"
        df_abc = df_filtrado[df_filtrado[col_mes] == mes_abc]

    if df_abc.empty:
        st.warning("No hay datos para esta selección.")
    else:
        df_abc_result = calcular_abc(df_abc)
        # Mostrar tabla ordenada por categoría ABC
        st.dataframe(df_abc_result[[col_producto, 'Subtotal Neto', 'PorcAcum', 'Categoria']].sort_values(by='Categoria'))

        # Gráfico ABC
        graf_abc = alt.Chart(df_abc_result).mark_bar().encode(
            x=alt.X(col_producto, sort='-y'),
            y=alt.Y('Subtotal Neto', title='Subtotal Neto CLP'),
            color=alt.Color('Categoria', scale=alt.Scale(domain=['A', 'B', 'C'],
                                                        range=['#1f77b4', '#ff7f0e', '#2ca02c'])),
            tooltip=[
                alt.Tooltip(col_producto, title='Producto'),
                alt.Tooltip('Subtotal Neto', format=",.0f"),
                alt.Tooltip('Categoria')
            ]
        ).properties(height=400)
        st.altair_chart(graf_abc, use_container_width=True)

with tab3:
    st.markdown("## 🍂 Análisis por Temporada")

    if seleccion_temporada == "Todas":
        st.info("Selecciona una temporada en el filtro lateral para ver datos por temporada.")
    else:
        resumen_temp = df_filtrado[df_filtrado['Temporada'] == seleccion_temporada][medidas].sum()
        st.write(f"### Resumen Temporada: {seleccion_temporada}")
        for m in medidas:
            valor = resumen_temp[m]
            display_val = formato_moneda(valor) if m != 'Cantidad' else f"{int(valor):,}".replace(",", ".")
            st.metric(m, display_val)

        # Top productos temporada
        ventas_temp_prod = df_filtrado[df_filtrado['Temporada'] == seleccion_temporada].groupby(col_producto)['Subtotal Neto'].sum().sort_values(ascending=False).reset_index()
        st.markdown("#### Top Productos en Temporada")
        graf_temp_prod = alt.Chart(ventas_temp_prod.head(10)).mark_bar().encode(
            x=alt.X('Subtotal Neto:Q', title="Subtotal Neto CLP"),
            y=alt.Y(f"{col_producto}:N", sort='-x'),
            tooltip=[alt.Tooltip('Subtotal Neto', format=",.0f")]
        ).properties(height=400)
        st.altair_chart(graf_temp_prod, use_container_width=True)

