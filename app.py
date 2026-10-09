from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st


st.set_page_config(page_title="Energia mensal", page_icon="⚡", layout="wide")
st.title("Painel de geração de energia")

csv_path = Path(__file__).parent / "energia_ons_mensal.csv"

if not csv_path.exists():
    st.error(f"Arquivo não encontrado: {csv_path.name}")
    st.stop()

try:
    dados = pd.read_csv(csv_path)
except (OSError, pd.errors.ParserError, UnicodeDecodeError) as erro:
    st.error(f"Não foi possível ler o arquivo {csv_path.name}: {erro}")
    st.stop()

fontes = {
    "Hidráulica": "hidraulica_gwh",
    "Térmica": "termica_gwh",
    "Eólica": "eolica_gwh",
    "Solar": "solar_gwh",
}
cores_fontes = {
    "Hidráulica": "#1f77b4",
    "Térmica": "#ff7f0e",
    "Eólica": "#2a9d8f",
    "Solar": "#f2c94c",
}
colunas_necessarias = {"ano", "mes", "regiao", *fontes.values()}
if not colunas_necessarias.issubset(dados.columns):
    st.error("O CSV não contém todas as colunas necessárias para o painel.")
    st.stop()

anos = pd.to_numeric(dados["ano"], errors="coerce").dropna()
if anos.empty:
    st.error("Não há anos válidos na coluna 'ano'.")
    st.stop()

dados["ano"] = pd.to_numeric(dados["ano"], errors="coerce")
regioes = sorted(dados["regiao"].dropna().astype(str).unique())
with st.sidebar:
    st.header("Filtros")
    regiao_selecionada = st.selectbox("Região", ["Brasil", *regioes])
    intervalo_anos = st.slider(
        "Intervalo de anos",
        min_value=int(anos.min()),
        max_value=int(anos.max()),
        value=(int(anos.min()), int(anos.max())),
        step=1,
    )

dados_filtrados = dados[dados["ano"].between(*intervalo_anos)]
if regiao_selecionada != "Brasil":
    dados_filtrados = dados_filtrados[dados_filtrados["regiao"] == regiao_selecionada]

colunas_fontes = list(fontes.values())
totais_fontes = dados_filtrados[colunas_fontes].sum()
geracao_total = totais_fontes.sum()
fontes_renovaveis = ["hidraulica_gwh", "eolica_gwh", "solar_gwh"]
percentual_renovavel = (
    dados_filtrados[fontes_renovaveis].sum().sum() / geracao_total * 100
    if geracao_total
    else 0
)
geracao_formatada = f"{geracao_total:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
percentual_formatado = f"{percentual_renovavel:.1f}".replace(".", ",")

indicador_total, indicador_renovavel = st.columns(2)
indicador_total.metric("Geração total no período", f"{geracao_formatada} GWh")
indicador_renovavel.metric("Geração de fontes renováveis", f"{percentual_formatado}%")
st.caption(f"Região: {regiao_selecionada} · período: {intervalo_anos[0]} a {intervalo_anos[1]}")

if dados_filtrados.empty:
    st.info("Não há dados para a região e o intervalo selecionados.")
else:
    dados_mensais = dados_filtrados.groupby(["ano", "mes"], as_index=False)[colunas_fontes].sum()
    dados_mensais["Mês"] = pd.to_datetime(
        {
            "year": dados_mensais["ano"].astype(int),
            "month": dados_mensais["mes"].astype(int),
            "day": 1,
        }
    )
    serie_mensal = dados_mensais[["Mês", *colunas_fontes]].rename(
        columns={coluna: fonte for fonte, coluna in fontes.items()}
    ).set_index("Mês")

st.subheader("Geração mensal por fonte")
if not dados_filtrados.empty:
    st.line_chart(
        serie_mensal,
        x_label="Mês",
        y_label="Geração (GWh)",
        color=[cores_fontes[fonte] for fonte in serie_mensal.columns],
        width="stretch",
    )

st.subheader(f"Participação percentual por fonte em {intervalo_anos[1]}")
dados_ultimo_ano = dados_filtrados[dados_filtrados["ano"] == intervalo_anos[1]]
if dados_ultimo_ano.empty:
    st.info(f"Não há dados para a região selecionada em {intervalo_anos[1]}.")
else:
    totais_ultimo_ano = dados_ultimo_ano[colunas_fontes].sum()
    geracao_total_ultimo_ano = totais_ultimo_ano.sum()
    if geracao_total_ultimo_ano <= 0:
        st.info(f"Não há geração registrada para calcular os percentuais em {intervalo_anos[1]}.")
    else:
        participacoes_ultimo_ano = totais_ultimo_ano / geracao_total_ultimo_ano * 100
        dados_participacao = pd.DataFrame(
            {
                "Fonte": list(fontes.keys()),
                "Participação (%)": participacoes_ultimo_ano.values,
            }
        )
        grafico_participacao = (
            alt.Chart(dados_participacao)
            .mark_bar()
            .encode(
                x=alt.X("Fonte:N", sort=None, title="Fonte"),
                y=alt.Y("Participação (%):Q", title="Participação (%)"),
                color=alt.Color(
                    "Fonte:N",
                    scale=alt.Scale(
                        domain=list(cores_fontes.keys()),
                        range=list(cores_fontes.values()),
                    ),
                    legend=None,
                ),
                tooltip=["Fonte:N", "Participação (%):Q"],
            )
        )
        st.altair_chart(grafico_participacao, width="stretch")

with st.expander("Detalhes dos dados"):
    st.write(f"**Quantidade de linhas no filtro:** {len(dados_filtrados):,}".replace(",", "."))
    st.write(f"**Regiões:** {', '.join(regioes)}")

    st.subheader("Geração por fonte no filtro")
    if dados_filtrados.empty:
        st.info("Não há dados para resumir.")
    else:
        totais_filtrados = dados_filtrados[colunas_fontes].sum()
        total_filtrado = totais_filtrados.sum()
        participacoes = totais_filtrados / total_filtrado * 100 if total_filtrado else totais_filtrados * 0
        resumo_geracao = pd.DataFrame(
            {
                "Fonte": list(fontes.keys()),
                "Geração (GWh)": totais_filtrados.values,
                "Participação (%)": participacoes.values,
            }
        )
        st.dataframe(
            resumo_geracao,
            width="stretch",
            hide_index=True,
            column_config={
                "Geração (GWh)": st.column_config.NumberColumn(format="%.1f"),
                "Participação (%)": st.column_config.NumberColumn(format="%.1f%%"),
            },
        )

    st.subheader("Primeiras linhas")
    st.dataframe(dados_filtrados.head(), width="stretch", hide_index=True)