import os
import re
from datetime import datetime
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(layout="wide", page_title="Dashboard - Baterias e OS não processadas")
st.title("Dashboard: Trocas de Baterias / OS não processadas")

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
tabs = st.tabs(["Análise", "Adicionar OS manual"])

with tabs[0]:
    # painel principal
    st.header("Resumo geral")
    col1, col2, col3 = st.columns(3)
    col1.metric("Registros totais", len(df))
    col2.metric("Registros com menção a bateria", int(df["IS_BATERIA"].sum()))
    col3.metric("Registros que parecem trocar bateria", int(df["IS_TROCA_BATERIA"].sum()))

    # listar OS não processadas (usar relatorio_status.xlsx se disponível)
    st.subheader("OS / PDFs não processadas (relatorio_status.xlsx)")
    if status_df is not None:
        status_df.columns = [c.strip().upper() for c in status_df.columns]
        if "STATUS" in status_df.columns:
            not_ok = status_df[status_df["STATUS"].astype(str).str.upper() != "OK"]
            if not not_ok.empty:
                st.write(f"{len(not_ok)} arquivos com status != OK")
                st.dataframe(not_ok[["ARQUIVO", "STATUS", "DETALHES", "CAMINHO"]].fillna(""))
                if st.button("Exportar lista de arquivos não processados (.csv)"):
                    outp = PASTA_SAIDA / "os_nao_processadas.csv"
                    not_ok.to_csv(outp, index=False, encoding="utf-8-sig")
                    st.success(f"Gerado: {outp}")
            else:
                st.success("Nenhuma OS com status diferente de OK encontrada no relatorio_status.xlsx")
        else:
            st.warning("relatorio_status.xlsx encontrado, mas coluna 'STATUS' não existe. Exibindo todo o arquivo:")
            st.dataframe(status_df)
    else:
        st.info("relatorio_status.xlsx não encontrado. Se quiser, gere-o no script extracao.py ou faça upload manual do arquivo de status.")
        st.write("Verificando consistência: arquivos na pasta 'dados' (se existir) vs registros no relatório")
        if PASTA_DADOS.is_dir():
            arquivos_dados = sorted([f for f in os.listdir(PASTA_DADOS) if f.lower().endswith(".pdf")])
            st.write(f"{len(arquivos_dados)} PDFs na pasta '{PASTA_DADOS.name}'")
            # verificar nomes que não aparecem representados pelo NUMERO_LAUDO no relatório
            laudos = df["NUMERO_LAUDO"].astype(str).unique().tolist()
            nao_listados = [a for a in arquivos_dados if not any(str(l) in a for l in laudos)]
            if nao_listados:
                st.write("Arquivos possivelmente não processados (nomes não casam com NUMERO_LAUDO):")
                st.dataframe(pd.DataFrame({"arquivo": nao_listados}))
                if st.button("Exportar lista de PDFs possivelmente não processados (.csv)"):
                    outp = PASTA_SAIDA / "pdfs_possiveis_nao_processados.csv"
                    pd.DataFrame({"arquivo": nao_listados}).to_csv(outp, index=False, encoding="utf-8-sig")
                    st.success(f"Gerado: {outp}")
            else:
                st.success(f"Todos os PDFs da pasta '{PASTA_DADOS.name}' parecem estar representados no relatório (por NUMERO_LAUDO).")
        else:
            st.info(f"Pasta '{PASTA_DADOS.name}' não existe neste diretório do projeto. Crie-a e coloque os PDFs lá para validação automática.")

    # análise por frota (códigos únicos)
    st.subheader("Frotas (códigos únicos)")
    frotas = sorted(df["FROTA"].dropna().astype(str).unique())
    st.write(f"Total de equipamentos únicos (FROTA): {len(frotas)}")
    st.dataframe(pd.DataFrame({"FROTA": frotas}))

    # tabela de trocas de bateria detectadas
    st.subheader("Registros com TROCA/ SUBSTITUIÇÃO de bateria (detecção por texto)")
    exchanges = df[df["IS_TROCA_BATERIA"]].copy()
    # garantir que exista e seja datetime; recalcula a partir da coluna DATA se necessário
    if "DATA_DT" not in exchanges.columns:
        exchanges["DATA_DT"] = pd.to_datetime(exchanges.get("DATA", "").astype(str), dayfirst=True, errors="coerce")
    else:
        exchanges["DATA_DT"] = pd.to_datetime(exchanges["DATA_DT"], dayfirst=True, errors="coerce")
    # ordenar, colocamos NaT ao final
    if not exchanges.empty:
        exchanges = exchanges.sort_values(by="DATA_DT", na_position="last")
    if not exchanges.empty:
        st.write(f"{len(exchanges)} registros detectados como troca de bateria")
        st.dataframe(exchanges[["NUMERO_LAUDO", "DATA", "FROTA", "PARECER", "ANALISE", "CONCLUSAO"]].reset_index(drop=True))
        if st.button("Exportar trocas detectadas (.csv)"):
            outp = PASTA_SAIDA / "trocas_bateria_detectadas.csv"
            exchanges.to_csv(outp, index=False, encoding="utf-8-sig")
            st.success(f"Gerado: {outp}")
    else:
        st.info("Nenhuma troca de bateria detectada com as palavras-chaves atuais.")

    # calcular intervalos entre trocas por frota
    st.subheader("Intervalos entre trocas por equipamento (dias)")
    if not exchanges.empty:
        def add_intervals(g):
            g = g.sort_values("DATA_DT")
            g["PREV_DATE"] = g["DATA_DT"].shift(1)
            g["DIAS_DESDE_ULTIMA"] = (g["DATA_DT"] - g["PREV_DATE"]).dt.days
            return g

        exch_with_intervals = exchanges.groupby("FROTA", group_keys=False).apply(add_intervals)
        # resumo por frota
        summary = exch_with_intervals.dropna(subset=["DIAS_DESDE_ULTIMA"]).groupby("FROTA")["DIAS_DESDE_ULTIMA"]\
            .agg(["count", "mean", "median", "min", "max"]).reset_index().sort_values("count", ascending=False)
        st.dataframe(summary.reset_index(drop=True))
        # gráficos
        # garantir que o eixo x seja tratado como categoria (string)
        summary["FROTA"] = summary["FROTA"].astype(str)
        top30 = summary.head(30).copy()
        fig_bar = px.bar(top30, x="FROTA", y="count",
                         labels={"count":"Número de trocas","FROTA":"Frota"},
                         title="Top 30 frotas por número de trocas")
        fig_bar.update_xaxes(type="category")
        st.plotly_chart(fig_bar, use_container_width=True)

        if not exch_with_intervals["DIAS_DESDE_ULTIMA"].dropna().empty:
            fig_hist = px.histogram(exch_with_intervals.dropna(subset=["DIAS_DESDE_ULTIMA"]), x="DIAS_DESDE_ULTIMA", nbins=30, title="Distribuição dos intervalos entre trocas (dias)")
            st.plotly_chart(fig_hist, use_container_width=True)
    else:
        st.info("Sem dados para calcular intervalos entre trocas.")

    # --- Vida útil esperada da bateria (12 meses após troca) ---
    st.subheader("Vida útil esperada da bateria (12 meses após troca)")

    if not exchanges.empty:
        last_troca = exchanges.groupby("FROTA", as_index=False)["DATA_DT"].max()
        # calcular fim esperado adicionando 12 meses
        last_troca["EXPECTED_END"] = last_troca["DATA_DT"] + pd.DateOffset(months=12)
        today = pd.Timestamp(datetime.utcnow().date())

        # coluna de dias
        last_troca["DAYS_SINCE_TROCA"] = (today - last_troca["DATA_DT"]).dt.days
        last_troca["DAYS_TOTAL_EXPECTED"] = (last_troca["EXPECTED_END"] - last_troca["DATA_DT"]).dt.days
        last_troca["DAYS_REMAINING"] = (last_troca["EXPECTED_END"] - today).dt.days
        # pct elapsed (clamp 0..1)
        last_troca["PCT_ELAPSED"] = (last_troca["DAYS_SINCE_TROCA"] / last_troca["DAYS_TOTAL_EXPECTED"]).clip(0,1)

        # selector para visualizar um equipamento específico
        st.write("Escolha um equipamento para ver o progresso da vida útil da bateria (12 meses):")
        select_frota_for_life = st.selectbox("Equipamento (frota)", options=["(todos)"] + sorted(last_troca["FROTA"].astype(str).tolist()))

        if select_frota_for_life != "(todos)":
            row = last_troca[last_troca["FROTA"].astype(str) == select_frota_for_life]
            if not row.empty:
                r = row.iloc[0]
                st.markdown(f"**Última troca:** {r['DATA_DT'].date()}  •  **Fim esperado:** {r['EXPECTED_END'].date()}")
                pct = float(r["PCT_ELAPSED"])
                st.progress(int(pct * 100))
                col_a, col_b, col_c = st.columns(3)
                col_a.metric("Dias desde a troca", int(r["DAYS_SINCE_TROCA"]))
                col_b.metric("Dias restantes (aprox.)", int(r["DAYS_REMAINING"]) if pd.notnull(r["DAYS_REMAINING"]) else "N/A")
                col_c.metric("Período total (dias)", int(r["DAYS_TOTAL_EXPECTED"]))
                hist = exchanges[exchanges["FROTA"].astype(str) == select_frota_for_life].sort_values("DATA_DT", ascending=False)
                st.dataframe(hist[["NUMERO_LAUDO","DATA","PARECER","ANALISE","CONCLUSAO"]].reset_index(drop=True))
            else:
                st.warning("Nenhuma troca registrada para o equipamento selecionado.")
        else:
            agg_view = last_troca.sort_values("PCT_ELAPSED", ascending=False).reset_index(drop=True)
            agg_view["DATA_DT"] = agg_view["DATA_DT"].dt.date
            agg_view["EXPECTED_END"] = agg_view["EXPECTED_END"].dt.date
            st.dataframe(agg_view[["FROTA","DATA_DT","EXPECTED_END","DAYS_SINCE_TROCA","DAYS_REMAINING","PCT_ELAPSED"]].head(200))

            top_progress = agg_view.head(30).copy()
            top_progress["FROTA"] = top_progress["FROTA"].astype(str)
            fig_prog = px.bar(top_progress, x="FROTA", y="PCT_ELAPSED",
                              labels={"PCT_ELAPSED":"% do período (0..1)","FROTA":"Frota"},
                              title="Progresso da vida útil (12 meses) - Top 30 por prazo decorrido")
            fig_prog.update_yaxes(tickformat=".0%", range=[0,1])
            fig_prog.update_xaxes(type="category")
            st.plotly_chart(fig_prog, use_container_width=True)
    else:
        st.info("Nenhuma troca detectada — não é possível calcular a vida útil esperada. Ajuste palavras-chave e reanalise.")

    st.markdown("Observações: a detecção é por busca textual nas colunas PARECER/ANALISE/CONCLUSAO. Ajuste as palavras-chave na barra lateral para melhorar a captura.")

with tabs[1]:
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
                st.success(f"O.S. salva em: {manual_csv}")

                # anexar ao DataFrame em memória para que apareça na análise atual
                try:
                    df = pd.concat([df, df_rec], ignore_index=True)
                    # recalcular campos derivados para incluir novo registro
                    df["DATA_DT"] = pd.to_datetime(df["DATA"].astype(str), dayfirst=True, errors="coerce")
                    df["TEXTO_COMBINADO"] = (
                        df["PARECER"].fillna("").astype(str) + " " +
                        df["ANALISE"].fillna("").astype(str) + " " +
                        df["CONCLUSAO"].fillna("").astype(str)
                    ).str.upper()
                    df["IS_BATERIA"] = df["TEXTO_COMBINADO"].apply(lambda s: bool(pat_bat.search(s)) if pat_bat else False)
                    df["IS_TROCA_BATERIA"] = df["TEXTO_COMBINADO"].apply(lambda s: bool(pat_bat.search(s) and pat_troca.search(s)) if (pat_bat and pat_troca) else False)
                    st.info("Registro adicionado à análise em memória.")
                except Exception:
                    pass
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