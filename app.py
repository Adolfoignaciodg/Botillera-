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
col_fecha = encontrar_col("fecha")

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

if not col_fecha:
    st.error("No se encontró columna 'Fecha' para detalle diario. Es necesaria.")
    st.stop()

# --- Conversión de medidas a float ---
for col in medidas:
    df[col] = pd.to_numeric(df[col], errors="coerce")

# Convertir columna fecha a datetime
df[col_fecha] = pd.to_datetime(df[col_fecha], errors='coerce')

# Extraer Año, Mes (numérico y nombre) y Día para filtros en nueva pestaña
df['Año'] = df[col_fecha].dt.year
df['MesNum'] = df[col_fecha].dt.month
df['MesNombre'] = df[col_fecha].dt.strftime('%B')
df['Día'] = df[col_fecha].dt.day

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
    seleccion_tipo_producto = st.sidebar.selectbox("Seleccionar Tipo Producto / Servicio", tipos_producto)
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

# --- Aplicar filtros ---
df_filtrado = df.copy()

if len(sucursales_disponibles) > 1 and seleccion_sucursal != "Todas":
    df_filtrado = df_filtrado[df_filtrado[col_sucursal] == seleccion_sucursal]

if seleccion_tipo_producto and seleccion_tipo_producto != "Todos":
    df_filtrado = df_filtrado[df_filtrado[col_tipo_producto] == seleccion_tipo_producto]

if seleccion_mes != "Todos":
    df_filtrado = df_filtrado[df_filtrado[col_mes] == seleccion_mes]

if seleccion_producto != "Todos":
    df_filtrado = df_filtrado[df_filtrado[col_producto] == seleccion_producto]

if df_filtrado.empty:
    st.warning("No hay datos para los filtros seleccionados.")
    st.stop()

# --- Función formato moneda ---
def formato_moneda(x):
    try:
        val = float(x)
        return f"${val:,.0f}".replace(",", ".")
    except Exception:
        return "$0"

# --- Pestañas ---
tab1, tab2, tab3 = st.tabs(["Resumen y Detalle", "Análisis ABC", "Detalle por Día y Categoría"])

with tab1:
    st.markdown("## 📌 Resumen General")
    resumen = {m: df_filtrado[m].sum() for m in medidas}
    cols_metrics = st.columns(len(medidas))
    for idx, m in enumerate(medidas):
        valor = resumen.get(m, 0)
        display_val = f"{int(valor):,}".replace(",", ".") if m == 'Cantidad' else formato_moneda(valor)
        cols_metrics[idx].metric(m, display_val)

    st.markdown(f"## 🛒 Cantidades Vendidas por Producto en categoría '{seleccion_tipo_producto or 'Todos'}' " +
                (f"y Mes '{seleccion_mes}'" if seleccion_mes != "Todos" else "(todo el tiempo)"))

    df_cantidades = df_filtrado.copy()
    if seleccion_producto != "Todos":
        df_cantidades = df_cantidades[df_cantidades[col_producto] == seleccion_producto]

    cantidades_por_producto = df_cantidades.groupby(col_producto)['Cantidad'].sum().reset_index().sort_values(by='Cantidad', ascending=False)
    st.dataframe(cantidades_por_producto, use_container_width=True)

    st.markdown(f"## 📅 Detalle Diario de Ventas " +
                (f"para producto '{seleccion_producto}'" if seleccion_producto != "Todos" else "para todos los productos"))

    if seleccion_producto == "Todos":
        detalle_diario = df_filtrado.groupby([col_producto, col_fecha])['Cantidad'].sum().reset_index()
        pivot_diario = detalle_diario.pivot(index=col_producto, columns=col_fecha, values='Cantidad').fillna(0)
        pivot_diario.columns = pivot_diario.columns.strftime('%d/%m/%Y')
        st.dataframe(pivot_diario.astype(int), use_container_width=True)

        prod_para_graf = st.selectbox("Seleccionar Producto para gráfico diario", ["Todos"] + sorted(detalle_diario[col_producto].unique()))
        if prod_para_graf != "Todos":
            df_graf = detalle_diario[detalle_diario[col_producto] == prod_para_graf]
            graf_diario = alt.Chart(df_graf).mark_line(point=True).encode(
                x=alt.X(col_fecha, title="Fecha", axis=alt.Axis(format='%d/%m/%Y')),
                y=alt.Y('Cantidad', title="Cantidad Vendida"),
                tooltip=[alt.Tooltip(col_fecha, title="Fecha", format='%d/%m/%Y'), alt.Tooltip('Cantidad')]
            ).properties(height=300)
            st.altair_chart(graf_diario, use_container_width=True)
    else:
        detalle_diario = df_filtrado.groupby(col_fecha)['Cantidad'].sum().reset_index().sort_values(col_fecha)
        st.dataframe(detalle_diario, use_container_width=True)

        graf_diario = alt.Chart(detalle_diario).mark_line(point=True).encode(
            x=alt.X(col_fecha, title="Fecha", axis=alt.Axis(format='%d/%m/%Y')),
            y=alt.Y('Cantidad', title="Cantidad Vendida"),
            tooltip=[alt.Tooltip(col_fecha, title="Fecha", format='%d/%m/%Y'), alt.Tooltip('Cantidad')]
        ).properties(height=300)
        st.altair_chart(graf_diario, use_container_width=True)

with tab2:
    st.markdown("## 🔍 Análisis ABC de Productos")

    # Elimino opción "Por Mes", solo "Total"
    df_abc = df_filtrado.copy()

    if df_abc.empty:
        st.warning("No hay datos para esta selección.")
    else:
        def calcular_abc(df_abc, valor_col='Subtotal Neto', grupo_col=col_producto):
            df_abc = df_abc.groupby(grupo_col)[valor_col].sum().reset_index()
            df_abc = df_abc.sort_values(by=valor_col, ascending=False)
            df_abc['Acumulado'] = df_abc[valor_col].cumsum()
            total = df_abc[valor_col].sum()
            df_abc['PorcAcum'] = df_abc['Acumulado'] / total
            bins = [0, 0.7, 0.9, 1]
            labels = ['A', 'B', 'C']
            df_abc['Categoria'] = pd.cut(df_abc['PorcAcum'], bins=bins, labels=labels, include_lowest=True)
            return df_abc

        df_abc_result = calcular_abc(df_abc)
        st.dataframe(df_abc_result[[col_producto, 'Subtotal Neto', 'PorcAcum', 'Categoria']].sort_values(by='Categoria'))

        graf_abc = alt.Chart(df_abc_result).mark_bar().encode(
            x=alt.X(col_producto, sort='-y'),
            y=alt.Y('Subtotal Neto', title='Subtotal Neto CLP'),
            color=alt.Color('Categoria', scale=alt.Scale(domain=['A', 'B', 'C'], range=['#1f77b4', '#ff7f0e', '#2ca02c'])),
            tooltip=[
                alt.Tooltip(col_producto, title='Producto'),
                alt.Tooltip('Subtotal Neto', format=",.0f"),
                alt.Tooltip('Categoria')
            ]
        ).properties(height=400)
        st.altair_chart(graf_abc, use_container_width=True)

with tab3:
    st.markdown("## 📋 Detalle de Ventas por Día y Categoría")

    años_disponibles = sorted(df['Año'].dropna().unique())
    año_seleccionado = st.selectbox("Seleccionar Año", años_disponibles)

    meses_disponibles = df[df['Año'] == año_seleccionado][['MesNum', 'MesNombre']].drop_duplicates().sort_values('MesNum')
    mes_seleccionado = st.selectbox("Seleccionar Mes", meses_disponibles['MesNombre'].tolist())

    dias_disponibles = df[(df['Año'] == año_seleccionado) & (df['MesNombre'] == mes_seleccionado)]['Día'].dropna().unique()
    dias_disponibles = sorted(dias_disponibles)
    dia_seleccionado = st.selectbox("Seleccionar Día", dias_disponibles)

    df_detalle_fecha = df[
        (df['Año'] == año_seleccionado) &
        (df['MesNombre'] == mes_seleccionado) &
        (df['Día'] == dia_seleccionado)
    ]

    if df_detalle_fecha.empty:
        st.warning("No hay datos para la fecha seleccionada.")
    else:
        # Ordenar por categoría (si existe) y producto
        ordenar_por = []
        if col_tipo_producto:
            ordenar_por.append(col_tipo_producto)
        ordenar_por.append(col_producto)

        df_detalle_fecha = df_detalle_fecha.sort_values(by=ordenar_por)

        categorias_unicas = df_detalle_fecha[col_tipo_producto].dropna().unique() if col_tipo_producto else ["Sin Categoría"]

        for cat in categorias_unicas:
            st.markdown(f"### 📂 Categoría: {cat}")
            if col_tipo_producto:
                df_cat = df_detalle_fecha[df_detalle_fecha[col_tipo_producto] == cat]
            else:
                df_cat = df_detalle_fecha

            cols_mostrar = [col_producto, 'Cantidad', 'Subtotal Neto']
            cols_mostrar = [c for c in cols_mostrar if c in df_cat.columns]
            st.dataframe(df_cat[cols_mostrar], use_container_width=True)

