import streamlit as st
import pandas as pd
import calendar
from datetime import datetime
import altair as alt  # <- para gráficos interactivos en resumen y detalle por trabajador

# Paleta de colores uniforme y agradable para ambos gráficos
paleta_colores_anos = ['#4E79A7', '#F28E2B', '#E15759', '#76B7B2', '#59A14F', '#EDC948']

# Función para formatear números con separador de miles como punto y sin decimales
def formato_miles_punto(x):
    try:
        if pd.isna(x):
            return "-"
        return f"{int(x):,}".replace(",", ".")
    except:
        return x

# Configuración de la página
st.set_page_config(
    page_title="Dashboard",
    page_icon="📈",
    layout="wide"
)

st.title("Dashboard Stock Operacional")

# --- Selección de vista antes de cargar archivo ---
menu = st.sidebar.radio("Selecciona vista:", ["Resumen General", "Producción Total Mensual", "Detalle por Trabajador"])

# --- Subida de archivo solo si está en "Resumen General" ---
if menu == "Resumen General":
    uploaded_file = st.file_uploader("Sube el archivo Excel actualizado", type=["xlsx"])
    if uploaded_file is not None:
        archivo = uploaded_file
        st.success("✅ Archivo cargado correctamente.")
    else:
        archivo = "excel/reporte.xlsx"
        st.info("ℹ️ Se usará el archivo por defecto.")
else:
    archivo = "excel/reporte.xlsx"

try:
    # --- CARGA Y LIMPIEZA ---
    df_20 = pd.read_excel(archivo, sheet_name="STOCK 20")
    df_20["TIPO_ERROR"] = "Error 20"

    df_28 = pd.read_excel(archivo, sheet_name="STOCK 28")
    df_28["TIPO_ERROR"] = "Error 28"

    df = pd.concat([df_20, df_28], ignore_index=True)
    df.columns = df.columns.str.strip()

    filas_antes = len(df)
    df.dropna(how='all', inplace=True)
    filas_despues = len(df)
    filas_eliminadas = filas_antes - filas_despues

    if filas_eliminadas > 0:
        st.info(f"ℹ️ Se eliminaron {filas_eliminadas} filas completamente vacías del archivo.")

    df = df[df['Responsable'].notna() & (df['Responsable'].str.strip() != '')]
    df['Responsable'] = df['Responsable'].astype(str).str.strip().str.lower().str.capitalize()
    df['ESTADO FINAL'] = df['ESTADO FINAL'].astype(str).str.strip().str.upper()
    df['FECHA'] = pd.to_datetime(df['FECHA'], dayfirst=True, errors='coerce')
    df['Fecha de cierre'] = pd.to_datetime(df['Fecha de cierre'], dayfirst=True, errors='coerce')

    estados_na = df[df['ESTADO FINAL'].isna()]
    if not estados_na.empty:
        st.warning(f"⚠️ Atención: Se encontraron {len(estados_na)} registros sin ESTADO FINAL.")
        st.caption("Primeros registros sin estado:")
        st.dataframe(estados_na.head(), use_container_width=True)

    # --------------------- VISTAS ---------------------

    if menu == "Resumen General":
        total_stock = len(df)
        total_20 = len(df[df['TIPO_ERROR'] == 'Error 20'])
        total_28 = len(df[df['TIPO_ERROR'] == 'Error 28'])
        total_reg = len(df[df['ESTADO FINAL'] == 'REGULARIZADA'])

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("TOTAL STOCK", formato_miles_punto(total_stock))
        col2.metric("Error 28", formato_miles_punto(total_28))
        col3.metric("Error 20", formato_miles_punto(total_20))
        col4.metric("Regularizadas", formato_miles_punto(total_reg))

        # Desglose de regularizadas por PROGRAMA con % y formato limpio
        df_reg = df[df['ESTADO FINAL'] == 'REGULARIZADA']
        programas = ['Tradicional', 'Reactiva', 'Chile Apoya', 'COVID']
        conteo_programas = {p: len(df_reg[df_reg['PROGRAMA'].str.strip().str.upper() == p.upper()]) for p in programas}
        total_prog = sum(conteo_programas.values())
        
        desglose_programas = []
        for p in programas:
            cant = conteo_programas[p]
            porc = (cant / total_prog * 100) if total_prog > 0 else 0
            desglose_programas.append(f"**{p}:** {formato_miles_punto(cant)} ({porc:.1f}%)")
        st.markdown(" - ".join(desglose_programas))

        st.markdown("---")
        st.subheader("Resumen por Colaborador y Tipo de Error")

        df_resumen = df[df['TIPO_ERROR'].notna() & (df['TIPO_ERROR'].str.strip() != '')]
        resumen = df_resumen.groupby(["Responsable", "TIPO_ERROR"]).size().unstack(fill_value=0)
        resumen["TOTAL"] = resumen.sum(axis=1)
        resumen = resumen.sort_values("TOTAL", ascending=False)
        resumen_display = resumen.applymap(formato_miles_punto)
        st.dataframe(resumen_display, use_container_width=True)

        # --- Gráfico Altair interactivo en Resumen General ---
        df_reg_historico = df_reg.copy()
        df_reg_historico = df_reg_historico[df_reg_historico['Fecha de cierre'].notna()]
        df_reg_historico['Año'] = df_reg_historico['Fecha de cierre'].dt.year
        df_reg_historico['Mes'] = df_reg_historico['Fecha de cierre'].dt.month

        años = sorted(df_reg_historico['Año'].unique())
        todos_los_meses = pd.DataFrame([(a,m) for a in años for m in range(1,13)], columns=['Año', 'Mes'])

        resumen_mensual = df_reg_historico.groupby(['Año', 'Mes']).size().reset_index(name='Cantidad')
        resumen_mensual = pd.merge(todos_los_meses, resumen_mensual, on=['Año','Mes'], how='left').fillna(0)
        resumen_mensual['Cantidad'] = resumen_mensual['Cantidad'].astype(int)
        resumen_mensual['Mes_nombre'] = resumen_mensual['Mes'].apply(lambda x: calendar.month_name[x])

        meses_orden = list(calendar.month_name)[1:]  # Enero a Diciembre

        chart = (
            alt.Chart(resumen_mensual)
            .mark_bar()
            .encode(
                x=alt.X('Mes_nombre:N', sort=meses_orden, title='Mes'),
                y=alt.Y('Cantidad:Q', title='Cantidad de Regularizadas'),
                color=alt.Color('Año:N',
                                scale=alt.Scale(range=paleta_colores_anos),
                                legend=alt.Legend(title="Año")),
                tooltip=[
                    alt.Tooltip('Mes_nombre:N', title='Mes'),
                    alt.Tooltip('Año:N', title='Año'),
                    alt.Tooltip('Cantidad:Q', title='Cantidad')
                ]
            )
            .properties(
                width=700,
                height=400,
                title="Regularizadas mes a mes por año"
            )
            .interactive()
        )
        st.altair_chart(chart, use_container_width=True)


    elif menu == "Producción Total Mensual":
        st.subheader("Producción Total Mensual")

        df_reg = df[df['ESTADO FINAL'] == 'REGULARIZADA'].copy()
        df_reg = df_reg[df_reg['Fecha de cierre'].notna()]

        hoy = datetime.now()
        años_disponibles = sorted(df_reg['Fecha de cierre'].dt.year.dropna().unique())
        año_default = hoy.year if hoy.year in años_disponibles else años_disponibles[-1]
        año = st.selectbox("Selecciona Año", años_disponibles, index=años_disponibles.index(año_default))

        meses_disponibles = sorted(df_reg[df_reg['Fecha de cierre'].dt.year == año]['Fecha de cierre'].dt.month.unique())
        mes_default = hoy.month if hoy.month in meses_disponibles else meses_disponibles[-1]
        mes = st.selectbox("Selecciona Mes", meses_disponibles, index=meses_disponibles.index(mes_default), format_func=lambda x: calendar.month_name[x])

        actual = df_reg[(df_reg['Fecha de cierre'].dt.month == mes) & (df_reg['Fecha de cierre'].dt.year == año)]

        total_20 = len(actual[actual['TIPO_ERROR'] == 'Error 20'])
        total_28 = len(actual[actual['TIPO_ERROR'] == 'Error 28'])
        total = len(actual)

        col1, col2, col3 = st.columns(3)
        col1.metric(f"Error 28 ({calendar.month_name[mes]} {año})", formato_miles_punto(total_28))
        col2.metric(f"Error 20 ({calendar.month_name[mes]} {año})", formato_miles_punto(total_20))
        col3.metric("Total del Mes", formato_miles_punto(total))

        st.caption("Solo se consideran operaciones REGULARIZADAS con Fecha de cierre")

        if not actual.empty:
            conteo = actual.groupby([actual['Fecha de cierre'].dt.strftime("%d-%m-%Y"), 'TIPO_ERROR']).size().unstack(fill_value=0)
            conteo.index = pd.to_datetime(conteo.index, format="%d-%m-%Y")
            conteo = conteo.sort_index()
            conteo.index = conteo.index.strftime("%d-%m-%Y")
            conteo['TOTAL DIARIO'] = conteo.sum(axis=1)

            st.markdown(f"#### Detalle de Producción: {calendar.month_name[mes]} {año}")
            st.dataframe(conteo, use_container_width=True)
        else:
            st.info("No hay operaciones REGULARIZADAS este mes.")

    elif menu == "Detalle por Trabajador":
        responsables = sorted(df['Responsable'].dropna().unique())
        seleccionado = st.selectbox("Selecciona un responsable", responsables)

        df_resp = df[df['Responsable'] == seleccionado]
        hoy = pd.Timestamp.now()
        hace_un_mes = hoy - pd.DateOffset(months=1)

        fechas_validas = df_resp[(df_resp['ESTADO FINAL'] == 'REGULARIZADA') & (df_resp['Fecha de cierre'].notna())]['Fecha de cierre']
        año_default = fechas_validas.max().year if not fechas_validas.empty else hoy.year
        mes_default = fechas_validas.max().month if not fechas_validas.empty else hoy.month

        años_disponibles = sorted(df['FECHA'].dt.year.dropna().unique())
        año_index = años_disponibles.index(año_default) if año_default in años_disponibles else 0
        año = st.selectbox("Año", años_disponibles, index=año_index)

        meses_disponibles = sorted(df['FECHA'][df['FECHA'].dt.year == año].dt.month.unique())
        mes_index = meses_disponibles.index(mes_default) if mes_default in meses_disponibles else 0
        mes = st.selectbox("Mes", options=meses_disponibles, index=mes_index, format_func=lambda x: calendar.month_name[x])

        df_mes = df_resp[
            (df_resp['Fecha de cierre'].dt.year == año) &
            (df_resp['Fecha de cierre'].dt.month == mes) &
            (df_resp['ESTADO FINAL'] == 'REGULARIZADA')
        ]
        total_reg = len(df_mes)

        en_revision = df_resp[df_resp['ESTADO FINAL'] == 'EN REVISIÓN']
        pendiente = df_resp[df_resp['ESTADO FINAL'] == 'PENDIENTE']
        total_rev = len(en_revision)
        total_pen = len(pendiente)

        atrasadas = df_resp[
            (df_resp['ESTADO FINAL'].isin(['EN REVISIÓN', 'PENDIENTE'])) &
            (df_resp['FECHA'] < hace_un_mes)
        ]
        total_atrasadas = len(atrasadas)

        otros_estados = [
            "PENDIENTE BANCO", "CONSULTA BANCO", "OP EQUIPO COBRO",
            "CADUCADA", "RECHAZO FORMAL", "NO APLICA", "REVERSADA"
        ]
        otros = df_resp[df_resp['ESTADO FINAL'].isin(otros_estados)]

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("REGULARIZADAS", formato_miles_punto(total_reg))
        col2.metric("EN REVISIÓN", formato_miles_punto(total_rev))
        col3.metric("PENDIENTE", formato_miles_punto(total_pen))
        col4.metric("OTROS ESTADOS", formato_miles_punto(len(otros)))
        col5.metric("ATRASADAS", formato_miles_punto(total_atrasadas))

        st.markdown(f"### Detalle REGULARIZADAS en {calendar.month_name[mes]} {año}")
        if not df_mes.empty:
            resumen_dia = df_mes.groupby(df_mes['Fecha de cierre'].dt.day).size().reset_index(name='Cantidad')
            resumen_dia.columns = ['Día', 'Cantidad']
            st.dataframe(resumen_dia.set_index('Día'), use_container_width=True)
            st.success(f"Total regularizadas: {formato_miles_punto(total_reg)}")
        else:
            st.info("No hay regularizadas este mes.")

        st.markdown("### Resumen mensual de regularizadas")

        # --- Gráfico Altair interactivo en Detalle por Trabajador ---
        df_reg_historico = df_resp[
            (df_resp['ESTADO FINAL'] == 'REGULARIZADA') &
            (df_resp['Fecha de cierre'].notna())
        ].copy()
        df_reg_historico['Año'] = df_reg_historico['Fecha de cierre'].dt.year
        df_reg_historico['Mes'] = df_reg_historico['Fecha de cierre'].dt.month

        años = sorted(df_reg_historico['Año'].unique())
        todos_los_meses = pd.DataFrame([(a,m) for a in años for m in range(1,13)], columns=['Año', 'Mes'])

        resumen_mensual = df_reg_historico.groupby(['Año', 'Mes']).size().reset_index(name='Cantidad')
        resumen_mensual = pd.merge(todos_los_meses, resumen_mensual, on=['Año','Mes'], how='left').fillna(0)
        resumen_mensual['Cantidad'] = resumen_mensual['Cantidad'].astype(int)
        resumen_mensual['Mes_nombre'] = resumen_mensual['Mes'].apply(lambda x: calendar.month_name[x])

        meses_orden = list(calendar.month_name)[1:]  # Enero a Diciembre

        chart = (
            alt.Chart(resumen_mensual)
            .mark_bar()
            .encode(
                x=alt.X('Mes_nombre:N', sort=meses_orden, title='Mes'),
                y=alt.Y('Cantidad:Q', title='Cantidad de Regularizadas'),
                color=alt.Color('Año:N',
                                scale=alt.Scale(range=paleta_colores_anos),
                                legend=alt.Legend(title="Año")),
                tooltip=[
                    alt.Tooltip('Mes_nombre:N', title='Mes'),
                    alt.Tooltip('Año:N', title='Año'),
                    alt.Tooltip('Cantidad:Q', title='Cantidad')
                ]
            )
            .properties(
                width=700,
                height=400,
                title=f"Regularizadas mes a mes por año - {seleccionado}"
            )
            .interactive()
        )
        st.altair_chart(chart, use_container_width=True)

        st.markdown("### Detalle mensual de operaciones ATRASADAS (todo histórico)")
        if not atrasadas.empty:
            atrasadas_detalle = atrasadas.copy()
            atrasadas_detalle['Año'] = atrasadas_detalle['FECHA'].dt.year
            atrasadas_detalle['Mes'] = atrasadas_detalle['FECHA'].dt.month.apply(lambda x: calendar.month_name[x])
            resumen_atrasadas = atrasadas_detalle.groupby(['Año', 'Mes']).size().reset_index(name='Cantidad')
            st.dataframe(resumen_atrasadas, use_container_width=True)
        else:
            st.info("No hay operaciones atrasadas para este responsable.")

        st.markdown("### Detalle mensual de OTROS ESTADOS (todo histórico)")
        if not otros.empty:
            otros_detalle = otros.copy()
            otros_detalle['Año'] = otros_detalle['FECHA'].dt.year
            otros_detalle['Mes'] = otros_detalle['FECHA'].dt.month.apply(lambda x: calendar.month_name[x])
            resumen_otros = otros_detalle.groupby(['Año', 'Mes', 'ESTADO FINAL']).size().reset_index(name='Cantidad')
            st.dataframe(resumen_otros, use_container_width=True)
        else:
            st.info("No hay operaciones en otros estados para este responsable.")

except Exception as e:
    st.error(f"❌ Error al cargar el archivo: {e}")

