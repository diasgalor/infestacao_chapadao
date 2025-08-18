import os
import re
from datetime import datetime
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(layout="wide", page_title="Dashboard - Baterias e OS não processadas")
st.title("Dashboard: Trocas de Baterias / OS não processadas")

# --- estilo escuro consistente ---
st.markdown(
    """
    <style>
    .stApp { background: #0b0b0b; color: #e6e6e6; }
    .card {
        background: rgba(20,20,20,0.9);
        padding: 16px;
        border-radius: 10px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.6);
        margin-bottom: 14px;
        border: 1px solid rgba(255,255,255,0.03);
    }
    .stDataFrame table { background: rgba(15,15,15,0.9) !important; color: #e6e6e6; }
    .stDataFrame th, .stDataFrame td { border-color: rgba(255,255,255,0.04) !important; color: #e6e6e6; }
    .metric { color: #e6e6e6; }
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

# --- carregar relatório (upload ou default) ---
df = None
uploaded = st.file_uploader("Carregar relatório (Excel .xlsx) ou CSV", type=["xlsx", "csv"])
if uploaded:
    try:
        uploaded.seek(0)
    except Exception:
        pass
    try:
        df = pd.read_excel(uploaded)
    except Exception:
        try:
            uploaded.seek(0)
        except Exception:
            pass
        for enc in ("utf-8", "latin1", "cp1252"):
            try:
                df = pd.read_csv(uploaded, encoding=enc)
                break
            except Exception:
                continue
else:
    if os.path.exists(DEFAULT_REPORT):
        try:
            df = pd.read_excel(DEFAULT_REPORT)
        except Exception:
            df = None

if df is None:
    df = pd.DataFrame(columns=["NUMERO_LAUDO", "DATA", "FROTA", "PARECER", "ANALISE", "CONCLUSAO"])
    st.warning("Nenhum relatório automático carregado — usando DataFrame vazio. Use 'Adicionar OS manual' para incluir registros.")

# --- garantir colunas e campos derivados ---
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

# --- detecção por palavras-chave (sidebar) ---
st.sidebar.header("Configurações de detecção")
keywords_bateria = st.sidebar.text_area("Palavras-chave para 'bateria' (vírgula)", value="BATERIA,BATERIAS,BATT").upper().split(",")
keywords_troca = st.sidebar.text_area("Palavras-chave para 'troca' (vírgula)", value="TROCA,SUBSTITUI,SUBSTITUICAO,TROCADO,TROCAR,INSTALADO").upper().split(",")

pat_bat = re.compile(r"\b(" + "|".join([re.escape(k.strip()) for k in keywords_bateria if k.strip()]) + r")\b") if any(k.strip() for k in keywords_bateria) else None
pat_troca = re.compile(r"\b(" + "|".join([re.escape(k.strip()) for k in keywords_troca if k.strip()]) + r")\b") if any(k.strip() for k in keywords_troca) else None

df["IS_BATERIA"] = df["TEXTO_COMBINADO"].apply(lambda s: bool(pat_bat.search(s)) if pat_bat else False)
df["IS_TROCA_BATERIA"] = df["TEXTO_COMBINADO"].apply(lambda s: bool(pat_bat.search(s) and pat_troca.search(s)) if (pat_bat and pat_troca) else False)

# --- pré-computos reutilizáveis ---
pdf_count = len(list(PASTA_DADOS.glob("*.pdf")))
exchanges = df[df["IS_TROCA_BATERIA"]].copy()
if "DATA_DT" in exchanges.columns:
    exchanges["DATA_DT"] = pd.to_datetime(exchanges["DATA_DT"], dayfirst=True, errors="coerce")
elif "DATA" in exchanges.columns:
    exchanges["DATA_DT"] = pd.to_datetime(exchanges["DATA"].astype(str), dayfirst=True, errors="coerce")
else:
    exchanges["DATA_DT"] = pd.NaT
exchanges["FROTA"] = exchanges["FROTA"].astype(str)

# vida útil: últimos registros por frota -> days remaining
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

# --- abas: tabelas | gráficos | adicionar OS --- 
tabs = st.tabs(["Tabelas", "Gráficos", "Adicionar OS manual"])

# --- TAB: Tabelas (todas as tabelas em um único lugar) ---
with tabs[0]:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Tabelas")
    st.write("Relatório completo (fonte atual em memória):")
    st.dataframe(df.reset_index(drop=True))
    st.write("Registros detectados como troca de bateria:")
    st.dataframe(exchanges[["NUMERO_LAUDO","DATA","FROTA","PARECER","ANALISE","CONCLUSAO","DATA_DT"]].reset_index(drop=True))
    manual_csv = PASTA_SAIDA / "manual_additions.csv"
    if manual_csv.exists():
        st.write("Adições manuais (histórico):")
        try:
            hist = pd.read_csv(manual_csv, encoding="utf-8-sig")
            st.dataframe(hist)
            if st.button("Exportar histórico manual (.csv)"):
                outp = PASTA_SAIDA / "manual_additions_export.csv"
                hist.to_csv(outp, index=False, encoding="utf-8-sig")
                st.success(f"Exportado: {outp}")
        except Exception as e:
            st.error(f"Erro lendo histórico manual: {e}")
    # PDFs possivelmente não processados
    st.write("PDFs em pasta 'dados' que não aparecem no relatório (por NUMERO_LAUDO):")
    arquivos_dados = sorted([f.name for f in PASTA_DADOS.glob("*.pdf")])
    laudos = df["NUMERO_LAUDO"].astype(str).unique().tolist()
    nao_listados = [a for a in arquivos_dados if not any(str(l) in a for l in laudos)]
    st.dataframe(pd.DataFrame({"arquivo": nao_listados}))
    if st.button("Exportar lista de PDFs possivelmente não processados"):
        outp = PASTA_SAIDA / "pdfs_possiveis_nao_processados.csv"
        pd.DataFrame({"arquivo": nao_listados}).to_csv(outp, index=False, encoding="utf-8-sig")
        st.success(f"Gerado: {outp}")
    st.markdown('</div>', unsafe_allow_html=True)

# --- TAB: Gráficos (visualizações em separado) ---
with tabs[1]:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Gráficos")
    # cores consistentes
    accent = "#00cc96"
    font_color = "#e6e6e6"
    bg_plot = "rgba(15,15,15,0)"  # transparent card, plot dark
    # Top frotas por número de trocas
    st.write("Top frotas por número de trocas")
    if not exchanges.empty:
        summary_cnt = exchanges.groupby("FROTA").size().reset_index(name="count").sort_values("count", ascending=False)
        top30 = summary_cnt.head(30).copy()
        fig_bar = px.bar(top30, x="FROTA", y="count", template="plotly_dark", color_discrete_sequence=[accent])
        fig_bar.update_layout(plot_bgcolor=bg_plot, paper_bgcolor=bg_plot, font_color=font_color)
        fig_bar.update_xaxes(title_text="Frota", tickfont_color=font_color, title_font_color=font_color)
        fig_bar.update_yaxes(title_text="Número de trocas", tickfont_color=font_color, title_font_color=font_color)
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
            fig_hist = px.histogram(exch_with_intervals.dropna(subset=["DIAS_DESDE_ULTIMA"]), x="DIAS_DESDE_ULTIMA", nbins=30, template="plotly_dark", color_discrete_sequence=[accent])
            fig_hist.update_layout(plot_bgcolor=bg_plot, paper_bgcolor=bg_plot, font_color=font_color)
            fig_hist.update_xaxes(title_text="Dias entre trocas", tickfont_color=font_color, title_font_color=font_color)
            fig_hist.update_yaxes(title_text="Contagem", tickfont_color=font_color, title_font_color=font_color)
            st.plotly_chart(fig_hist, use_container_width=True)
        else:
            st.info("Sem intervalos suficientes para histograma.")
    # Vida útil -> gráfico dias restantes por equipamento
    st.write("Vida útil restante (dias) por equipamento — últimos registros de troca")
    if not last_troca.empty:
        last_troca_sorted = last_troca.sort_values("DAYS_REMAINING", ascending=True)  # soonest expiry first
        fig_life = px.bar(last_troca_sorted, x="FROTA", y="DAYS_REMAINING", template="plotly_dark",
                          color="DAYS_REMAINING", color_continuous_scale="RdYlGn_r")
        fig_life.update_layout(plot_bgcolor=bg_plot, paper_bgcolor=bg_plot, font_color=font_color, coloraxis_colorbar=dict(title="Dias restantes"))
        fig_life.update_xaxes(type="category", tickfont_color=font_color, title_font_color=font_color)
        fig_life.update_yaxes(title_text="Dias restantes", tickfont_color=font_color, title_font_color=font_color)
        st.plotly_chart(fig_life, use_container_width=True)

        # tabela auxiliar com dias restantes e progresso %
        st.write("Resumo de vida útil (dias restantes e % do período)")
        display_tbl = last_troca_sorted[["FROTA","DATA_DT","EXPECTED_END","DAYS_SINCE_TROCA","DAYS_TOTAL_EXPECTED","DAYS_REMAINING","PCT_ELAPSED"]].copy()
        display_tbl["DATA_DT"] = display_tbl["DATA_DT"].dt.date
        display_tbl["EXPECTED_END"] = display_tbl["EXPECTED_END"].dt.date
        st.dataframe(display_tbl.reset_index(drop=True))
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
        frota = st.text_input("FROTA")
        parecer = st.text_area("PARECER", height=120)
        analise = st.text_area("ANALISE", height=120)
        conclusao = st.text_area("CONCLUSAO", height=120)
        submit = st.form_submit_button("Salvar O.S. manual")

    if submit:
        if not numero_laudo or not frota:
            st.error("Preencha ao menos NUMERO_LAUDO e FROTA.")
        else:
            rec = {
                "NUMERO_LAUDO": str(numero_laudo).strip(),
                "DATA": pd.Timestamp(data_input).strftime("%d/%m/%Y"),
                "FROTA": str(frota).strip(),
                "PARECER": str(parecer).strip(),
                "ANALISE": str(analise).strip(),
                "CONCLUSAO": str(conclusao).strip()
            }
            manual_csv = PASTA_SAIDA / "manual_additions.csv"
            try:
                df_rec = pd.DataFrame([rec])
                if manual_csv.exists():
                    df_rec.to_csv(manual_csv, mode="a", header=False, index=False, encoding="utf-8-sig")
                else:
                    df_rec.to_csv(manual_csv, index=False, encoding="utf-8-sig")
                # persistir no DEFAULT_REPORT (xlsx) ou CSV fallback
                try:
                    if os.path.exists(DEFAULT_REPORT):
                        try:
                            df_report = pd.read_excel(DEFAULT_REPORT)
                        except Exception:
                            df_report = pd.DataFrame(columns=["NUMERO_LAUDO","DATA","FROTA","PARECER","ANALISE","CONCLUSAO"])
                    else:
                        df_report = pd.DataFrame(columns=["NUMERO_LAUDO","DATA","FROTA","PARECER","ANALISE","CONCLUSAO"])
                    df_report = pd.concat([df_report, df_rec], ignore_index=True)
                    df_report["NUMERO_LAUDO"] = df_report["NUMERO_LAUDO"].astype(str)
                    df_report["FROTA"] = df_report["FROTA"].astype(str)
                    df_report = df_report.drop_duplicates(subset=["NUMERO_LAUDO","FROTA"], keep="last")
                    try:
                        df_report.to_excel(DEFAULT_REPORT, index=False)
                    except Exception:
                        df_report.to_csv(PASTA_SAIDA / "relatorio_tecnico_simplificado.csv", index=False, encoding="utf-8-sig")
                except Exception:
                    pass
                # atualizar em memória e forçar reload para refletir alterações
                st.success(f"O.S. salva em: {manual_csv} (e persistida no relatório de saída).")
                st.experimental_rerun()
            except Exception as e:
                st.error(f"Falha ao salvar O.S. manual: {e}")
    st.markdown('</div>', unsafe_allow_html=True)