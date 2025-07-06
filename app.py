import streamlit as st
import pandas as pd
import json
import altair as alt
import re
import datetime

st.set_page_config(page_title="Dashboard Botillería", layout="wide")
st.title("📊 Dashboard de Ventas - Visión Propietario")

# --- Cargar configuración JSON ---
try:
    with open("report.json", "r", encoding="utf-8") as f:
        config = json.load(f)
except Exception as e:
    st.error(f"Error leyendo JSON: {e}")
    st.stop()

csv_url = config.get("dataSource", {}).get("filename", "")
if not csv_url:
    st.error("No se encontró URL CSV en JSON.")
    st.stop()

# --- Función para cargar datos ---
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

# --- Detectar columnas clave dinámicamente ---
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
col_dia = encontrar_col("día") or encontrar_col("dia")  # Para día

# Medidas que se esperan en el dataset
medidas_esperadas = ["Subtotal Neto", "Subtotal Bruto", "Margen Neto", "Costo Neto", "Impuestos", "Cantidad"]
medidas = [m for m in medidas_esperadas if m in cols]

# Validar columnas clave
if not col_sucursal or not col_producto or not col_mes:
    st.error("No se encontraron columnas clave para sucursal, producto o mes en el CSV.")
    st.write("Columnas encontradas:", cols)
    st.stop()

if not medidas:
    st.error("No se encontraron columnas de medidas importantes en el CSV.")
    st.stop()

# --- Convertir columnas de medidas a numéricas ---
for col in medidas:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

# --- Normalizar columna Mes: convertir número a nombre y limpiar texto ---
def numero_a_mes(mes):
    m = str(mes).strip()
    if m.isdigit():
        n = int(m)
        if 1 <= n <= 12:
            meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
                     "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
            return meses[n-1]
    texto_sin_num = re.sub(r"^\d+\s*", "", m).lower()
    return texto_sin_num

df[col_mes] = df[col_mes].apply(numero_a_mes)

# --- Convertir día a numérico si existe ---
if col_dia and col_dia in df.columns:
    df[col_dia] = pd.to_numeric(df[col_dia], errors='coerce')

# --- Preparar filtros del sidebar ---
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
    seleccion_tipo_producto = st.sidebar.selectbox("Seleccionar Tipo de Producto / Servicio", tipos_producto)
else:
    seleccion_tipo_producto = None

# Filtrar productos según tipo seleccionado para mejorar UX
df_para_productos = df.copy()
if seleccion_tipo_producto and seleccion_tipo_producto != "Todos" and col_tipo_producto:
    df_para_productos = df_para_productos[df_para_productos[col_tipo_producto] == seleccion_tipo_producto]

productos = ["Todos"] + sorted(df_para_productos[col_producto].dropna().unique().tolist())
seleccion_producto = st.sidebar.selectbox("Seleccionar Producto", productos)

meses = ["Todos"] + sorted(df[col_mes].dropna().unique().tolist())
seleccion_mes = st.sidebar.selectbox("Seleccionar Mes", meses)

# --- Aplicar filtros a dataframe ---
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

# --- Función para formatear moneda chilena ---
def formato_moneda(x):
    try:
        val = float(x)
        return f"${val:,.0f}".replace(",", ".")
    except:
        return "$0"

# --- Función para cálculo ABC ---
def calcular_abc(df_abc, valor_col='Subtotal Neto', grupo_col=col_producto):
    df_abc = df_abc.groupby(grupo_col)[valor_col].sum().reset_index()
    df_abc = df_abc.sort_values(by=valor_col, ascending=False)
    df_abc['Acumulado'] = df_abc[valor_col].cumsum()
    total = df_abc[valor_col].sum()
    df_abc['PorcAcum'] = df_abc['Acumulado'] / total
    choices = ['A', 'B', 'C']
    df_abc['Categoria'] = pd.cut(df_abc['PorcAcum'], bins=[0, 0.7, 0.9, 1], labels=choices, include_lowest=True)
    return df_abc

# --- Orden definido para meses ---
orden_meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
               "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

df_filtrado[col_mes] = pd.Categorical(df_filtrado[col_mes], categories=orden_meses, ordered=True)

# --- Función para obtener tooltip con fecha completa ---
def dia_semana_nombre(mes_nombre, dia_num):
    meses_num = {
        "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
        "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
        "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12
    }
    mes_num = meses_num.get(mes_nombre.lower())
    if mes_num is None or pd.isna(dia_num):
        return ""
    try:
        fecha = datetime.date(2025, mes_num, int(dia_num))  # año fijo
        nombre_dia = fecha.strftime("%A").lower()
        nombre_dia_es = {
            "monday": "lunes",
            "tuesday": "martes",
            "wednesday": "miércoles",
            "thursday": "jueves",
            "friday": "viernes",
            "saturday": "sábado",
            "sunday": "domingo"
        }
        mes_nombre_minuscula = mes_nombre.lower()
        return f"{nombre_dia_es.get(nombre_dia, nombre_dia)} {int(dia_num)} {mes_nombre_minuscula} 2025"
    except:
        return ""

# --- Construcción de pestañas ---
tab1, tab2 = st.tabs(["Resumen y Gráficos", "Análisis ABC"])

with tab1:
    st.markdown("## 📌 Resumen General")

    resumen = {m: df_filtrado[m].sum() for m in medidas}

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Subtotal Neto", formato_moneda(resumen.get("Subtotal Neto", 0)))
    col2.metric("Subtotal Bruto", formato_moneda(resumen.get("Subtotal Bruto", 0)))
    col3.metric("Margen Neto", formato_moneda(resumen.get("Margen Neto", 0)))
    col4.metric("Costo Neto", formato_moneda(resumen.get("Costo Neto", 0)))
    col5.metric("Impuestos", formato_moneda(resumen.get("Impuestos", 0)))
    col6.metric("Cantidad Vendida", f"{int(resumen.get('Cantidad', 0)):,}".replace(",", "."))

    st.markdown("## 📈 Subtotal Neto por Mes")
    graf1 = alt.Chart(df_filtrado).mark_bar(color="#377eb8").encode(
        x=alt.X(col_mes, sort=orden_meses),
        y=alt.Y("sum(Subtotal Neto)", title="Subtotal Neto"),
        tooltip=[
            alt.Tooltip("sum(Subtotal Neto)", title="Subtotal CLP", format=",.0f"),
            alt.Tooltip("sum(Margen Neto)", title="Margen CLP", format=",.0f"),
            alt.Tooltip("sum(Cantidad)", title="Cantidad", format=",.0f")
        ]
    ).properties(height=400)
    st.altair_chart(graf1, use_container_width=True)

    st.markdown("## 📉 Margen Neto por Mes")
    df_agrupado = df_filtrado.groupby(col_mes).agg({
        "Margen Neto": "sum",
        "Subtotal Neto": "sum"
    }).reset_index()

    df_agrupado["Margen Neto Tooltip"] = df_agrupado["Margen Neto"].apply(formato_moneda)
    df_agrupado["Subtotal Neto Tooltip"] = df_agrupado["Subtotal Neto"].apply(formato_moneda)

    graf2 = alt.Chart(df_agrupado).mark_line(point=True, color="#e41a1c").encode(
        x=alt.X(col_mes, sort=orden_meses, title="Mes"),
        y=alt.Y("Margen Neto", title="Margen Neto"),
        tooltip=[
            alt.Tooltip("Margen Neto Tooltip", title="Margen CLP"),
            alt.Tooltip("Subtotal Neto Tooltip", title="Subtotal CLP")
        ]
    ).properties(height=400)
    st.altair_chart(graf2, use_container_width=True)

    if len(sucursales_disponibles) > 1:
        st.markdown("## 🏪 Ventas por Sucursal")
        ventas_suc = df_filtrado.groupby(col_sucursal)["Subtotal Neto"].sum().sort_values(ascending=False).reset_index()
        graf3 = alt.Chart(ventas_suc).mark_bar(color="#4daf4a").encode(
            x=alt.X("Subtotal Neto:Q", title="Subtotal CLP"),
            y=alt.Y(f"{col_sucursal}:N", sort="-x"),
            tooltip=[alt.Tooltip("Subtotal Neto", format=",.0f")]
        ).properties(height=400)
        st.altair_chart(graf3, use_container_width=True)

    st.markdown("## 🛒 Top 10 Productos por Subtotal Neto")
    top_prod = df_filtrado.groupby(col_producto)["Subtotal Neto"].sum().sort_values(ascending=False).head(10).reset_index()
    graf4 = alt.Chart(top_prod).mark_bar(color="#984ea3").encode(
        x=alt.X("Subtotal Neto:Q", title="Subtotal CLP"),
        y=alt.Y(f"{col_producto}:N", sort="-x"),
        tooltip=[alt.Tooltip("Subtotal Neto", format=",.0f")]
    ).properties(height=400)
    st.altair_chart(graf4, use_container_width=True)

    if col_tipo_producto:
        st.markdown(f"## 📊 Subtotal por Tipo de Producto / Servicio ({seleccion_tipo_producto or 'Todos'})")
        ventas_tipo = df_filtrado.groupby(col_tipo_producto)["Subtotal Neto"].sum().sort_values(ascending=False).reset_index()
        graf5 = alt.Chart(ventas_tipo).mark_bar(color="#ff7f00").encode(
            x=alt.X("Subtotal Neto:Q", title="Subtotal CLP"),
            y=alt.Y(f"{col_tipo_producto}:N", sort="-x"),
            tooltip=[alt.Tooltip("Subtotal Neto", format=",.0f")]
        ).properties(height=400)
        st.altair_chart(graf5, use_container_width=True)

    # --- Cantidad diaria para producto y mes seleccionados ---
    if seleccion_mes != "Todos" and seleccion_producto != "Todos" and col_dia and col_dia in df_filtrado.columns:
        st.markdown(f"## 📅 Cantidad Vendida por Día para '{seleccion_producto}' en {seleccion_mes.capitalize()}")
        df_producto_mes = df_filtrado[(df_filtrado[col_producto] == seleccion_producto) & (df_filtrado[col_mes] == seleccion_mes)]
        df_dias_producto = df_producto_mes.groupby(col_dia).agg({"Cantidad": "sum"}).reset_index()
        df_dias_producto[col_dia] = pd.to_numeric(df_dias_producto[col_dia], errors='coerce')
        df_dias_producto = df_dias_producto.sort_values(col_dia)

        # Crear tooltip con fecha completa
        df_dias_producto["Tooltip Dia"] = df_dias_producto.apply(
            lambda row: dia_semana_nombre(seleccion_mes, row[col_dia]), axis=1)

        graf_cantidad_dia = alt.Chart(df_dias_producto).mark_bar(color="#66c2a5").encode(
            x=alt.X(f"{col_dia}:O", title="Día del Mes"),
            y=alt.Y("Cantidad", title="Cantidad Vendida"),
            tooltip=[
                alt.Tooltip("Tooltip Dia", title="Fecha"),
                alt.Tooltip("Cantidad", format=",.0f", title="Cantidad")
            ]
        ).properties(height=400)
        st.altair_chart(graf_cantidad_dia, use_container_width=True)

        # --- Mostrar resumen numérico junto al gráfico ---
        st.markdown("### 🧾 Resumen de Cantidad Vendida por Día")
        st.dataframe(df_dias_producto[[col_dia, "Cantidad"]].rename(columns={col_dia:"Día del Mes", "Cantidad":"Cantidad Vendida"}).reset_index(drop=True), use_container_width=True)

    # --- Tabla detalle ---
    st.markdown("## 📋 Detalle de Ventas")
    st.dataframe(df_filtrado.sort_values(by="Subtotal Neto", ascending=False), use_container_width=True)

with tab2:
    st.markdown("## 🔍 Análisis ABC de Productos")

    opcion_abc = st.radio("Ver análisis ABC por:", ("Total", "Por Mes"))

    if opcion_abc == "Total":
        df_abc = df_filtrado.copy()
    else:
        mes_abc = st.selectbox("Seleccionar Mes para ABC", meses[1:])  # excluye "Todos"
        df_abc = df_filtrado[df_filtrado[col_mes] == mes_abc]

    if df_abc.empty:
        st.warning("No hay datos para esta selección.")
    else:
        df_abc_result = calcular_abc(df_abc)

        st.dataframe(df_abc_result[[col_producto, 'Subtotal Neto', 'PorcAcum', 'Categoria']].sort_values(by='Categoria'))

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
