import streamlit as st
import sqlite3
import folium
import geopandas as gpd
import pandas as pd
from streamlit_folium import st_folium
from datetime import datetime
import random

# Função para criar o banco de dados e a tabela
def init_db():
    conn = sqlite3.connect('scorpion_infestation.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS infestations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            address TEXT,
            latitude REAL,
            longitude REAL,
            infestation_level TEXT,
            date TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Função para inserir dados no banco
def insert_infestation(address, latitude, longitude, infestation_level):
    conn = sqlite3.connect('scorpion_infestation.db')
    c = conn.cursor()
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('''
        INSERT INTO infestations (address, latitude, longitude, infestation_level, date)
        VALUES (?, ?, ?, ?, ?)
    ''', (address, latitude, longitude, infestation_level, date))
    conn.commit()
    conn.close()

# Função para recuperar dados do banco
def get_infestations():
    conn = sqlite3.connect('scorpion_infestation.db')
    df = pd.read_sql_query("SELECT * FROM infestations", conn)
    conn.close()
    return df

# Função para criar um GeoDataFrame simulado de áreas verdes
def get_vegetation_data():
    # Dados fictícios de áreas verdes (florestas, córregos)
    vegetation = {
        'name': ['Floresta 1', 'Córrego 1', 'Floresta 2'],
        'geometry': [
            gpd.points_from_xy([ -46.65], [-23.55])[0],  # Floresta 1
            gpd.points_from_xy([ -46.66], [-23.56])[0],  # Córrego 1
            gpd.points_from_xy([ -46.64], [-23.54])[0]   # Floresta 2
        ],
        'type': ['forest', 'stream', 'forest']
    }
    return gpd.GeoDataFrame(vegetation, crs="EPSG:4326")

# Função para criar o mapa
def create_map(infestations_df, vegetation_gdf):
    # Centro do mapa (exemplo: São Paulo)
    m = folium.Map(location=[-23.55, -46.65], zoom_start=12)

    # Adicionar pontos de infestação
    for _, row in infestations_df.iterrows():
        folium.Marker(
            location=[row['latitude'], row['longitude']],
            popup=f"Endereço: {row['address']}<br>Nível: {row['infestation_level']}<br>Data: {row['date']}",
            icon=folium.Icon(color='red' if row['infestation_level'] == 'Alto' else 'orange' if row['infestation_level'] == 'Médio' else 'green')
        ).add_to(m)

    # Adicionar áreas verdes
    for _, row in vegetation_gdf.iterrows():
        folium.Marker(
            location=[row.geometry.y, row.geometry.x],
            popup=f"Tipo: {row['type']}<br>Nome: {row['name']}",
            icon=folium.Icon(color='green', icon='tree')
        ).add_to(m)

    return m

# Inicializar o banco de dados
init_db()

# Interface do Streamlit
st.title("Monitoramento de Infestações de Escorpião")

# Formulário para entrada de dados
st.header("Registrar Infestação")
with st.form(key='infestation_form'):
    address = st.text_input("Endereço")
    latitude = st.number_input("Latitude", min_value=-90.0, max_value=90.0, step=0.0001, format="%.6f")
    longitude = st.number_input("Longitude", min_value=-180.0, max_value=180.0, step=0.0001, format="%.6f")
    infestation_level = st.selectbox("Nível de Infestação", ["Baixo", "Médio", "Alto"])
    submit_button = st.form_submit_button(label="Registrar")

    if submit_button:
        if address and latitude and longitude:
            insert_infestation(address, latitude, longitude, infestation_level)
            st.success("Infestação registrada com sucesso!")
        else:
            st.error("Preencha todos os campos!")

# Exibir mapa com infestações e vegetação
st.header("Mapa de Infestações e Áreas Verdes")
infestations_df = get_infestations()
vegetation_gdf = get_vegetation_data()

if not infestations_df.empty:
    # Análise de proximidade com áreas verdes
    infestations_gdf = gpd.GeoDataFrame(
        infestations_df,
        geometry=gpd.points_from_xy(infestations_df.longitude, infestations_df.latitude),
        crs="EPSG:4326"
    )
    st.write("Análise: Infestações próximas a áreas verdes ou úmidas")
    for idx, inf in infestations_gdf.iterrows():
        distances = vegetation_gdf.geometry.distance(inf.geometry)
        min_distance = distances.min()
        closest_veg = vegetation_gdf.iloc[distances.idxmin()]
        if min_distance < 0.01:  # Aproximadamente 1km em graus
            st.write(f"Infestação em {inf.address}: Próxima a {closest_veg['name']} ({closest_veg['type']}) - Distância: {min_distance*111:.2f} km")

    # Exibir o mapa
    m = create_map(infestations_df, vegetation_gdf)
    st_folium(m, width=700, height=500)
else:
    st.write("Nenhuma infestação registrada ainda.")