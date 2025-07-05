import streamlit as st
import pandas as pd
import json

# --- Cargar configuración desde report.json ---
with open("report.json", "r", encoding="utf-8") as f:
    config = json.load(f)

# --- Obtener URL del CSV ---
csv_url = config["dataSource"]["filename"]

# --- Cargar el CSV ---
@st.cache_data
def cargar_datos(url):
    return pd.read_csv(url)

df = cargar_datos(csv_url)

# --- Filtro de sucursal según config ---
expands = config["slice"]["expands"]["rows"]
for item in expands:
    for value in item["tuple"]:
        sucursal = value.split(".[")[1].replace("]", "").strip().lower()
        df = df[df["Sucursal"].str.lower() == sucursal]

# --- Agrupar según configuración ---
agrupado = df.groupby([
    "Sucursal", 
    "Producto / Servicio + Variante", 
    "Mes"
]).agg({
    "Subtotal Neto": "sum",
    "Subtotal Bruto": "sum",
    "Margen Neto": "sum",
    "Costo Neto": "sum",
    "Impuestos": "sum",
    "Cantidad": "sum"
}).reset_index()

# --- Mostrar en Streamlit ---
st.title("Dashboard de Ventas")
st.dataframe(agrupado)
