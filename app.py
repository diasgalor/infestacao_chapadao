import streamlit as st
import sqlite3
import folium
import geopandas as gpd
import pandas as pd
import numpy as np
import rasterio
import ee
import geemap
from folium.plugins import HeatMap
from streamlit_folium import st_folium
from datetime import datetime
import os

# CSS para layout responsivo
st.markdown("""
    <style>
    .main .block-container {
        padding: 1rem;
        max-width: 100%;
    }
    .stForm {
        width: 100%;
        max-width: 600px;
        margin: auto;
    }
    .stTextInput, .stNumberInput, .stSelectbox {
        margin-bottom: 1rem;
    }
    .stDataFrame {
        width: 100%;
        overflow-x: auto;
    }
    @media (max-width: 600px) {
        .stNumberInput input, .stTextInput input {
            font-size: 16px;
        }
        .stSelectbox select {
            font-size: 16px;
        }
        h1, h2, h3 {
            font-size: 1.5rem !important;
        }
    }
    </style>
""", unsafe_allow_html=True)

# Função para inicializar o GEE
def initialize_gee():
    try:
        ee.Initialize()
        return True
    except Exception as e:
        st.error(f"Erro ao inicializar o GEE: {str(e)}")
        return False

# Função para criar o banco de dados e a tabela
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

# Função para inserir dados no banco
def insert_infestation(latitude, longitude, infestation_level):
    conn = sqlite3.connect('scorpion_infestation.db')
    c = conn.cursor()
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('''
        INSERT INTO infestations (latitude, longitude, infestation_level, date)
        VALUES (?, ?, ?, ?)
    ''', (latitude, longitude, infestation_level, date))
    conn.commit()
    conn.close()

# Função para recuperar dados do banco
def get_infestations():
    conn = sqlite3.connect('scorpion_infestation.db')
    df = pd.read_sql_query("SELECT * FROM infestations", conn)
    conn.close()
    return df

# Função para obter a imagem específica com o índice personalizado
def get_sentinel2_indices():
    bbox = [-52.65, -19.05, -52.55, -18.95]  # Chapadão do Sul
    geometry = ee.Geometry.Rectangle(bbox)
    
    # Carregar a imagem específica
    image_id = 'COPERNICUS/S2_SR/S2B_MSIL2A_20250723T133839_N0511_R124_T22KCE_20250723T185733'
    image = ee.Image(image_id).clip(geometry)
    
    # Calcular NDVI e NDBI
    ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
    ndbi = image.normalizedDifference(['B11', 'B8']).rename('NDBI')
    
    # Índice personalizado (adaptado do script do Carlos Bentes)
    veg_th = 0.4
    R = image.select('B4').multiply(2.5)
    G = image.select('B3').multiply(2.5)
    B = image.select('B2').multiply(2.5)
    Y = R.multiply(0.2).add(G.multiply(0.7)).add(B.multiply(0.1))
    rgb_image = Y.addBands([Y, Y]).rename(['R', 'G', 'B'])
    veg_mask = ndvi.gte(veg_th)
    rgb_veg = Y.multiply(0.1).addBands([Y.multiply(1.8), Y.multiply(0.1)]).rename(['R', 'G', 'B'])
    custom_rgb = rgb_image.where(veg_mask, rgb_veg)
    
    # Exportar NDVI, NDBI e imagem RGB personalizada
    ndvi_file = 'ndvi_chapadao.tif'
    ndbi_file = 'ndbi_chapadao.tif'
    rgb_file = 'custom_rgb_chapadao.tif'
    if not os.path.exists(ndvi_file):
        geemap.ee_export_image(ndvi, filename=ndvi_file, scale=10, region=geometry)
    if not os.path.exists(ndbi_file):
        geemap.ee_export_image(ndbi, filename=ndbi_file, scale=10, region=geometry)
    if not os.path.exists(rgb_file):
        geemap.ee_export_image(custom_rgb, filename=rgb_file, scale=10, region=geometry)
    
    return ndvi_file, ndbi_file, rgb_file

# Função para extrair valores NDVI e NDBI
def get_indices_values(ndvi_path, ndbi_path, lon, lat):
    ndvi_value = 0.5
    ndbi_value = 0.0
    try:
        with rasterio.open(ndvi_path) as src:
            row, col = src.index(lon, lat)
            ndvi_value = src.read(1)[row, col]
            ndvi_value = ndvi_value if -1 <= ndvi_value <= 1 else 0.5
        with rasterio.open(ndbi_path) as src:
            row, col = src.index(lon, lat)
            ndbi_value = src.read(1)[row, col]
            ndbi_value = ndbi_value if -1 <= ndbi_value <= 1 else 0.0
    except:
        pass
    return ndvi_value, ndbi_value

# Função para calcular o IPVU
def calculate_ipvu(infestations_gdf, ndvi_path, ndbi_path):
    ipvu_data = []
    for idx, inf in infestations_gdf.iterrows():
        ndvi, ndbi = get_indices_values(ndvi_path, ndbi_path, inf.longitude, inf.latitude)
        if ndvi > 0.6 and ndbi < -0.1:
            classification = "Arborizada"
            ipvu = ndvi * 3
        elif ndbi > 0.1 and ndvi < 0.3:
            classification = "Edificada"
            ipvu = ndvi * 1
        else:
            classification = "Mista"
            ipvu = ndvi * 2
        ipvu_data.append({
            'Latitude': inf.latitude,
            'Longitude': inf.longitude,
            'NDVI': round(ndvi, 2),
            'NDBI': round(ndbi, 2),
            'IPVU': round(ipvu, 2),
            'Classificação': classification
        })
    return pd.DataFrame(ipvu_data)

# Função para criar o mapa com a imagem RGB personalizada e mapa de calor
def create_map(infestations_df, rgb_path):
    all_points = []
    if not infestations_df.empty:
        all_points.extend([(row.latitude, row.longitude) for _, row in infestations_df.iterrows()])
    
    with rasterio.open(rgb_path) as src:
        bounds = src.bounds
        all_points.extend([(bounds.bottom, bounds.left), (bounds.top, bounds.right)])
    
    if not all_points:
        m = folium.Map(location=[-19.0, -52.6], zoom_start=12)
    else:
        lats, lons = zip(*all_points)
        bounds = [[min(lats), min(lons)], [max(lats), max(lons)]]
        m = folium.Map(location=[(min(lats) + max(lats)) / 2, (min(lons) + max(lons)) / 2], zoom_start=12)
        m.fit_bounds(bounds)
    
    # Adicionar camada RGB personalizada
    with rasterio.open(rgb_path) as src:
        rgb_data = src.read([1, 2, 3])  # Ler bandas R, G, B
        rgb_data = np.clip(rgb_data, 0, 1)  # Normalizar para 0-1
        folium.raster_layers.ImageOverlay(
            image=rgb_data,
            bounds=[[bounds.bottom, bounds.left], [bounds.top, bounds.right]],
            opacity=0.8
        ).add_to(m)
    
    # Adicionar mapa de calor
    if not infestations_df.empty:
        heat_data = [
            [row.latitude, row.longitude, {'Baixo': 1, 'Médio': 2, 'Alto': 3}[row.infestation_level]]
            for _, row in infestations_df.iterrows()
        ]
        HeatMap(heat_data, radius=15, blur=20, max_zoom=18).add_to(m)
    
    # Adicionar legenda ao mapa
    legend_html = """
    <div style="position: fixed; bottom: 50px; left: 50px; z-index: 1000; padding: 10px; background-color: white; border: 2px solid grey; border-radius: 5px;">
        <h4>Níveis de Infestação</h4>
        <p><i style="background: blue; width: 20px; height: 20px; display: inline-block;"></i> Baixo: 0-1 escorpião</p>
        <p><i style="background: yellow; width: 20px; height: 20px; display: inline-block;"></i> Médio: 2 escorpiões</p>
        <p><i style="background: red; width: 20px; height: 20px; display: inline-block;"></i> Alto: 2 escorpiões com risco de colônia</p>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    return m

# Inicializar o GEE
if initialize_gee():
    ndvi_path, ndbi_path, rgb_path = get_sentinel2_indices()
else:
    ndvi_path, ndbi_path, rgb_path = None, None, None
    st.error("Falha ao inicializar o GEE. Verifique a autenticação ou conexão.")

# Interface do Streamlit
st.title("Monitoramento de Infestações de Escorpião")

# Explicação da legenda
with st.container():
    st.subheader("Legenda dos Níveis de Infestação")
    st.markdown("""
    - **Baixo (Azul)**: 0-1 escorpião observado. Indica risco baixo, possivelmente um escorpião isolado.
    - **Médio (Amarelo)**: 2 escorpiões observados no mesmo local ou em ocasiões próximas. Sugere risco moderado e ambiente favorável.
    - **Alto (Vermelho)**: 2 escorpiões com sinais de colônia (ex.: ambiente úmido ou vegetado). Requer ação imediata.
    """)

# Formulário para entrada de dados
with st.container():
    st.header("Registrar Infestação")
    with st.form(key='infestation_form'):
        col1, col2 = st.columns([1, 1])
        with col1:
            latitude = st.number_input("Latitude", min_value=-90.0, max_value=90.0, step=0.0001, format="%.6f", value=-19.0)
        with col2:
            longitude = st.number_input("Longitude", min_value=-180.0, max_value=180.0, step=0.0001, format="%.6f", value=-52.6)
        infestation_level = st.selectbox("Nível de Infestação", ["Baixo", "Médio", "Alto"])
        submit_button = st.form_submit_button(label="Registrar")

        if submit_button:
            if latitude and longitude:
                insert_infestation(latitude, longitude, infestation_level)
                st.success("Infestação registrada com sucesso!")
            else:
                st.error("Preencha todos os campos!")

# Inicializar o banco de dados
init_db()

# Exibir mapa com infestações e camada RGB personalizada
with st.container():
    st.header("Mapa de Calor de Infestações com Imagem Personalizada")
    infestations_df = get_infestations()

    if not infestations_df.empty and ndvi_path and ndbi_path and rgb_path:
        infestations_gdf = gpd.GeoDataFrame(
            infestations_df,
            geometry=gpd.points_from_xy(infestations_df.longitude, infestations_df.latitude),
            crs="EPSG:4326"
        )
        
        st.subheader("Índice de Proximidade à Vegetação Urbana (IPVU)")
        ipvu_df = calculate_ipvu(infestations_gdf, ndvi_path, ndbi_path)
        st.dataframe(ipvu_df)

        m = create_map(infestations_df, rgb_path)
        st_folium(m, width=700, height=500, returned_objects=[])
    else:
        st.write("Nenhuma infestação registrada ou dados de imagem não disponíveis.")