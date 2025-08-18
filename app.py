import os
import re
from datetime import datetime
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(layout="wide", page_title="Dashboard - Baterias e OS não processadas")
st.title("Dashboard: Trocas de Baterias / OS não processadas")

# --- estilo dark / cards ---
st.markdown(
    """
    <style>
    /* fundo preto */
    .stApp { background: #0b0b0b; color: #e6e6e6; }
    /* cartões / contêineres */
    .card {
        background: rgba(17,17,17,0.85);
        padding: 18px;
        border-radius: 10px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.6);
        margin-bottom: 14px;
        border: 1px solid rgba(255,255,255,0.03);
    }
    .small-muted { color: #aaaaaa; font-size:12px; }
    /* tabela em dark */
    .stDataFrame table { background: transparent; color: #e6e6e6; }
    .stDataFrame th, .stDataFrame td { border-color: rgba(255,255,255,0.03); }
    body, .stApp, .stMarkdown { font-size: 14px; line-height: 1.45; color: #e6e6e6; }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Pastas padrão ---
BASE_DIR = Path.cwd()
PASTA_DADOS = BASE_DIR / "dados"    # coloque os PDFs aqui
PASTA_SAIDA = BASE_DIR / "saida"    # outputs (relatórios, CSVs)
PASTA_DADOS.mkdir(exist_ok=True)
PASTA_SAIDA.mkdir(exist_ok=True)

DEFAULT_REPORT = str(PASTA_SAIDA / "relatorio_tecnico_simplificado.xlsx")
STATUS_REPORT = str(PASTA_SAIDA / "relatorio_status.xlsx")

# carregamento do relatório principal (aceita upload ou arquivo padrão)
df = None
uploaded = st.file_uploader("Carregar relatório (Excel .xlsx) ou CSV", type=["xlsx", "csv"])
if uploaded:
    # alguns objetos de upload mantêm o ponteiro; resetar antes de cada tentativa
    try:
        uploaded.seek(0)
    except Exception:
        pass
    try:
        df = pd.read_excel(uploaded)
        st.info("Arquivo carregado (Excel).")
    except Exception:
        try:
            uploaded.seek(0)
        except Exception:
            pass
        try:
            # tentar leituras comuns de CSV com encodings padrão
            df = pd.read_csv(uploaded, encoding="utf-8")
            st.info("Arquivo carregado (CSV utf-8).")
        except Exception:
            try:
                uploaded.seek(0)
            except Exception:
                pass
            try:
                df = pd.read_csv(uploaded, encoding="latin1")
                st.info("Arquivo carregado (CSV latin1).")
            except Exception as e:
                st.error(f"Erro ao ler o arquivo enviado: {e}")
                df = None
else:
    if os.path.exists(DEFAULT_REPORT):
        try:
            df = pd.read_excel(DEFAULT_REPORT)
            st.info(f"Usando arquivo padrão: {DEFAULT_REPORT}")
        except Exception as e:
            st.warning(f"Falha ao ler o arquivo padrão: {e}. Continuando com análise vazia; você pode adicionar O.S. manualmente.")
            df = None
    else:
        st.info(f"Arquivo padrão '{DEFAULT_REPORT}' não encontrado. Você pode fazer upload do relatório ou adicionar O.S. manualmente na aba apropriada.")
        df = None

# se df não foi carregado, criar DataFrame vazio com colunas esperadas (permite entrada manual)
if df is None:
    df = pd.DataFrame(columns=["NUMERO_LAUDO", "DATA", "FROTA", "PARECER", "ANALISE", "CONCLUSAO"])
    st.warning("Nenhum relatório automático carregado — usando DataFrame vazio. Use a aba 'Adicionar OS manual' para incluir registros.")

# carregar relatório de status (opcional) para listar OS não processadas
status_df = None
if os.path.exists(STATUS_REPORT):
    try:
        status_df = pd.read_excel(STATUS_REPORT)
    except Exception:
        status_df = None

# normalizar colunas e garantir colunas mínimas
df.columns = [c.strip().upper() for c in df.columns]
for c in ["NUMERO_LAUDO", "DATA", "FROTA", "PARECER", "ANALISE", "CONCLUSAO"]:
    if c not in df.columns:
        df[c] = ""

# parse de datas
df["DATA_DT"] = pd.to_datetime(df["DATA"].astype(str), dayfirst=True, errors="coerce")

# campo combinado para busca
df["TEXTO_COMBINADO"] = (
    df["PARECER"].fillna("").astype(str) + " " +
    df["ANALISE"].fillna("").astype(str) + " " +
    df["CONCLUSAO"].fillna("").astype(str)
).str.upper()

# painel lateral: palavras-chave para identificar bateria e troca/substituição
st.sidebar.header("Configurações de detecção")
keywords_bateria = st.sidebar.text_area(
    "Palavras-chave para 'bateria' (separadas por vírgula)",
    value="BATERIA,BATERIAS,BATT"
).upper().split(",")

keywords_troca = st.sidebar.text_area(
    "Palavras-chave para 'troca/substituição' (separadas por vírgula)",
    value="TROCA,SUBSTITUI,SUBSTITUICAO,TROCADO,TROCAR,INSTALADO,INSERIDO"
).upper().split(",")

# compilar padrões
pat_bat = re.compile(r"\b(" + "|".join([re.escape(k.strip()) for k in keywords_bateria if k.strip()]) + r")\b") if any(k.strip() for k in keywords_bateria) else None
pat_troca = re.compile(r"\b(" + "|".join([re.escape(k.strip()) for k in keywords_troca if k.strip()]) + r")\b") if any(k.strip() for k in keywords_troca) else None

df["IS_BATERIA"] = df["TEXTO_COMBINADO"].apply(lambda s: bool(pat_bat.search(s)) if pat_bat else False)
df["IS_TROCA_BATERIA"] = df["TEXTO_COMBINADO"].apply(lambda s: bool(pat_bat.search(s) and pat_troca.search(s)) if (pat_bat and pat_troca) else False)

# criar abas: Análise (conteúdo atual) e Adicionar OS manual
show_analysis_tab = st.sidebar.checkbox("Mostrar aba 'Análises / Extração'", value=True)

tabs_labels = ["Visualização"]
if show_analysis_tab:
    tabs_labels.append("Análises / Extração")
tabs_labels.append("Adicionar OS manual")
tabs = st.tabs(tabs_labels)
tabs_map = {label: tabs[i] for i, label in enumerate(tabs_labels)}

# --- Visualização principal (cards e gráficos) ---
with tabs_map["Visualização"]:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Resumo geral")
    c1, c2, c3, c4 = st.columns([1.5,1,1,1])
    c1.metric("Registros totais", len(df))
    c2.metric("Menção a bateria", int(df["IS_BATERIA"].sum()))
    c3.metric("Troca de bateria detectada", int(df["IS_TROCA_BATERIA"].sum()))
    # mostrar número de PDFs na pasta dados
    pdf_count = len(list(PASTA_DADOS.glob("*.pdf")))
    c4.metric("PDFs em dados/", pdf_count)
    st.markdown('</div>', unsafe_allow_html=True)

    # Frotas
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Frotas (códigos únicos)")
    frotas = sorted(df["FROTA"].dropna().astype(str).unique())
    st.write(f"Total de equipamentos únicos (FROTA): {len(frotas)}")
    st.dataframe(pd.DataFrame({"FROTA": frotas}))
    st.markdown('</div>', unsafe_allow_html=True)

    # trocas detectadas tabela e export
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Registros com TROCA/ SUBSTITUIÇÃO de bateria (detecção por texto)")
    exchanges = df[df["IS_TROCA_BATERIA"]].copy()
    # garantir coluna DATA_DT correta
    if "DATA_DT" in exchanges.columns:
        exchanges["DATA_DT"] = pd.to_datetime(exchanges["DATA_DT"], dayfirst=True, errors="coerce")
    elif "DATA" in exchanges.columns:
        exchanges["DATA_DT"] = pd.to_datetime(exchanges["DATA"].astype(str), dayfirst=True, errors="coerce")
    else:
        exchanges["DATA_DT"] = pd.NaT
    if not exchanges.empty:
        # garantir FROTA como string para eixo x
        exchanges["FROTA"] = exchanges["FROTA"].astype(str)
        exchanges = exchanges.sort_values(by="DATA_DT", na_position="last")
        st.write(f"{len(exchanges)} registros detectados como troca de bateria")
        st.dataframe(exchanges[["NUMERO_LAUDO", "DATA", "FROTA", "PARECER", "ANALISE", "CONCLUSAO"]].reset_index(drop=True))

        if st.button("Exportar trocas detectadas (.csv)"):
            outp = PASTA_SAIDA / "trocas_bateria_detectadas.csv"
            exchanges.to_csv(outp, index=False, encoding="utf-8-sig")
            st.success(f"Gerado: {outp}")
    else:
        st.info("Nenhuma troca de bateria detectada com as palavras-chaves atuais.")
    st.markdown('</div>', unsafe_allow_html=True)

    # gráfico top frotas por número de trocas
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Top frotas por número de trocas")
    if not exchanges.empty:
        summary_cnt = exchanges.groupby("FROTA").size().reset_index(name="count").sort_values("count", ascending=False)
        top30 = summary_cnt.head(30).copy()
        top30["FROTA"] = top30["FROTA"].astype(str)
        fig_bar = px.bar(top30, x="FROTA", y="count",
                         labels={"count":"Número de trocas","FROTA":"Frota"},
                         title="Top 30 frotas por número de trocas",
                         template="plotly_dark")
        fig_bar.update_xaxes(type="category")
        fig_bar.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("Sem dados para gráfico.")
    st.markdown('</div>', unsafe_allow_html=True)

    # vida útil progress bar (12 meses)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Vida útil esperada da bateria (12 meses após troca)")
    if not exchanges.empty:
        last_troca = exchanges.groupby("FROTA", as_index=False)["DATA_DT"].max()
        last_troca["EXPECTED_END"] = last_troca["DATA_DT"] + pd.DateOffset(months=12)
        today = pd.Timestamp(datetime.utcnow().date())
        last_troca["DAYS_SINCE_TROCA"] = (today - last_troca["DATA_DT"]).dt.days
        last_troca["DAYS_TOTAL_EXPECTED"] = (last_troca["EXPECTED_END"] - last_troca["DATA_DT"]).dt.days
        last_troca["DAYS_REMAINING"] = (last_troca["EXPECTED_END"] - today).dt.days
        last_troca["PCT_ELAPSED"] = (last_troca["DAYS_SINCE_TROCA"] / last_troca["DAYS_TOTAL_EXPECTED"]).clip(0,1)

        select_frota_for_life = st.selectbox("Equipamento (frota)", options=["(todos)"] + sorted(last_troca["FROTA"].astype(str).tolist()))
        if select_frota_for_life != "(todos)":
            row = last_troca[last_troca["FROTA"].astype(str) == select_frota_for_life]
            if not row.empty:
                r = row.iloc[0]
                st.markdown(f"**Última troca:** {r['DATA_DT'].date()}  •  **Fim esperado:** {r['EXPECTED_END'].date()}")
                pct = float(r["PCT_ELAPSED"])
                st.progress(int(pct * 100))
                ca, cb, cc = st.columns(3)
                ca.metric("Dias desde a troca", int(r["DAYS_SINCE_TROCA"]))
                cb.metric("Dias restantes (aprox.)", int(r["DAYS_REMAINING"]) if pd.notnull(r["DAYS_REMAINING"]) else "N/A")
                cc.metric("Período total (dias)", int(r["DAYS_TOTAL_EXPECTED"]))
            else:
                st.warning("Nenhuma troca registrada para o equipamento selecionado.")
        else:
            agg_view = last_troca.sort_values("PCT_ELAPSED", ascending=False).reset_index(drop=True)
            agg_view["DATA_DT"] = agg_view["DATA_DT"].dt.date
            agg_view["EXPECTED_END"] = agg_view["EXPECTED_END"].dt.date
            st.dataframe(agg_view[["FROTA","DATA_DT","EXPECTED_END","DAYS_SINCE_TROCA","DAYS_REMAINING","PCT_ELAPSED"]].head(200))
    else:
        st.info("Nenhuma troca detectada — não é possível calcular a vida útil esperada.")
    st.markdown('</div>', unsafe_allow_html=True)

    # botão para exportar dataset atual
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Exportar / Recarregar")
    if st.button("Exportar dataset atual (.csv)"):
        outp = PASTA_SAIDA / "dataset_atual.csv"
        df.to_csv(outp, index=False, encoding="utf-8-sig")
        st.success(f"Dataset exportado: {outp}")
    if st.button("Exportar dataset atual (.xlsx)"):
        outp = PASTA_SAIDA / "dataset_atual.xlsx"
        try:
            df.to_excel(outp, index=False)
            st.success(f"Dataset exportado: {outp}")
        except Exception as e:
            st.error(f"Falha ao salvar xlsx: {e}. Verifique se 'openpyxl' está instalado.")
    if st.button("Recarregar / Recontar PDFs"):
        st.experimental_rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# --- Análises / Extração / Importação ---
with tabs_map.get("Análises / Extração", None):
    if tabs_map.get("Análises / Extração", None) is not None:
        with tabs_map["Análises / Extração"]:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.subheader("Processos de extração / importação")
            st.write("Verificações rápidas e status das importações/extracões.")
            col_a, col_b = st.columns(2)
            col_a.write("Pasta de dados:")
            col_a.write(f"- Path: {PASTA_DADOS}")
            col_a.write(f"- PDFs encontrados: {pdf_count}")
            col_b.write("Relatórios:")
            col_b.write(f"- Relatório padrão (saida): {DEFAULT_REPORT}")
            col_b.write(f"- Status report presente: {'Sim' if status_df is not None else 'Não'}")
            st.caption("Sugestão: para persistência confiável considere usar um único arquivo mestre (xlsx/csv) como fonte de verdade ou um pequeno banco SQLite para concorrência.")
            st.markdown('</div>', unsafe_allow_html=True)

# --- Adicionar OS manualmente e persistência ---
with tabs_map["Adicionar OS manual"]:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.header("Adicionar O.S. manualmente")
    st.write("Use este formulário para inserir um laudo/O.S. que não foi processado automaticamente. Campos obrigatórios: NUMERO_LAUDO, DATA, FROTA.")
    with st.form("form_adicionar_os", clear_on_submit=True):
        numero_laudo = st.text_input("NUMERO_LAUDO", help="Número do laudo (ex.: 12345)")
        data_input = st.date_input("DATA", help="Data do laudo")
        frota = st.text_input("FROTA", help="Código da frota / equipamento")
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

                # persistir também no DEFAULT_REPORT (xlsx) — cria/atualiza
                try:
                    if os.path.exists(DEFAULT_REPORT):
                        try:
                            df_report = pd.read_excel(DEFAULT_REPORT)
                        except Exception:
                            df_report = pd.DataFrame(columns=["NUMERO_LAUDO", "DATA", "FROTA", "PARECER", "ANALISE", "CONCLUSAO"])
                    else:
                        df_report = pd.DataFrame(columns=["NUMERO_LAUDO", "DATA", "FROTA", "PARECER", "ANALISE", "CONCLUSAO"])
                    df_report = pd.concat([df_report, df_rec], ignore_index=True)
                    # remover duplicados mantendo o mais recente (com base em igualdade NUMERO_LAUDO+FROTA)
                    df_report["NUMERO_LAUDO"] = df_report["NUMERO_LAUDO"].astype(str)
                    df_report["FROTA"] = df_report["FROTA"].astype(str)
                    df_report = df_report.drop_duplicates(subset=["NUMERO_LAUDO","FROTA"], keep="last")
                    try:
                        df_report.to_excel(DEFAULT_REPORT, index=False)
                        st.success(f"O.S. salva em: {manual_csv} e persistida em {DEFAULT_REPORT}")
                    except Exception as e:
                        # fallback para CSV se não conseguir salvar xlsx
                        outp_csv = PASTA_SAIDA / "relatorio_tecnico_simplificado.csv"
                        df_report.to_csv(outp_csv, index=False, encoding="utf-8-sig")
                        st.warning(f"Salvo em CSV (fallback) em {outp_csv} porque falhou salvar xlsx: {e}")
                except Exception as e:
                    st.warning(f"Falha ao persistir no DEFAULT_REPORT: {e}")

                # anexar ao DataFrame em memória e recalcular campos derivados
                try:
                    df = pd.concat([df, df_rec], ignore_index=True)
                    df["DATA_DT"] = pd.to_datetime(df["DATA"].astype(str), dayfirst=True, errors="coerce")
                    df["TEXTO_COMBINADO"] = (
                        df["PARECER"].fillna("").astype(str) + " " +
                        df["ANALISE"].fillna("").astype(str) + " " +
                        df["CONCLUSAO"].fillna("").astype(str)
                    ).str.upper()
                    df["IS_BATERIA"] = df["TEXTO_COMBINADO"].apply(lambda s: bool(pat_bat.search(s)) if pat_bat else False)
                    df["IS_TROCA_BATERIA"] = df["TEXTO_COMBINADO"].apply(lambda s: bool(pat_bat.search(s) and pat_troca.search(s)) if (pat_bat and pat_troca) else False)
                    st.info("Registro adicionado e análise atualizada.")
                    st.experimental_rerun()
                except Exception:
                    st.info("Registro salvo, mas não foi possível atualizar a análise em memória automaticamente.")
            except Exception as e:
                st.error(f"Falha ao salvar O.S. manual: {e}")

    # mostrar histórico das adições manuais
    manual_csv = PASTA_SAIDA / "manual_additions.csv"
    if manual_csv.exists():
        st.subheader("Histórico de O.S. adicionadas manualmente")
        try:
            hist = pd.read_csv(manual_csv, encoding="utf-8-sig")
            st.dataframe(hist)
            if st.button("Exportar histórico (.csv)"):
                outp = PASTA_SAIDA / "manual_additions_export.csv"
                hist.to_csv(outp, index=False, encoding="utf-8-sig")
                st.success(f"Exportado: {outp}")
        except Exception as e:
            st.error(f"Falha ao ler histórico: {e}")
    else:
        st.info("Nenhum registro manual salvo ainda. Registros serão salvos em: ./saida/manual_additions.csv")
    st.markdown('</div>', unsafe_allow_html=True)