import streamlit as st
import sqlite3
import pandas as pd
import folium
import geopandas as gpd
from datetime import datetime
from folium.plugins import HeatMap
from streamlit_folium import st_folium

# -------- CONFIGURAÇÃO INICIAL --------
st.set_page_config(layout="wide")
st.title("🦂 Monitoramento de Infestações de Escorpião")

# -------- BANCO DE DADOS --------
def init_db():
    conn = sqlite3.connect('scorpion_infestation.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS infestations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            latitude REAL,
            longitude REAL,
            infestation_level TEXT,
            date TEXT
        )
    ''')
    conn.commit()
    conn.close()

def insert_infestation(lat, lon, level):
    conn = sqlite3.connect('scorpion_infestation.db')
    c = conn.cursor()
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('INSERT INTO infestations (latitude, longitude, infestation_level, date) VALUES (?, ?, ?, ?)',
              (lat, lon, level, date))
    conn.commit()
    conn.close()

def get_infestations():
    conn = sqlite3.connect('scorpion_infestation.db')
    df = pd.read_sql_query("SELECT * FROM infestations", conn)
    conn.close()
    return df

# -------- MAPA COM FOLIUM --------
def create_map(df):
    # Mapa base com tiles do OpenStreetMap
    m = folium.Map(location=[-19.0, -52.6], 
                  zoom_start=13,
                  tiles='OpenStreetMap')
    
    # Adiciona mapa de calor se houver dados
    if not df.empty:
        heat_data = [
            [row.latitude, row.longitude, {"Baixo": 1, "Médio": 2, "Alto": 3}[row.infestation_level]]
            for _, row in df.iterrows()
        ]
        HeatMap(heat_data, radius=15, blur=20).add_to(m)
    
    # Adiciona marcadores para cada ponto
    for _, row in df.iterrows():
        folium.Marker(
            location=[row.latitude, row.longitude],
            popup=f"Nível: {row.infestation_level}",
            icon=folium.Icon(
                color={'Baixo': 'blue', 'Médio': 'orange', 'Alto': 'red'}[row.infestation_level],
                icon='bug'
            )
        ).add_to(m)
    
    # Legenda
    legend = """
    <div style="position: fixed; bottom: 50px; left: 50px; z-index: 9999; background-color: white; padding: 10px; border: 1px solid black;">
        <b>Legenda:</b><br>
        <span style="color: blue;">●</span> Baixo<br>
        <span style="color: orange;">●</span> Médio<br>
        <span style="color: red;">●</span> Alto
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend))
    
    return m

# -------- INTERFACE DO USUÁRIO --------
init_db()

# Seção de legenda
with st.expander("🗺️ Sobre os Níveis de Infestação"):
    st.markdown("""
    - **Baixo (Azul)**: 0-1 escorpião observado
    - **Médio (Laranja)**: 2 escorpiões em sequência
    - **Alto (Vermelho)**: Colônia possível (úmido/vegetado)
    """)

# Formulário para novos registros
with st.form("infestation_form"):
    st.subheader("📍 Registrar Nova Infestação")
    col1, col2 = st.columns(2)
    lat = col1.number_input("Latitude", value=-19.00, format="%.6f")
    lon = col2.number_input("Longitude", value=-52.60, format="%.6f")
    level = st.selectbox("Nível de Infestação", ["Baixo", "Médio", "Alto"])
    submitted = st.form_submit_button("Registrar")
    if submitted:
        insert_infestation(lat, lon, level)
        st.success("Infestação registrada com sucesso!")

# Exibição dos dados
df = get_infestations()
if not df.empty:
    # Mostra tabela com os registros
    st.subheader("📋 Registros de Infestações")
    st.dataframe(df[['latitude', 'longitude', 'infestation_level', 'date']], 
                use_container_width=True)
    
    # Mostra o mapa
    st.subheader("🗺️ Mapa de Infestações")
    map_ = create_map(df)
    st_folium(map_, height=500, width=700)
else:
    st.info("Nenhuma infestação registrada ainda. Use o formulário acima para adicionar registros.")