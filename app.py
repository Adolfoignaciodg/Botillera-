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

# --- Obtener URL catálogo desde JSON ---
catalogo_url = config.get("catalogoProductos", {}).get("url", "")
if not catalogo_url:
    st.warning("No se encontró URL del catálogo en JSON, la pestaña de productos repetidos no funcionará.")

# --- Función para cargar datos CSV con cache ---
@st.cache_data(show_spinner=False)
def cargar_datos_csv(url):
    try:
        df = pd.read_csv(url, sep=None, engine='python')
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"Error cargando CSV: {e}")
        return pd.DataFrame()

df = cargar_datos_csv(csv_url)
if df.empty:
    st.warning("Archivo CSV vacío o no cargado.")
    st.stop()

# --- Función para cargar catálogo Excel con cache ---
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

if seleccion_mes != "Todas" and seleccion_mes != "Todos":
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
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Resumen y Detalle",
    "Análisis ABC",
    "Detalle por Día y Categoría",
    "🧾 Productos Repetidos / No Registrados",
    "📦 Cuadratura de Stock"
])

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
            df_abc['tipo de producto'] = pd.cut(df_abc['PorcAcum'], bins=bins, labels=labels, include_lowest=True)
            return df_abc

        df_abc_result = calcular_abc(df_abc)
        st.dataframe(df_abc_result[[col_producto, 'Subtotal Neto', 'PorcAcum', 'tipo de producto']].sort_values(by='tipo de producto'))

        graf_abc = alt.Chart(df_abc_result).mark_bar().encode(
            x=alt.X(col_producto, sort='-y'),
            y=alt.Y('Subtotal Neto', title='Subtotal Neto CLP'),
            color=alt.Color('tipo de producto', scale=alt.Scale(domain=['A', 'B', 'C'], range=['#1f77b4', '#ff7f0e', '#2ca02c'])),
            tooltip=[
                alt.Tooltip(col_producto, title='Producto'),
                alt.Tooltip('Subtotal Neto', format=",.0f"),
                alt.Tooltip('tipo de producto')
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

with tab4:
    st.markdown("## 🧾 Productos Repetidos y No Registrados")

    if df_catalogo.empty:
        st.warning("No se pudo cargar el catálogo. Por favor revisa la URL en report.json")
    else:
        # Detectar columnas clave en catálogo: nombre, variante y SKU
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

        st.write(f"Columna nombre producto detectada en catálogo: {col_nom_prod}")
        st.write(f"Columna variante detectada en catálogo: {col_variante}")
        st.write(f"Columna SKU detectada en catálogo: {col_sku}")

        if not col_nom_prod:
            st.error("No se encontró columna 'Nombre del Producto' en el catálogo.")
        else:
            # Para detectar duplicados se usa la combinación nombre + variante + sku (si existen)
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

        # Productos vendidos en CSV no encontrados en catálogo por nombre (normalizados)
        st.write("### Productos vendidos que NO están en el catálogo (por nombre):")
        nombres_catalogo = df_catalogo[col_nom_prod].dropna().str.strip().str.lower().unique()
        nombres_ventas = df[col_producto].dropna().str.strip().str.lower().unique()
        productos_no_catalogo = sorted(set(nombres_ventas) - set(nombres_catalogo))
        if productos_no_catalogo:
            st.dataframe(pd.DataFrame(productos_no_catalogo, columns=["Producto vendido no registrado"]))
        else:
            st.success("Todos los productos vendidos están registrados en el catálogo.")

        # Productos vendidos con SKU no encontrados en catálogo
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



# --- NUEVA PESTAÑA: Cuadratura de Stock ---
with tab5:
    st.markdown("## 📦 Cuadratura de Stock")

    # URL raw directa a tu Excel stock.xlsx (modifica según tu repo)
    url_stock = "https://raw.githubusercontent.com/Adolfoignaciodg/Botillera-/main/stock.xlsx"

    @st.cache_data
    def cargar_stock(url):
        try:
            df_stock = pd.read_excel(url)
            df_stock.columns = df_stock.columns.str.strip()
            return df_stock
        except Exception as e:
            st.error(f"Error cargando archivo de stock: {e}")
            return pd.DataFrame()

    df_stock = cargar_stock(url_stock)

    if df_stock.empty:
        st.warning("No se pudo cargar el archivo de stock.")
    else:
        # Filtrar solo las categorías que nos interesan
        categorias_clave = [
            'DESTILADOS',
            'AGUAS. JUGOS Y TE HELADO',
            'BEBIDAS',
            'CERVEZAS',
            'VINOS',
            'TABAQUERIA',
            'LICORES',
            'ENERGETICAS E ISOTONICAS',
            'ESPUMANTES'
        ]

        # Buscar columna Categoría (sensible a mayúsculas/minúsculas)
        col_categoria_stock = None
        for c in df_stock.columns:
            if "tipo de producto" in c.lower():
                col_categoria_stock = c
                break

        if not col_categoria_stock:
            st.error("No se encontró columna de categoría en archivo de stock.")
        else:
            df_stock_filtrado = df_stock[df_stock[col_categoria_stock].str.upper().isin(categorias_clave)]

            # Mostrar filtros
            categorias_disponibles = sorted(df_stock_filtrado[col_categoria_stock].dropna().unique())
            seleccion_cat_stock = st.selectbox("Seleccionar Categoría", ["Todas"] + categorias_disponibles)

            # Si selecciona categoría filtra
            if seleccion_cat_stock != "Todas":
                df_stock_filtrado = df_stock_filtrado[df_stock_filtrado[col_categoria_stock] == seleccion_cat_stock]

            # Columnas para mostrar, ajustar según tu stock.xlsx
            columnas_mostrar = []
            posibles_cols = [
                "Producto",
                "Marca",
                "Stock Actual",
                "Por Despachar",
                "Disponible",
                "Por Recibir",
                "Costo Neto Promedio",
                "Precio Venta",
                "Margen"
            ]
            # Mapear columnas según las que existan realmente en el archivo
            for pc in posibles_cols:
                for c in df_stock_filtrado.columns:
                    if pc.lower() == c.lower():
                        columnas_mostrar.append(c)
                        break

            if columnas_mostrar:
                # Resaltar stock 0 o bajo con estilo
                def destacar_stock(val):
                    try:
                        if float(val) == 0:
                            return 'background-color: #ff4d4d; color: white; font-weight: bold'
                        elif float(val) < 5:
                            return 'background-color: #ffcc00; font-weight: bold'
                    except:
                        return ''

                # Mostrar tabla con estilos para la columna Stock Actual si existe
                if "Stock Actual" in columnas_mostrar or any("stock" in c.lower() for c in columnas_mostrar):
                    st.markdown("### Tabla de stock filtrado")
                    styled_df = df_stock_filtrado[columnas_mostrar].style.applymap(destacar_stock, subset=[c for c in columnas_mostrar if "stock" in c.lower()])
                    st.dataframe(styled_df, use_container_width=True)
                else:
                    st.dataframe(df_stock_filtrado[columnas_mostrar], use_container_width=True)

                # KPIs resumen por categoría
                    palabras_clave = ['stock','despachar','disponible','recibir']
                    columnas_resumen = [c for c in columnas_mostrar if any(p in c.lower() for p in palabras_clave)]
                

                if  columnas_resumen:
                    resumen_stock = df_stock_filtrado.groupby(col_categoria_stock).agg({c: 'sum' for c in columnas_resumen}).reset_index()
                    st.markdown("### Resumen por Categoría")
                    st.dataframe(resumen_stock, use_container_width=True)
            else:
                st.warning("No se encontraron columnas esperadas en archivo de stock para mostrar.")


