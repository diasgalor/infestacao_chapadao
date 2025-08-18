import os
import re
from datetime import datetime
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(layout="wide", page_title="Dashboard - Baterias e OS não processadas")
st.title("Dashboard: Trocas de Baterias / OS não processadas")

# --- Estilo escuro otimizado ---
st.markdown(
    """
    <style>
    /* Global styles */
    .stApp {
        background: #0b0b0b;
        color: #e6e6e6;
        font-family: 'Inter', sans-serif;
    }
    /* Card styling */
    .card {
        background: rgba(20, 20, 20, 0.95);
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.5);
        border: 1px solid rgba(255, 255, 255, 0.05);
        margin-bottom: 20px;
    }
    /* DataFrame styling */
    .stDataFrame, .stDataFrame table {
        background: transparent !important;
        color: #e6e6e6 !important;
        border: none !important;
    }
    .stDataFrame th, .stDataFrame td {
        background: transparent !important;
        color: #e6e6e6 !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        font-family: 'Inter', sans-serif;
        font-size: 14px;
    }
    .stDataFrame th {
        background: rgba(255, 255, 255, 0.05) !important;
        font-weight: 600;
    }
    /* Metrics and text */
    .metric, .stMetric, .stMarkdown, p, h1, h2, h3, h4, h5, h6 {
        color: #e6e6e6 !important;
        font-family: 'Inter', sans-serif;
    }
    /* Buttons */
    .stButton > button {
        background: #00cc96;
        color: #0b0b0b;
        border: none;
        border-radius: 8px;
        padding: 8px 16px;
        font-family: 'Inter', sans-serif;
        font-weight: 500;
        transition: background 0.2s;
    }
    .stButton > button:hover {
        background: #00e6a8;
        color: #0b0b0b;
    }
    /* Text inputs and areas */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea {
        background: rgba(255, 255, 255, 0.05);
        color: #e6e6e6;
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        font-family: 'Inter', sans-serif;
    }
    /* Sidebar */
    .css-1d391kg, .stSidebar {
        background: #0b0b0b !important;
        color: #e6e6e6 !important;
    }
    .stSidebar h2, .stSidebar label {
        color: #e6e6e6 !important;
        font-family: 'Inter', sans-serif;
    }
    /* Tabs */
    .stTabs [role="tab"] {
        color: #e6e6e6;
        font-family: 'Inter', sans-serif;
        border-bottom: 2px solid transparent;
    }
    .stTabs [role="tab"][aria-selected="true"] {
        color: #00cc96;
        border-bottom: 2px solid #00cc96;
    }
    /* Plotly chart container */
    .js-plotly-plot, .plotly {
        background: transparent !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Pastas padrão ---
BASE_DIR = Path.cwd()
PASTA_DADOS = BASE_DIR / "dados"
PASTA_SAIDA = BASE_DIR / "saida"
PASTA_DADOS.mkdir(exist_ok=True)
PASTA_SAIDA.mkdir(exist_ok=True)

DEFAULT_REPORT = str(PASTA_SAIDA / "relatorio_tecnico_simplificado.xlsx")
STATUS_REPORT = str(PASTA_SAIDA / "relatorio_status.xlsx")

# --- Carregar relatório (upload ou default) ---
df = None
uploaded = st.file_uploader("Carregar relatório (Excel .xlsx) ou CSV", type=["xlsx", "csv"])
if uploaded:
    try:
        uploaded.seek(0)
    except Exception:
        pass
    try:
        df = pd.read_excel(uploaded)
        st.write("Colunas no arquivo carregado:", df.columns.tolist())  # Diagnóstico
    except Exception:
        try:
            uploaded.seek(0)
        except Exception:
            pass
        for enc in ("utf-8", "latin1", "cp1252"):
            try:
                df = pd.read_csv(uploaded, encoding=enc)
                st.write("Colunas no arquivo carregado:", df.columns.tolist())  # Diagnóstico
                break
            except Exception:
                continue
else:
    if os.path.exists(DEFAULT_REPORT):
        try:
            df = pd.read_excel(DEFAULT_REPORT)
            st.write("Colunas no arquivo padrão:", df.columns.tolist())  # Diagnóstico
        except Exception:
            df = None

if df is None:
    df = pd.DataFrame(columns=["NUMERO_LAUDO", "DATA", "FROTA", "PARECER", "ANALISE", "CONCLUSAO"])
    st.warning("Nenhum relatório automático carregado — usando DataFrame vazio. Use 'Adicionar OS manual' para incluir registros.")

# --- Garantir colunas e campos derivados ---
df.columns = [c.strip().upper() for c in df.columns]
for c in ["NUMERO_LAUDO", "DATA", "FROTA", "PARECER", "ANALISE", "CONCLUSAO"]:
    if c not in df.columns:
        df[c] = ""

df["DATA_DT"] = pd.to_datetime(df["DATA"].astype(str), dayfirst=True, errors="coerce")
df["TEXTO_COMBINADO"] = (
    df["PARECER"].fillna("").astype(str) + " " +
    df["ANALISE"].fillna("").astype(str) + " " +
    df["CONCLUSAO"].fillna("").astype(str)
).str.upper()

# --- Detecção por palavras-chave (sidebar) ---
st.sidebar.header("Configurações de detecção")
keywords_bateria = st.sidebar.text_area("Palavras-chave para 'bateria' (vírgula)", value="BATERIA,BATERIAS,BATT").upper().split(",")
keywords_troca = st.sidebar.text_area("Palavras-chave para 'troca' (vírgula)", value="TROCA,SUBSTITUI,SUBSTITUICAO,TROCADO,TROCAR,INSTALADO").upper().split(",")

pat_bat = re.compile(r"\b(" + "|".join([re.escape(k.strip()) for k in keywords_bateria if k.strip()]) + r")\b") if any(k.strip() for k in keywords_bateria) else None
pat_troca = re.compile(r"\b(" + "|".join([re.escape(k.strip()) for k in keywords_troca if k.strip()]) + r")\b") if any(k.strip() for k in keywords_troca) else None

df["IS_BATERIA"] = df["TEXTO_COMBINADO"].apply(lambda s: bool(pat_bat.search(s)) if pat_bat else False)
df["IS_TROCA_BATERIA"] = df["TEXTO_COMBINADO"].apply(lambda s: bool(pat_bat.search(s) and pat_troca.search(s)) if (pat_bat and pat_troca) else False)

# Log para verificar detecção
st.write("Registros com IS_TROCA_BATERIA = True:", df[df["IS_TROCA_BATERIA"]][["NUMERO_LAUDO", "FROTA", "TEXTO_COMBINADO"]])

# --- Pré-computos reutilizáveis ---
pdf_count = len(list(PASTA_DADOS.glob("*.pdf")))
exchanges = df[df["IS_TROCA_BATERIA"]].copy()

# Verificar e garantir a coluna "FROTA" em exchanges
if "FROTA" not in exchanges.columns:
    st.error("A coluna 'FROTA' não foi encontrada no DataFrame de trocas. Verifique o arquivo de entrada.")
    exchanges["FROTA"] = ""  # Adiciona coluna vazia para evitar falhas subsequentes
else:
    exchanges["FROTA"] = exchanges["FROTA"].astype(str)

# Continuação do processamento de DATA_DT
if "DATA_DT" in exchanges.columns:
    exchanges["DATA_DT"] = pd.to_datetime(exchanges["DATA_DT"], dayfirst=True, errors="coerce")
elif "DATA" in exchanges.columns:
    exchanges["DATA_DT"] = pd.to_datetime(exchanges["DATA"].astype(str), dayfirst=True, errors="coerce")
else:
    exchanges["DATA_DT"] = pd.NaT

# Log para verificar exchanges
st.write("Conteúdo de exchanges:", exchanges[["NUMERO_LAUDO", "FROTA", "PARECER", "IS_TROCA_BATERIA"]])

# Vida útil: últimos registros por frota -> days remaining
if not exchanges.empty:
    last_troca = exchanges.groupby("FROTA", as_index=False)["DATA_DT"].max()
    last_troca["EXPECTED_END"] = last_troca["DATA_DT"] + pd.DateOffset(months=12)
    today = pd.Timestamp(datetime.utcnow().date())
    last_troca["DAYS_SINCE_TROCA"] = (today - last_troca["DATA_DT"]).dt.days
    last_troca["DAYS_TOTAL_EXPECTED"] = (last_troca["EXPECTED_END"] - last_troca["DATA_DT"]).dt.days
    last_troca["DAYS_REMAINING"] = (last_troca["EXPECTED_END"] - today).dt.days
    last_troca["PCT_ELAPSED"] = (last_troca["DAYS_SINCE_TROCA"] / last_troca["DAYS_TOTAL_EXPECTED"]).clip(0,1)
else:
    last_troca = pd.DataFrame(columns=["FROTA","DATA_DT","EXPECTED_END","DAYS_SINCE_TROCA","DAYS_TOTAL_EXPECTED","DAYS_REMAINING","PCT_ELAPSED"])

# --- Abas: tabelas | gráficos | adicionar OS ---
tabs = st.tabs(["Tabelas", "Gráficos", "Adicionar OS manual"])

# --- TAB: Tabelas ---
with tabs[0]:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Tabelas")
    st.write("Relatório completo (fonte atual em memória):")
    st.dataframe(df.reset_index(drop=True), use_container_width=True)
    st.write("Registros detectados como troca de bateria:")
    st.dataframe(exchanges[["NUMERO_LAUDO","DATA","FROTA","PARECER","ANALISE","CONCLUSAO","DATA_DT"]].reset_index(drop=True), use_container_width=True)
    manual_csv = PASTA_SAIDA / "manual_additions.csv"
    if manual_csv.exists():
        st.write("Adições manuais (histórico):")
        try:
            hist = pd.read_csv(manual_csv, encoding="utf-8-sig")
            st.dataframe(hist, use_container_width=True)
            if st.button("Exportar histórico manual (.csv)"):
                outp = PASTA_SAIDA / "manual_additions_export.csv"
                hist.to_csv(outp, index=False, encoding="utf-8-sig")
                st.success(f"Exportado: {outp}")
        except Exception as e:
            st.error(f"Erro lendo histórico manual: {e}")
    st.write("PDFs em pasta 'dados' que não aparecem no relatório (por NUMERO_LAUDO):")
    arquivos_dados = sorted([f.name for f in PASTA_DADOS.glob("*.pdf")])
    laudos = df["NUMERO_LAUDO"].astype(str).unique().tolist()
    nao_listados = [a for a in arquivos_dados if not any(str(l) in a for l in laudos)]
    st.dataframe(pd.DataFrame({"arquivo": nao_listados}), use_container_width=True)
    if st.button("Exportar lista de PDFs possivelmente não processados"):
        outp = PASTA_SAIDA / "pdfs_possiveis_nao_processados.csv"
        pd.DataFrame({"arquivo": nao_listados}).to_csv(outp, index=False, encoding="utf-8-sig")
        st.success(f"Gerado: {outp}")
    st.markdown('</div>', unsafe_allow_html=True)

# --- TAB: Gráficos ---
with tabs[1]:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Gráficos")
    # Cores consistentes
    accent = "#00cc96"
    font_color = "#e6e6e6"
    bg_plot = "rgba(0,0,0,0)"  # Transparent to blend with card
    # Top frotas por número de trocas
    st.write("Top frotas por número de trocas")
    if not exchanges.empty:
        summary_cnt = exchanges.groupby("FROTA").size().reset_index(name="count").sort_values("count", ascending=False)
        top30 = summary_cnt.head(30).copy()
        fig_bar = px.bar(top30, x="FROTA", y="count", template="plotly_dark", color_discrete_sequence=[accent])
        fig_bar.update_layout(
            plot_bgcolor=bg_plot,
            paper_bgcolor=bg_plot,
            font_color=font_color,
            font_family="'Inter', sans-serif",
            xaxis_title="Frota",
            yaxis_title="Número de trocas",
            xaxis=dict(tickfont=dict(color=font_color), title_font=dict(color=font_color)),
            yaxis=dict(tickfont=dict(color=font_color), title_font=dict(color=font_color))
        )
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("Sem dados para este gráfico.")

    st.write("Distribuição dos intervalos entre trocas (dias)")
    if not exchanges.empty:
        def add_intervals(g):
            g = g.sort_values("DATA_DT")
            g["PREV_DATE"] = g["DATA_DT"].shift(1)
            g["DIAS_DESDE_ULTIMA"] = (g["DATA_DT"] - g["PREV_DATE"]).dt.days
            return g
        exch_with_intervals = exchanges.groupby("FROTA", group_keys=False).apply(add_intervals)
        if not exch_with_intervals["DIAS_DESDE_ULTIMA"].dropna().empty:
            fig_hist = px.histogram(
                exch_with_intervals.dropna(subset=["DIAS_DESDE_ULTIMA"]),
                x="DIAS_DESDE_ULTIMA",
                nbins=30,
                template="plotly_dark",
                color_discrete_sequence=[accent]
            )
            fig_hist.update_layout(
                plot_bgcolor=bg_plot,
                paper_bgcolor=bg_plot,
                font_color=font_color,
                font_family="'Inter', sans-serif",
                xaxis_title="Dias entre trocas",
                yaxis_title="Contagem",
                xaxis=dict(tickfont=dict(color=font_color), title_font=dict(color=font_color)),
                yaxis=dict(tickfont=dict(color=font_color), title_font=dict(color=font_color))
            )
            st.plotly_chart(fig_hist, use_container_width=True)
        else:
            st.info("Sem intervalos suficientes para histograma.")
    # Vida útil -> gráfico dias restantes por equipamento
    st.write("Vida útil restante (dias) por equipamento — últimos registros de troca")
    if not last_troca.empty:
        last_troca_sorted = last_troca.sort_values("DAYS_REMAINING", ascending=True)
        fig_life = px.bar(
            last_troca_sorted,
            x="FROTA",
            y="DAYS_REMAINING",
            template="plotly_dark",
            color="DAYS_REMAINING",
            color_continuous_scale="RdYlGn_r"
        )
        fig_life.update_layout(
            plot_bgcolor=bg_plot,
            paper_bgcolor=bg_plot,
            font_color=font_color,
            font_family="'Inter', sans-serif",
            xaxis_title="Frota",
            yaxis_title="Dias restantes",
            xaxis=dict(type="category", tickfont=dict(color=font_color), title_font=dict(color=font_color)),
            yaxis=dict(tickfont=dict(color=font_color), title_font=dict(color=font_color)),
            coloraxis_colorbar=dict(title="Dias restantes")
        )
        st.plotly_chart(fig_life, use_container_width=True)

        st.write("Resumo de vida útil (dias restantes e % do período)")
        display_tbl = last_troca_sorted[["FROTA","DATA_DT","EXPECTED_END","DAYS_SINCE_TROCA","DAYS_TOTAL_EXPECTED","DAYS_REMAINING","PCT_ELAPSED"]].copy()
        display_tbl["DATA_DT"] = display_tbl["DATA_DT"].dt.date
        display_tbl["EXPECTED_END"] = display_tbl["EXPECTED_END"].dt.date
        st.dataframe(display_tbl.reset_index(drop=True), use_container_width=True)
    else:
        st.info("Nenhuma troca detectada para calcular vida útil.")
    st.markdown('</div>', unsafe_allow_html=True)

# --- TAB: Adicionar OS manualmente ---
with tabs[2]:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.header("Adicionar O.S. manualmente")
    with st.form("form_adicionar_os", clear_on_submit=True):
        numero_laudo = st.text_input("NUMERO_LAUDO")
        data_input = st.date_input("DATA")
        frota = st.text_input("FROTA (separe múltiplas frotas com vírgula, ex: 4000,437)")
        parecer = st.text_area("PARECER", height=120)
        analise = st.text_area("ANALISE", height=120)
        conclusao = st.text_area("CONCLUSAO", height=120)
        submit = st.form_submit_button("Salvar O.S. manual")

    if submit:
        if not numero_laudo or not frota:
            st.error("Preencha ao menos NUMERO_LAUDO e FROTA.")
        else:
            # Dividir as frotas por vírgula e remover espaços
            frota_list = [f.strip() for f in frota.split(",") if f.strip()]
            if not frota_list:
                st.error("Nenhuma frota válida fornecida.")
            else:
                manual_csv = PASTA_SAIDA / "manual_additions.csv"
                try:
                    # Criar registros para cada frota
                    records = []
                    for f in frota_list:
                        rec = {
                            "NUMERO_LAUDO": str(numero_laudo).strip(),
                            "DATA": pd.Timestamp(data_input).strftime("%d/%m/%Y"),
                            "FROTA": str(f).strip(),
                            "PARECER": str(parecer).strip(),
                            "ANALISE": str(analise).strip(),
                            "CONCLUSAO": str(conclusao).strip()
                        }
                        records.append(rec)
                    df_rec = pd.DataFrame(records)
                    
                    # Salvar no arquivo manual_additions.csv
                    if manual_csv.exists():
                        df_rec.to_csv(manual_csv, mode="a", header=False, index=False, encoding="utf-8-sig")
                    else:
                        df_rec.to_csv(manual_csv, index=False, encoding="utf-8-sig")
                    
                    # Persistir no relatório principal (xlsx ou csv)
                    try:
                        if os.path.exists(DEFAULT_REPORT):
                            try:
                                df_report = pd.read_excel(DEFAULT_REPORT)
                                st.write("Colunas no relatório existente:", df_report.columns.tolist())  # Log de depuração
                            except Exception as e:
                                st.warning(f"Erro ao ler relatório existente: {e}")
                                df_report = pd.DataFrame(columns=["NUMERO_LAUDO","DATA","FROTA","PARECER","ANALISE","CONCLUSAO"])
                        else:
                            df_report = pd.DataFrame(columns=["NUMERO_LAUDO","DATA","FROTA","PARECER","ANALISE","CONCLUSAO"])
                        
                        # Concatenar novos registros
                        df_report = pd.concat([df_report, df_rec], ignore_index=True)
                        df_report["NUMERO_LAUDO"] = df_report["NUMERO_LAUDO"].astype(str)
                        df_report["FROTA"] = df_report["FROTA"].astype(str)
                        # Comentar deduplicação para evitar remoção de registros
                        # df_report = df_report.drop_duplicates(subset=["NUMERO_LAUDO"], keep="last")
                        
                        # Tentar salvar como Excel
                        try:
                            df_report.to_excel(DEFAULT_REPORT, index=False)
                            st.write(f"Relatório salvo em: {DEFAULT_REPORT}")  # Log de depuração
                        except Exception as e:
                            st.warning(f"Erro ao salvar Excel: {e}")
                            df_report.to_csv(PASTA_SAIDA / "relatorio_tecnico_simplificado.csv", index=False, encoding="utf-8-sig")
                            st.write(f"Relatório salvo como CSV em: {PASTA_SAIDA / 'relatorio_tecnico_simplificado.csv'}")
                        
                        # Atualizar df em memória para refletir imediatamente
                        global df
                        df = pd.concat([df, df_rec], ignore_index=True)
                        df["NUMERO_LAUDO"] = df["NUMERO_LAUDO"].astype(str)
                        df["FROTA"] = df["FROTA"].astype(str)
                        df["DATA_DT"] = pd.to_datetime(df["DATA"].astype(str), dayfirst=True, errors="coerce")
                        df["TEXTO_COMBINADO"] = (
                            df["PARECER"].fillna("").astype(str) + " " +
                            df["ANALISE"].fillna("").astype(str) + " " +
                            df["CONCLUSAO"].fillna("").astype(str)
                        ).str.upper()
                        df["IS_BATERIA"] = df["TEXTO_COMBINADO"].apply(lambda s: bool(pat_bat.search(s)) if pat_bat else False)
                        df["IS_TROCA_BATERIA"] = df["TEXTO_COMBINADO"].apply(lambda s: bool(pat_bat.search(s) and pat_troca.search(s)) if (pat_bat and pat_troca) else False)
                        
                        st.success(f"{len(frota_list)} O.S. salvas em: {manual_csv} (e persistidas no relatório de saída).")
                        st.write("Frotas registradas:", ", ".join(frota_list))
                        st.write("Registros manuais adicionados:", df_rec)  # Exibir registros adicionados
                    except Exception as e:
                        st.error(f"Falha ao salvar O.S. manual: {e}")
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"Falha ao processar O.S. manual: {e}")
    # Exibir histórico de O.S. manuais
    if manual_csv.exists():
        try:
            hist = pd.read_csv(manual_csv, encoding="utf-8-sig")
            st.write("Histórico de O.S. manuais:", hist.tail())
        except Exception as e:
            st.error(f"Erro ao ler histórico manual: {e}")
    st.markdown('</div>', unsafe_allow_html=True)