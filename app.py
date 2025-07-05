import streamlit as st
import pandas as pd
import json

# Leer JSON
with open("config.json", "r") as f:
    config = json.load(f)

# Leer CSV desde URL
url_csv = config["dataSource"]["filename"]
df = pd.read_csv(url_csv)

# Filtrar sucursal si existe
sucursales_expand = config["slice"]["expands"]["rows"]
for item in sucursales_expand:
    for suc in item["tuple"]:
        suc_clean = suc.lower().split(".[")[1].replace("]", "")
        df = df[df["Sucursal"].str.lower() == suc_clean]

# Agrupación
agrupado = df.groupby(['Sucursal', 'Producto / Servicio + Variante', 'Mes']).agg({
    'Subtotal Neto': 'sum',
    'Subtotal Bruto': 'sum',
    'Margen Neto': 'sum',
    'Costo Neto': 'sum',
    'Impuestos': 'sum',
    'Cantidad': 'sum'
}).reset_index()

# Mostrar
st.title("Dashboard de Ventas")
st.dataframe(agrupado)
