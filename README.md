# Dashboard de Ventas - Botillería

## Descripción

Este proyecto es un dashboard interactivo desarrollado en **Streamlit** para analizar datos de ventas desde un archivo CSV, compararlos con un catálogo de productos en Excel, y obtener insights útiles para la gestión comercial.  
Incluye filtros, gráficos y reportes que ayudan a identificar productos vendidos, analizar categorías, y detectar inconsistencias.

---

## Código principal con explicación paso a paso

```python
import streamlit as st
import pandas as pd
import json
import altair as alt

# --------------------------------------------
# Configuración inicial de la página
# --------------------------------------------
st.set_page_config(page_title="Dashboard Botillería", layout="wide")
st.title("📊 Dashboard de Ventas - Visión Propietario")

# --------------------------------------------
# Función para cargar archivo JSON de configuración
# Usamos cache para no recargar innecesariamente
# --------------------------------------------
@st.cache_data
def cargar_config(path="report.json"):
    try:
        with open(path, "r", encoding="utf-8") as f:
            # Carga el archivo JSON que contiene las URLs o rutas
            return json.load(f)
    except Exception as e:
        st.error(f"Error leyendo JSON: {e}")
        return None

config = cargar_config()
if not config:
    st.stop()  # Detenemos si no carga la configuración

# --------------------------------------------
# Extraemos URL para CSV de ventas desde el JSON
# Validamos que exista
# --------------------------------------------
csv_url = config.get("dataSource", {}).get("filename", "")
if not csv_url:
    st.error("No se encontró URL CSV en JSON.")
    st.stop()

# --------------------------------------------
# Extraemos URL para catálogo de productos (Excel)
# No es obligatorio, pero algunas pestañas usan esto
# --------------------------------------------
catalogo_url = config.get("catalogoProductos", {}).get("url", "")
if not catalogo_url:
    st.warning("No se encontró URL del catálogo en JSON, la pestaña de productos repetidos no funcionará.")

# --------------------------------------------
# Función para cargar CSV con cache para mejor rendimiento
# --------------------------------------------
@st.cache_data(show_spinner=False)
def cargar_datos_csv(url):
    try:
        # Carga el CSV desde URL o ruta local
        df = pd.read_csv(url, sep=None, engine='python')
        # Limpia espacios en nombres de columnas
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"Error cargando CSV: {e}")
        return pd.DataFrame()

df = cargar_datos_csv(csv_url)
if df.empty:
    st.warning("Archivo CSV vacío o no cargado.")
    st.stop()

# --------------------------------------------
# Función para cargar catálogo Excel (si existe)
# --------------------------------------------
@st.cache_data(show_spinner=False)
def cargar_catalogo_excel(url):
    try:
        df_cat = pd.read_excel(url)
        df_cat.columns = df_cat.columns.str.strip()
        return df_cat
    except Exception as e:
        st.error(f"Error cargando catálogo Excel: {e}")
        return pd.DataFrame()

df_catalogo = pd.DataFrame()
if catalogo_url:
    df_catalogo = cargar_catalogo_excel(catalogo_url)

# --------------------------------------------
# Detectar columnas clave en el CSV automáticamente
# Esto hace el código más flexible y robusto
# --------------------------------------------
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

# Columnas de medidas que esperamos encontrar
medidas_esperadas = ["Subtotal Neto", "Subtotal Bruto", "Margen Neto", "Costo Neto", "Impuestos", "Cantidad"]
medidas = [m for m in medidas_esperadas if m in cols]

# Validaciones básicas para asegurarnos que datos mínimos existan
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

# --------------------------------------------
# Convertir columnas numéricas a tipo float para evitar errores
# --------------------------------------------
for col in medidas:
    df[col] = pd.to_numeric(df[col], errors="coerce")

# Convertir columna fecha a datetime para manipulación y filtros
df[col_fecha] = pd.to_datetime(df[col_fecha], errors='coerce')

# Extraemos Año, Mes numérico y nombre, y Día para filtros en pestañas
df['Año'] = df[col_fecha].dt.year
df['MesNum'] = df[col_fecha].dt.month
df['MesNombre'] = df[col_fecha].dt.strftime('%B')
df['Día'] = df[col_fecha].dt.day

# --------------------------------------------
# Detectamos las sucursales únicas para mostrar filtro
# --------------------------------------------
sucursales_disponibles = sorted(df[col_sucursal].dropna().unique())

# --------------------------------------------
# Sidebar: filtros para que usuario pueda elegir qué ver
# --------------------------------------------
st.sidebar.header("Filtros")

if len(sucursales_disponibles) == 1:
    # Si solo hay una sucursal, se muestra fija
    seleccion_sucursal = sucursales_disponibles[0]
    st.sidebar.markdown(f"**Sucursal:** {seleccion_sucursal}")
else:
    opciones_suc = ["Todas"] + sucursales_disponibles
    seleccion_sucursal = st.sidebar.selectbox("Seleccionar Sucursal", opciones_suc)

# Filtro tipo de producto, si existe la columna
if col_tipo_producto:
    tipos_producto = ["Todos"] + sorted(df[col_tipo_producto].dropna().unique())
    seleccion_tipo_producto = st.sidebar.selectbox("Seleccionar Tipo Producto / Servicio", tipos_producto)
else:
    seleccion_tipo_producto = None

# Productos filtrados según tipo seleccionado para mejorar selección
df_productos = df.copy()
if seleccion_tipo_producto and seleccion_tipo_producto != "Todos" and col_tipo_producto:
    df_productos = df_productos[df_productos[col_tipo_producto] == seleccion_tipo_producto]

productos = ["Todos"] + sorted(df_productos[col_producto].dropna().unique())
seleccion_producto = st.sidebar.selectbox("Seleccionar Producto", productos)

# Filtro de mes
meses = ["Todos"] + sorted(df[col_mes].dropna().unique())
seleccion_mes = st.sidebar.selectbox("Seleccionar Mes", meses)

# --------------------------------------------
# Aplicar filtros seleccionados sobre el dataframe
# --------------------------------------------
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

# --------------------------------------------
# Función para formatear números como moneda chilena
# --------------------------------------------
def formato_moneda(x):
    try:
        val = float(x)
        return f"${val:,.0f}".replace(",", ".")
    except Exception:
        return "$0"

# --------------------------------------------
# Creación de pestañas para organización visual
# --------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "Resumen y Detalle",
    "Análisis ABC",
    "Detalle por Día y Categoría",
    "🧾 Productos Repetidos / No Registrados"
])

# ---------------------------
# PESTAÑA 1: Resumen y detalle general
# ---------------------------
with tab1:
    st.markdown("## 📌 Resumen General")

    # Sumariza las medidas importantes (subtotal, margen, cantidad, etc)
    resumen = {m: df_filtrado[m].sum() for m in medidas}

    # Mostrar métricas en columnas horizontales
    cols_metrics = st.columns(len(medidas))
    for idx, m in enumerate(medidas):
        valor = resumen.get(m, 0)
        # Cantidad sin decimales y moneda con formato chileno
        display_val = f"{int(valor):,}".replace(",", ".") if m == 'Cantidad' else formato_moneda(valor)
        cols_metrics[idx].metric(m, display_val)

    # Mostrar cantidad vendida por producto en la categoría y mes filtrados
    st.markdown(f"## 🛒 Cantidades Vendidas por Producto en categoría '{seleccion_tipo_producto or 'Todos'}' " +
                (f"y Mes '{seleccion_mes}'" if seleccion_mes != "Todos" else "(todo el tiempo)"))

    df_cantidades = df_filtrado.copy()
    if seleccion_producto != "Todos":
        df_cantidades = df_cantidades[df_cantidades[col_producto] == seleccion_producto]

    cantidades_por_producto = df_cantidades.groupby(col_producto)['Cantidad'].sum().reset_index().sort_values(by='Cantidad', ascending=False)
    st.dataframe(cantidades_por_producto, use_container_width=True)

    # Detalle diario de ventas para producto seleccionado o todos
    st.markdown(f"## 📅 Detalle Diario de Ventas " +
                (f"para producto '{seleccion_producto}'" if seleccion_producto != "Todos" else "para todos los productos"))

    if seleccion_producto == "Todos":
        # Pivot table para mostrar cantidad diaria por producto
        detalle_diario = df_filtrado.groupby([col_producto, col_fecha])['Cantidad'].sum().reset_index()
        pivot_diario = detalle_diario.pivot(index=col_producto, columns=col_fecha, values='Cantidad').fillna(0)
        pivot_diario.columns = pivot_diario.columns.strftime('%d/%m/%Y')
        st.dataframe(pivot_diario.astype(int), use_container_width=True)

        # Gráfico línea diario para producto seleccionado en dropdown
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
        # Detalle diario para producto único
        detalle_diario = df_filtrado.groupby(col_fecha)['Cantidad'].sum().reset_index().sort_values(col_fecha)
        st.dataframe(detalle_diario, use_container_width=True)

        graf_diario = alt.Chart(detalle_diario).mark_line(point=True).encode(
            x=alt.X(col_fecha, title="Fecha", axis=alt.Axis(format='%d/%m/%Y')),
            y=alt.Y('Cantidad', title="Cantidad Vendida"),
            tooltip=[alt.Tooltip(col_fecha, title="Fecha", format='%d/%m/%Y'), alt.Tooltip('Cantidad')]
        ).properties(height=300)
        st.altair_chart(graf_diario, use_container_width=True)

# ---------------------------
# PESTAÑA 2: Análisis ABC
# ---------------------------
with tab2:
    st.markdown("## 🔍 Análisis ABC de Productos")

    df_abc = df_filtrado.copy()

    if df_abc.empty:
        st.warning("No hay datos para esta selección.")
    else:
        # Función para clasificar productos en A, B, C según % de ventas acumuladas
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

        # Gráfico de barras con colores por categoría ABC
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

# ---------------------------
# PESTAÑA 3: Detalle diario por categoría
# ---------------------------
with tab3:
    st.markdown("## 📋 Detalle de Ventas por Día y Categoría")

    # Selección año
    años_disponibles = sorted(df['Año'].dropna().unique())
    año_seleccionado = st.selectbox("Seleccionar Año", años_disponibles)

    # Selección mes según año
    meses_disponibles = df[df['Año'] == año_seleccionado][['MesNum', 'MesNombre']].drop_duplicates().sort_values('MesNum')
    mes_seleccionado = st.selectbox("Seleccionar Mes", meses_disponibles['MesNombre'].tolist())

    # Selección día según año y mes
    dias_disponibles = df[(df['Año'] == año_seleccionado) & (df['MesNombre'] == mes_seleccionado)]['Día'].dropna().unique()
    dias_disponibles = sorted(dias_disponibles)
    dia_seleccionado = st.selectbox("Seleccionar Día", dias_disponibles)

    # Filtrar datos según año, mes y día seleccionado
    df_detalle_fecha = df[
        (df['Año'] == año_seleccionado) &
        (df['MesNombre'] == mes_seleccionado) &
        (df['Día'] == dia_seleccionado)
    ]

    if df_detalle_fecha.empty:
        st.warning("No hay datos para la fecha seleccionada.")
    else:
        ordenar_por = []
        if col_tipo_producto:
            ordenar_por.append(col_tipo_producto)
        ordenar_por.append(col_producto)

        df_detalle_fecha = df_detalle_fecha.sort_values(by=ordenar_por)

        categorias_unicas = df_detalle_fecha[col_tipo_producto].dropna().unique() if col_tipo_producto else ["Sin Categoría"]

        # Mostrar tabla por cada categoría de producto
        for cat in categorias_unicas:
            st.markdown(f"### 📂 Categoría: {cat}")
            if col_tipo_producto:
                df_cat = df_detalle_fecha[df_detalle_fecha[col_tipo_producto] == cat]
            else:
                df_cat = df_detalle_fecha

            cols_mostrar = [col_producto, 'Cantidad', 'Subtotal Neto']
            cols_mostrar = [c for c in cols_mostrar if c in df_cat.columns]
            st.dataframe(df_cat[cols_mostrar], use_container_width=True)

# ---------------------------
# PESTAÑA 4: Productos repetidos y no registrados en catálogo
# ---------------------------
with tab4:
    st.markdown("## 🧾 Productos Repetidos y No Registrados")

    if df_catalogo.empty:
        st.warning("No se pudo cargar el catálogo. Por favor revisa la URL en report.json")
    else:
        # Detectar columnas clave en catálogo: nombre producto, variante y SKU
        col_nom_prod = None
        col_variante = None
        col_sku = None
        for c in df_catalogo.columns:
            c_lower = c.lower()
            if "nombre" in c_lower:
                col_nom_prod = c
            if "variante" in c_lower:
                col_variante = c
            if "sku" == c_lower:
                col_sku = c

        # Mostrar las columnas detectadas para transparencia
        st.write(f"Columna nombre producto detectada en catálogo: {col_nom_prod}")
        st.write(f"Columna variante detectada en catálogo: {col_variante}")
        st.write(f"Columna SKU detectada en catálogo: {col_sku}")

        if not col_nom_prod:
            st.error("No se encontró columna 'Nombre del Producto' en el catálogo.")
        else:
            # Buscar duplicados en catálogo combinando nombre + variante + sku si existen
            columnas_para_duplicados = [col_nom_prod]
            if col_variante:
                columnas_para_duplicados.append(col_variante)
            if col_sku:
                columnas_para_duplicados.append(col_sku)

            st.write("### Productos con nombres duplicados en catálogo (mismo nombre + variante + SKU):")
            dup_nombres = df_catalogo[df_catalogo.duplicated(subset=columnas_para_duplicados, keep=False)]
            st.dataframe(dup_nombres.sort_values(columnas_para_duplicados), use_container_width=True)

        if col_sku:
            st.write("### Productos con SKU duplicados en catálogo:")
            dup_skus = df_catalogo[df_catalogo.duplicated(subset=[col_sku], keep=False)]
            st.dataframe(dup_skus.sort_values(col_sku), use_container_width=True)

        # Comparar productos vendidos vs catálogo por nombre
        st.write("### Productos vendidos que NO están en el catálogo (por nombre):")
        nombres_catalogo = df_catalogo[col_nom_prod].dropna().str.strip().str.lower().unique()
        nombres_ventas = df[col_producto].dropna().str.strip().str.lower().unique()
        productos_no_catalogo = sorted(set(nombres_ventas) - set(nombres_catalogo))
        if productos_no_catalogo:
            st.dataframe(pd.DataFrame(productos_no_catalogo, columns=["Producto vendido no registrado"]))
        else:
            st.success("Todos los productos vendidos están registrados en el catálogo.")

        # Productos vendidos con SKU que no están en catálogo
        if col_sku:
            col_sku_ventas = encontrar_col("sku")
            if col_sku_ventas:
                st.write("### Productos vendidos con SKU que NO están en el catálogo:")
                skus_catalogo = df_catalogo[col_sku].dropna().astype(str).str.strip().unique()
                skus_ventas = df[col_sku_ventas].dropna().astype(str).str.strip().unique()
                skus_no_catalogo = sorted(set(skus_ventas) - set(skus_catalogo))
                if skus_no_catalogo:
                    st.dataframe(pd.DataFrame(skus_no_catalogo, columns=["SKU vendido no registrado"]))
                else:
                    st.success("Todos los SKUs vendidos están registrados en el catálogo.")


Requisitos
Python 3.7+

Streamlit

Pandas

Altair

OpenPyXL (para leer Excel)

Instalar dependencias:

bash
Copiar
Editar
pip install streamlit pandas altair openpyxl
Cómo ejecutar
Desde terminal o consola, en la carpeta del proyecto, ejecutar:

bash
Copiar
Editar
streamlit run nombre_del_archivo.py
Luego abrir el navegador en la URL que se muestra (normalmente http://localhost:8501).

Uso
Modificar el archivo report.json con las URLs o rutas locales del CSV de ventas y catálogo Excel.

Abrir el dashboard y usar los filtros laterales para explorar datos.

Navegar entre pestañas para diferentes análisis (resumen, ABC, detalle diario, calidad catálogo).

Explicación técnica
El dashboard detecta automáticamente columnas clave para mayor flexibilidad con distintos formatos de CSV.

Usa cache para optimizar carga de archivos grandes.

Permite filtrar por sucursal, producto, tipo, y mes.

Presenta métricas resumidas, tablas detalladas y gráficos interactivos.

Integra catálogo para detectar productos duplicados y faltantes, ayudando a mantener la calidad de datos.

Todo desarrollado en Python con librerías estándar y código limpio, modular y comentado.



