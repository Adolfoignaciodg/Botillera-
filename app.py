import streamlit as st
import pandas as pd
import json
import altair as alt

# Configuración de la página
st.set_page_config(page_title="Dashboard Botillería", layout="wide")
st.title("📊 Dashboard de Ventas")

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
df[col_fecha] = pd.to_datetime(df[col_fecha], errors='coerce', dayfirst=True)

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

import io

# Define variables de columna según tu Excel
col_producto = "+Producto / Servicio"  # nombre exacto de la columna producto
col_fecha = "+Fecha Documento"         # nombre exacto de la columna fecha
col_tipo_producto = "+Tipo de Producto / Servicio"  # para filtrar categoría


import io

import io

import io

with tab1:
    st.markdown("## 📌 Resumen General")
    resumen = {m: df_filtrado[m].sum() for m in medidas}
    cols_metrics = st.columns(len(medidas))
    for idx, m in enumerate(medidas):
        valor = resumen.get(m, 0)
        display_val = f"{int(valor):,}".replace(",", ".") if m == 'Cantidad' else formato_moneda(valor)
        cols_metrics[idx].metric(m, display_val)

    st.markdown(f"## 🛒 Cantidades Vendidas por Producto en categoría '{seleccion_tipo_producto or 'Todos'}' " +
                (f"y Mes '{seleccion_mes}'" if seleccion_mes != 'Todos' else "(todo el tiempo)"))

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
        pivot_diario = pivot_diario.sort_index(axis=1)
        fechas_formateadas = pivot_diario.columns.strftime('%d/%m/%Y')
        pivot_diario.columns = fechas_formateadas

        # Agregar totales por fila y columna
        pivot_diario['Total'] = pivot_diario.sum(axis=1)
        total_col = pivot_diario.sum(axis=0)
        total_col.name = 'Total'
        pivot_diario = pd.concat([pivot_diario, pd.DataFrame([total_col])])
        pivot_diario = pivot_diario.astype(int)

        # Mostrar tabla separando totales para evitar errores de .style
        pivot_diario_reset = pivot_diario.reset_index()
        ultima_fila = pivot_diario_reset.iloc[[-1]]
        otras_filas = pivot_diario_reset.iloc[:-1]

        st.dataframe(otras_filas, use_container_width=True)
        st.markdown("### 🔢 Totales Generales")
        try:
            st.dataframe(
                ultima_fila.style.set_properties(**{
                    'background-color': '#d9ead3',
                    'font-weight': 'bold'
                }),
                use_container_width=True
            )
        except:
            st.dataframe(ultima_fila, use_container_width=True)

        # Mostrar productos sin ventas
        if seleccion_tipo_producto != "Todos" and seleccion_tipo_producto is not None:
            productos_en_categoria = df[df[col_tipo_producto] == seleccion_tipo_producto][col_producto].drop_duplicates()
            productos_vendidos = df_filtrado[col_producto].drop_duplicates()
            productos_no_vendidos = productos_en_categoria[~productos_en_categoria.isin(productos_vendidos)]

            st.markdown(f"## 🚫 Productos SIN ventas en categoría '{seleccion_tipo_producto}'")
            if not productos_no_vendidos.empty:
                st.dataframe(productos_no_vendidos.to_frame(name=col_producto), use_container_width=True)
            else:
                st.info("Todos los productos de esta categoría han sido vendidos en el periodo seleccionado.")

        prod_para_graf = st.selectbox("Seleccionar Producto para gráfico diario", ["Todos"] + sorted(detalle_diario[col_producto].unique()))
        if prod_para_graf != "Todos":
            df_graf = detalle_diario[detalle_diario[col_producto] == prod_para_graf]
            graf_diario = alt.Chart(df_graf).mark_line(point=True).encode(
                x=alt.X(col_fecha, title="Fecha", axis=alt.Axis(format='%d/%m/%Y')),
                y=alt.Y('Cantidad', title="Cantidad Vendida"),
                tooltip=[
                    alt.Tooltip(col_fecha, title="Fecha", format='%d/%m/%Y'),
                    alt.Tooltip('Cantidad')
                ]
            ).properties(height=300)
            st.altair_chart(graf_diario, use_container_width=True)

    else:
        detalle_diario = df_filtrado.groupby(col_fecha)['Cantidad'].sum().reset_index().sort_values(col_fecha)
        st.dataframe(detalle_diario, use_container_width=True)

        graf_diario = alt.Chart(detalle_diario).mark_line(point=True).encode(
            x=alt.X(col_fecha, title="Fecha", axis=alt.Axis(format='%d/%m/%Y')),
            y=alt.Y('Cantidad', title="Cantidad Vendida"),
            tooltip=[
                alt.Tooltip(col_fecha, title="Fecha", format='%d/%m/%Y'),
                alt.Tooltip('Cantidad')
            ]
        ).properties(height=300)
        st.altair_chart(graf_diario, use_container_width=True)

with tab2:
    st.markdown("## 🔍 Análisis ABC de Productos")

    df_abc = df_filtrado.copy()

    if df_abc.empty:
        st.warning("No hay datos para esta selección.")
    else:
        columna_valor = st.selectbox(
            "Seleccionar métrica para Análisis ABC",
            ["Margen Neto", "Subtotal Neto"]
        )

        def calcular_abc(df_abc, valor_col='Subtotal Neto', grupo_col=col_producto):
            df_grouped = df_abc.groupby(grupo_col).agg({
                valor_col: 'sum',
                'Cantidad': 'sum'
            }).reset_index()

            df_grouped = df_grouped.sort_values(by=valor_col, ascending=False)
            df_grouped['Acumulado'] = df_grouped[valor_col].cumsum()
            total = df_grouped[valor_col].sum()
            df_grouped['PorcAcum'] = df_grouped['Acumulado'] / total
            bins = [0, 0.7, 0.9, 1]
            labels = ['A', 'B', 'C']
            df_grouped['tipo de producto'] = pd.cut(df_grouped['PorcAcum'], bins=bins, labels=labels, include_lowest=True)

            # Si es Margen Neto, calculamos margen por unidad
            if valor_col == "Margen Neto":
                df_grouped['Margen por Unidad'] = df_grouped.apply(
                    lambda x: x[valor_col] / x['Cantidad'] if x['Cantidad'] > 0 else 0, axis=1
                )

            return df_grouped

        df_abc_result = calcular_abc(df_abc, valor_col=columna_valor)

        # Crear copia para mostrar en tabla con formato CLP
        df_tabla = df_abc_result.copy()
        df_tabla[columna_valor] = df_tabla[columna_valor].apply(lambda x: f"${x:,.0f}".replace(",", "."))
        df_tabla['Cantidad'] = df_tabla['Cantidad'].apply(lambda x: f"{x:,.0f}".replace(",", "."))
        df_tabla['PorcAcum'] = (df_abc_result['PorcAcum'] * 100).round(2).astype(str) + '%'
        if 'Margen por Unidad' in df_tabla.columns:
            df_tabla['Margen por Unidad'] = df_tabla['Margen por Unidad'].apply(lambda x: f"${x:,.0f}".replace(",", "."))

        # Mostrar tabla con formato
        columnas_mostrar = [col_producto, columna_valor, 'Cantidad', 'PorcAcum', 'tipo de producto']
        if 'Margen por Unidad' in df_tabla.columns:
            columnas_mostrar.append('Margen por Unidad')

        st.dataframe(
            df_tabla[columnas_mostrar].sort_values(by='tipo de producto'),
            use_container_width=True
        )

        # Gráfico con valores reales (sin formatear)
        graf_abc = alt.Chart(df_abc_result).mark_bar().encode(
            x=alt.X(col_producto, sort='-y'),
            y=alt.Y(columna_valor, title=f'{columna_valor} CLP'),
            color=alt.Color('tipo de producto', scale=alt.Scale(domain=['A', 'B', 'C'], range=['#1f77b4', '#ff7f0e', '#2ca02c'])),
            tooltip=[
                alt.Tooltip(col_producto, title='Producto'),
                alt.Tooltip(columna_valor, format=",.0f", title=columna_valor),
                alt.Tooltip('Cantidad', format=",.0f", title='Unidades Vendidas'),
                alt.Tooltip('tipo de producto', title='Clasificación ABC')
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
        categorias_clave = [
            'DESTILADOS', 'AGUAS. JUGOS Y TE HELADO', 'BEBIDAS',
            'CERVEZAS', 'VINOS', 'TABAQUERIA', 'LICORES',
            'ENERGETICAS E ISOTONICAS', 'ESPUMANTES'
        ]

        # Buscar columna categoría en stock
        col_categoria_stock = next((c for c in df_stock.columns if "tipo de producto" in c.lower()), None)

        if not col_categoria_stock:
            st.error("No se encontró columna de categoría en archivo de stock.")
        else:
            df_stock_filtrado = df_stock[df_stock[col_categoria_stock].str.upper().isin(categorias_clave)]

            categorias_disponibles = sorted(df_stock_filtrado[col_categoria_stock].dropna().unique())
            seleccion_cat_stock = st.selectbox("Seleccionar Categoría", ["Todas"] + categorias_disponibles)

            if seleccion_cat_stock != "Todas":
                df_stock_filtrado = df_stock_filtrado[df_stock_filtrado[col_categoria_stock] == seleccion_cat_stock]

            # --- Ventas acumuladas desde enero ---
            inicio_anio = pd.Timestamp(datetime.now().year, 1, 1)
            ventas_desde_enero = df[df[col_fecha] >= inicio_anio]
            ventas_por_producto = ventas_desde_enero.groupby(col_producto)['Cantidad'].sum().reset_index()
            ventas_por_producto.columns = [col_producto, "Vendidas desde Ene"]

            col_prod_stock = "Producto"  # asegúrate que coincide con el Excel

            df_stock_cuadrado = pd.merge(
                df_stock_filtrado, ventas_por_producto,
                left_on=col_prod_stock, right_on=col_producto, how='left'
            )
            df_stock_cuadrado["Vendidas desde Ene"] = df_stock_cuadrado["Vendidas desde Ene"].fillna(0)

            # Agregar alerta por bajo stock o sin ventas
            df_stock_cuadrado["Alerta"] = df_stock_cuadrado.apply(lambda row: (
                "❗ Sin ventas" if row["Vendidas desde Ene"] == 0 else
                "⚠️ Bajo Stock" if row["Vendidas desde Ene"] >= 20 and row.get("Stock Actual", 0) < 5 else ""
            ), axis=1)

            # Columnas visuales
            posibles_cols = [
                "Producto", "Marca", "Stock Actual", "Cantidad por Despachar",
                "Cantidad Disponible", "Por Recibir", "Costo Neto Prom. Unitario",
                "Precio Venta Bruto", "Margen Unitario"
            ]
            columnas_mostrar = [c for pc in posibles_cols for c in df_stock_cuadrado.columns if pc.lower() == c.lower()]

            columnas_mostrar += ["Vendidas desde Ene", "Alerta"]

            # Estilo visual para stock
            def destacar_stock(val):
                try:
                    if float(val) == 0:
                        return 'background-color: #ff4d4d; color: white; font-weight: bold'
                    elif float(val) < 5:
                        return 'background-color: #ffcc00; font-weight: bold'
                except:
                    return ''

            st.markdown("### Tabla de stock + ventas desde enero")
            styled_df = df_stock_cuadrado[columnas_mostrar].style.applymap(
                destacar_stock,
                subset=[c for c in columnas_mostrar if "stock" in c.lower()]
            )
            st.dataframe(styled_df, use_container_width=True)

            # KPIs resumen por categoría
            palabras_clave = ['stock', 'cantidad por despachar', 'cantidad disponible', 'por recibir']
            columnas_resumen = [c for c in columnas_mostrar if any(p in c.lower() for p in palabras_clave)]

            if columnas_resumen:
                resumen_stock = df_stock_cuadrado.groupby(col_categoria_stock).agg(
                    {c: 'sum' for c in columnas_resumen}
                ).reset_index()
                st.markdown("### Resumen por Categoría")
                st.dataframe(resumen_stock, use_container_width=True)

            else:
                st.warning("No se encontraron columnas esperadas en archivo de stock para mostrar.")
