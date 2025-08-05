import streamlit as st
import sqlite3
import pandas as pd
import folium
from datetime import datetime
from folium.plugins import HeatMap
from streamlit_folium import st_folium

# Configuração do app
st.set_page_config(layout="wide", page_title="Monitor de Escorpiões")

# Conectar ao banco de dados
def get_data():
    conn = sqlite3.connect('scorpion_infestation.db')
    df = pd.read_sql_query("SELECT * FROM infestations", conn)
    conn.close()
    return df

# Criar mapa com os registros
def create_map(data):
    # Configuração básica do mapa
    mapa = folium.Map(location=[-19.0, -52.6], zoom_start=14)
    
    # Adicionar marcadores para cada registro
    for _, row in data.iterrows():
        folium.Marker(
            location=[row['latitude'], row['longitude']],
            popup=f"Nível: {row['infestation_level']}",
            icon=folium.Icon(
                color={'Baixo':'blue', 'Médio':'orange', 'Alto':'red'}.get(row['infestation_level'], 'gray'),
                icon='bug'
            )
        ).add_to(mapa)
    
    # Adicionar mapa de calor
    if not data.empty:
        heat_data = data.apply(lambda row: [
            row['latitude'], 
            row['longitude'], 
            {'Baixo':1, 'Médio':2, 'Alto':3}.get(row['infestation_level'], 0)
        ], axis=1).tolist()
        
        HeatMap(heat_data, radius=15).add_to(mapa)
    
    return mapa

# Interface principal
st.title("🦂 Meus Registros de Infestações")

# Carregar dados
registros = get_data()

if not registros.empty:
    # Mostrar estatísticas
    st.metric("Total de Registros", len(registros))
    
    # Mostrar o mapa
    st.subheader("Mapa de Ocorrências")
    mapa = create_map(registros)
    st_folium(mapa, width=700, height=500)
    
    # Mostrar últimos registros (opcional)
    with st.expander("Ver últimos registros"):
        st.dataframe(registros.sort_values('date', ascending=False).head(10))
else:
    st.warning("Nenhum registro encontrado no banco de dados.")

# Botão para atualizar os dados
if st.button("Atualizar Mapa"):
    registros = get_data()
    st.experimental_rerun()