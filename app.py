import streamlit as st
import sqlite3
import pandas as pd
import folium
from datetime import datetime
from folium.plugins import HeatMap
from streamlit_folium import st_folium

# Configuração inicial mobile-friendly
st.set_page_config(
    layout="wide",
    initial_sidebar_state="collapsed",
    page_title="Monitor Escorpiões"
)

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
            date TEXT,
            observacoes TEXT
        )
    ''')
    conn.commit()
    conn.close()

def insert_infestation(lat, lon, level, obs=""):
    conn = sqlite3.connect('scorpion_infestation.db')
    c = conn.cursor()
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('''INSERT INTO infestations 
                (latitude, longitude, infestation_level, date, observacoes) 
                VALUES (?, ?, ?, ?, ?)''',
              (lat, lon, level, date, obs))
    conn.commit()
    conn.close()

def get_infestations():
    conn = sqlite3.connect('scorpion_infestation.db')
    df = pd.read_sql_query("SELECT * FROM infestations", conn)
    conn.close()
    return df

# -------- MAPA INTERATIVO --------
def create_map(df):
    # Configuração mobile-friendly
    m = folium.Map(
        location=[-19.0, -52.6],
        zoom_start=14,
        tiles='CartoDB positron',
        control_scale=True,
        prefer_canvas=True  # Melhor performance para mobile
    )
    
    # Mapa de calor
    if not df.empty:
        heat_data = [
            [row.latitude, row.longitude, {"Baixo": 1, "Médio": 2, "Alto": 3}[row.infestation_level]]
            for _, row in df.iterrows()
        ]
        HeatMap(
            heat_data,
            radius=12,
            blur=15,
            min_opacity=0.5,
            max_zoom=16
        ).add_to(m)
    
    # Marcadores individuais
    for _, row in df.iterrows():
        popup_content = f"""
        <b>Nível:</b> {row.infestation_level}<br>
        <b>Data:</b> {row.date}<br>
        <small>{row.observacoes or 'Sem observações'}</small>
        """
        
        folium.Marker(
            location=[row.latitude, row.longitude],
            popup=folium.Popup(popup_content, max_width=250),
            icon=folium.Icon(
                color={'Baixo': 'blue', 'Médio': 'orange', 'Alto': 'red'}[row.infestation_level],
                icon='bug',
                prefix='fa'
            )
        ).add_to(m)
    
    # Legenda mobile-friendly
    legend_html = '''
    <div style="
        position: fixed; 
        bottom: 20px; 
        left: 10px; 
        z-index: 1000;
        background-color: white; 
        padding: 8px;
        border-radius: 5px;
        box-shadow: 0 0 5px rgba(0,0,0,0.2);
        font-size: 12px;
    ">
        <b>Legenda:</b><br>
        <span style="color: blue;">●</span> Baixo<br>
        <span style="color: orange;">●</span> Médio<br>
        <span style="color: red;">●</span> Alto
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    
    return m

# -------- INTERFACE MOBILE-FRIENDLY --------
init_db()

# CSS para melhorar a experiência mobile
st.markdown("""
    <style>
        .stForm {
            border: 1px solid #eee;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 20px;
        }
        .stButton>button {
            width: 100%;
        }
        .stSelectbox, .stNumberInput {
            margin-bottom: 10px;
        }
    </style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
    <h1 style='text-align: center; margin-bottom: 20px;'>
        🦂 Monitor Escorpiões
    </h1>
""", unsafe_allow_html=True)

# Formulário de registro
with st.form("infestation_form"):
    st.markdown("### 📍 Registrar Nova Ocorrência")
    
    # Layout responsivo
    col1, col2 = st.columns(2)
    with col1:
        lat = st.number_input("Latitude", value=-19.00, format="%.6f", key="lat")
    with col2:
        lon = st.number_input("Longitude", value=-52.60, format="%.6f", key="lon")
    
    level = st.selectbox("Nível de Risco", ["Baixo", "Médio", "Alto"])
    obs = st.text_area("Observações (opcional)", max_chars=100)
    
    submitted = st.form_submit_button("Salvar Registro")
    if submitted:
        insert_infestation(lat, lon, level, obs)
        st.success("Registro salvo com sucesso!")
        st.balloons()

# Exibição do mapa
# Substitua esta parte do código:
def get_infestations():
    conn = sqlite3.connect('scorpion_infestation.db')
    df = pd.read_sql_query("SELECT * FROM infestations", conn)
    conn.close()
    
    # Verificação segura das colunas
    required_columns = ['latitude', 'longitude', 'infestation_level', 'date']
    for col in required_columns:
        if col not in df.columns:
            df[col] = None  # Ou valor padrão apropriado
            
    return df

# E na função create_map:
def create_map(df):
    # Verificação adicional antes de acessar as colunas
    if df.empty:
        m = folium.Map(location=[-19.0, -52.6], zoom_start=13)
        return m
    
    try:
        heat_data = [
            [row['latitude'], row['longitude'], 
             {"Baixo": 1, "Médio": 2, "Alto": 3}[row['infestation_level']]]
            for _, row in df.iterrows()
        ]
    except KeyError as e:
        st.error(f"Erro nas colunas do DataFrame: {str(e)}")
        m = folium.Map(location=[-19.0, -52.6], zoom_start=13)
        return m

# Rodapé informativo
st.markdown("---")
st.markdown("""
    <div style="text-align: center; font-size: 0.9em; color: #666;">
        <p>Níveis de risco:</p>
        <p><b>Baixo</b>: 0-1 escorpião | <b>Médio</b>: 2 escorpiões | <b>Alto</b>: Colônia</p>
    </div>
""", unsafe_allow_html=True)