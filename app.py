from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st


st.set_page_config(page_title="Energia mensal", page_icon="⚡", layout="wide")
st.title("A geração solar aumentou de **7,4 GWh em 2015 para 91.832,6 GWh em 2025**.")
st.write("uma diferença de **91.825,2 GWh**.")

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
    dados_solar_anual = dados_filtrados.groupby("ano", as_index=False)["solar_gwh"].sum()
    dados_solar_anual["ano"] = dados_solar_anual["ano"].astype(int)
    primeiro_ano = dados_solar_anual.iloc[0]
    ultimo_ano = dados_solar_anual.iloc[-1]
    geracao_solar_inicial = primeiro_ano["solar_gwh"]
    geracao_solar_final = ultimo_ano["solar_gwh"]

    def formatar_gwh(valor):
        return f"{valor:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")

    st.subheader("Crescimento da geração solar")
    indicador_solar_inicial, indicador_solar_final, indicador_crescimento_solar = st.columns(3)
    indicador_solar_inicial.metric(
        f"Geração solar em {int(primeiro_ano['ano'])}",
        f"{formatar_gwh(geracao_solar_inicial)} GWh",
    )
    indicador_solar_final.metric(
        f"Geração solar em {int(ultimo_ano['ano'])}",
        f"{formatar_gwh(geracao_solar_final)} GWh",
    )
    if geracao_solar_inicial > 0:
        crescimento_solar = (geracao_solar_final / geracao_solar_inicial - 1) * 100
        crescimento_formatado = f"{crescimento_solar:+,.1f}%".replace(",", "X").replace(".", ",").replace("X", ".")
        indicador_crescimento_solar.metric(
            f"Variação de {int(primeiro_ano['ano'])} a {int(ultimo_ano['ano'])}",
            crescimento_formatado,
        )
    else:
        indicador_crescimento_solar.metric(
            f"Variação de {int(primeiro_ano['ano'])} a {int(ultimo_ano['ano'])}",
            "Sem geração solar no primeiro ano",
        )

    base_grafico_solar = alt.Chart(dados_solar_anual).encode(
        x=alt.X("ano:O", title="Ano"),
        y=alt.Y("solar_gwh:Q", title="Geração solar (GWh)", scale=alt.Scale(zero=True)),
        tooltip=[
            alt.Tooltip("ano:O", title="Ano"),
            alt.Tooltip("solar_gwh:Q", title="Geração solar (GWh)", format=",.1f"),
        ],
    )
    grafico_solar = base_grafico_solar.mark_line(
        color=cores_fontes["Solar"],
        strokeWidth=3,
    ) + base_grafico_solar.mark_point(color=cores_fontes["Solar"], size=75)
    st.altair_chart(grafico_solar, width="stretch")

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
    dados_mensais_longos = serie_mensal.reset_index().melt(
        id_vars="Mês",
        var_name="Fonte",
        value_name="Geração (GWh)",
    )
    grafico_mensal = (
        alt.Chart(dados_mensais_longos)
        .mark_line()
        .encode(
            x=alt.X("Mês:T", title="Mês"),
            y=alt.Y("Geração (GWh):Q", title="Geração (GWh)"),
            color=alt.Color(
                "Fonte:N",
                scale=alt.Scale(
                    domain=list(cores_fontes.keys()),
                    range=list(cores_fontes.values()),
                ),
                title="Fonte",
            ),
            opacity=alt.condition(alt.datum.Fonte == "Solar", alt.value(1), alt.value(0.35)),
            strokeWidth=alt.condition(alt.datum.Fonte == "Solar", alt.value(4), alt.value(1.5)),
            tooltip=[
                alt.Tooltip("Mês:T", title="Mês"),
                alt.Tooltip("Fonte:N", title="Fonte"),
                alt.Tooltip("Geração (GWh):Q", title="Geração (GWh)", format=",.1f"),
            ],
        )
    )
    marco_distribuida = pd.Timestamp("2023-05-01")
    if serie_mensal.index.min() <= marco_distribuida <= serie_mensal.index.max():
        marcador = pd.DataFrame({"Mês": [marco_distribuida]})
        nota_marco = pd.DataFrame(
            {
                "Mês": [marco_distribuida],
                "Geração (GWh)": [dados_mensais_longos["Geração (GWh)"].max()],
            }
        )
        grafico_mensal += alt.Chart(marcador).mark_rule(
            color="#555555",
            strokeDash=[6, 4],
        ).encode(x="Mês:T")
        grafico_mensal += (
            alt.Chart(nota_marco)
            .mark_text(
                text="a partir daqui, inclui geração distribuída.",
                align="left",
                baseline="top",
                dx=6,
                dy=6,
                color="#444444",
                fontStyle="italic",
            )
            .encode(
                x="Mês:T",
                y="Geração (GWh):Q",
            )
        )
    st.altair_chart(grafico_mensal, width="stretch")

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

st.caption("Fonte: ONS, Dados Abertos, Balanço de Energia nos Subsistemas. Licença CC-BY.")