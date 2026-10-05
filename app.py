"""Dashboard — Desemprego no Brasil (simulação 2015–2024)."""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import seaborn as sns
import streamlit as st
from scipy import stats

from database.db import ORDEM_RISCO, carregar_do_banco, engenharia, limpar, taxa_ponderada

st.set_page_config(page_title="Desemprego no Brasil", page_icon="📉", layout="wide")
sns.set_theme(style="whitegrid")
CORES_RISCO = {"Baixo": "#2a9d8f", "Médio": "#e9c46a", "Alto": "#f4a261", "Crítico": "#d62828"}
COLS_NUM = ["taxa_desemprego", "renda_media", "vagas_formais", "vagas_por_mil", "inflacao", "populacao_ativa"]


@st.cache_data
def carregar() -> pd.DataFrame:
    return carregar_do_banco()


# ---------------------------------------------------------------- Cabeçalho
st.title("📉 Desemprego no Brasil: onde, quando e quão grave?")
st.markdown(
    "**Problema:** o desemprego não é distribuído de forma uniforme — varia entre regiões, estados e momentos "
    "econômicos. Este painel analisa **800 observações trimestrais de 20 UFs (2015–2024)** para identificar "
    "quais territórios estão mais vulneráveis, como a pandemia afetou o mercado de trabalho e se renda, vagas "
    "formais e inflação ajudam a explicar a taxa de desemprego."
)
st.caption("⚠️ Base simulada para fins didáticos — os resultados ilustram a metodologia, não estatísticas oficiais do IBGE.")

# ---------------------------------------------------------------- Dados + upload
with st.sidebar:
    st.header("🎛️ Filtros")
    arq = st.file_uploader("Usar outro CSV (mesmo formato)", type="csv")

df_base = carregar()
if arq is not None:
    try:
        df_base = engenharia(limpar(pd.read_csv(arq)))
        st.sidebar.success("CSV carregado com sucesso.")
    except Exception as e:  # noqa: BLE001
        st.sidebar.error(f"Arquivo fora do formato esperado: {e}")

with st.sidebar:
    a0, a1 = int(df_base["ano"].min()), int(df_base["ano"].max())
    anos = st.slider("Período (anos)", a0, a1, (a0, a1))
    regs = st.multiselect("Região", sorted(df_base["regiao"].unique()), default=sorted(df_base["regiao"].unique()))
    ufs_disp = sorted(df_base[df_base["regiao"].isin(regs)]["uf"].unique())
    ufs = st.multiselect("UF", ufs_disp, default=ufs_disp)
    setores = st.multiselect("Setor predominante", sorted(df_base["setor_predominante"].unique()),
                             default=sorted(df_base["setor_predominante"].unique()))
    riscos = st.multiselect("Nível de risco", ORDEM_RISCO, default=ORDEM_RISCO)

df = df_base[
    df_base["ano"].between(*anos) & df_base["regiao"].isin(regs) & df_base["uf"].isin(ufs)
    & df_base["setor_predominante"].isin(setores) & df_base["nivel_risco"].isin(riscos)
]
if df.empty:
    st.warning("Nenhum dado para os filtros selecionados. Ajuste a barra lateral.")
    st.stop()
df = df.assign(nivel_risco=df["nivel_risco"].astype(str))

# ---------------------------------------------------------------- KPIs dinâmicos
por_trim = df.groupby("data").apply(taxa_ponderada, include_groups=False)
taxa_geral = taxa_ponderada(df)
taxa_ult = por_trim.iloc[-1]
delta = taxa_ult - por_trim.iloc[0]
por_uf = df.groupby("uf")["taxa_desemprego"].mean().sort_values()
pct_critico = (df["nivel_risco"] == "Crítico").mean() * 100

k = st.columns(5)
k[0].metric("Taxa de desemprego (ponderada)", f"{taxa_geral:.2f}%")
k[1].metric("Último trimestre filtrado", f"{taxa_ult:.2f}%", f"{delta:+.2f} p.p. vs. primeiro", delta_color="inverse")
k[2].metric("Renda média", f"R$ {df['renda_media'].mean():,.0f}".replace(",", "."))
k[3].metric("Pior UF (média)", f"{por_uf.index[-1]}", f"{por_uf.iloc[-1]:.1f}%", delta_color="off")
k[4].metric("Obs. em nível Crítico", f"{pct_critico:.1f}%")
st.divider()

tabs = st.tabs(["🏠 Visão geral", "📈 Análise temporal", "⚖️ Comparativos", "🗺️ Mapa", "🔗 Correlação", "🗂️ Dados"])

# ---------------------------------------------------------------- Visão geral
with tabs[0]:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Ranking de UFs")
        fig = px.bar(por_uf.reset_index(), x="taxa_desemprego", y="uf", orientation="h", color="taxa_desemprego",
                     color_continuous_scale="RdYlGn_r", labels={"taxa_desemprego": "Taxa média (%)", "uf": ""})
        fig.update_layout(height=520, coloraxis_showscale=False, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, width="stretch")
    with c2:
        st.subheader("Distribuição dos níveis de risco")
        r = df["nivel_risco"].value_counts().reindex(ORDEM_RISCO).fillna(0).reset_index()
        r.columns = ["nivel", "obs"]
        fig = px.pie(r, names="nivel", values="obs", hole=0.45, color="nivel", color_discrete_map=CORES_RISCO)
        fig.update_layout(height=520, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, width="stretch")
    st.info(
        f"**Interpretação:** com os filtros atuais, a taxa agregada é **{taxa_geral:.2f}%**. "
        f"**{por_uf.index[-1]}** apresenta a maior média ({por_uf.iloc[-1]:.1f}%) e **{por_uf.index[0]}** a menor "
        f"({por_uf.iloc[0]:.1f}%): uma diferença de **{por_uf.iloc[-1] - por_uf.iloc[0]:.1f} p.p.** entre extremos. "
        f"{pct_critico:.1f}% das observações estão no nível Crítico (taxa > 14%)."
    )

# ---------------------------------------------------------------- Temporal
with tabs[1]:
    st.subheader("Evolução trimestral da taxa de desemprego")
    cA, cB = st.columns([1, 1])
    agrup = cA.radio("Agrupar por", ["Região", "Brasil (filtro atual)"], horizontal=True)
    suav = cB.checkbox("Aplicar média móvel de 4 trimestres", value=True)
    if agrup == "Região":
        serie = df.groupby(["data", "regiao"]).apply(taxa_ponderada, include_groups=False).rename("taxa").reset_index()
        cor = "regiao"
    else:
        serie = por_trim.rename("taxa").reset_index()
        serie["regiao"] = "Brasil"
        cor = "regiao"
    if suav:
        serie["taxa"] = serie.groupby("regiao")["taxa"].transform(lambda s: s.rolling(4, min_periods=1).mean())
    fig = px.line(serie, x="data", y="taxa", color=cor, markers=True, labels={"taxa": "Taxa (%)", "data": ""})
    fig.add_vrect(x0="2020-01-01", x1="2021-12-31", fillcolor="red", opacity=0.08, line_width=0,
                  annotation_text="Pandemia", annotation_position="top left")
    fig.update_layout(height=450, hovermode="x unified")
    st.plotly_chart(fig, width="stretch")

    st.subheader("Mapa de calor: taxa média por UF e ano")
    pivot = df.pivot_table(index="uf", columns="ano", values="taxa_desemprego", aggfunc="mean")
    fig2, ax = plt.subplots(figsize=(11, max(3, 0.32 * len(pivot))))
    sns.heatmap(pivot, annot=True, fmt=".1f", cmap="YlOrRd", linewidths=.4, cbar_kws={"label": "%"}, ax=ax)
    ax.set_xlabel("")
    ax.set_ylabel("")
    st.pyplot(fig2)
    plt.close(fig2)
    anos_taxa = df.groupby("ano").apply(taxa_ponderada, include_groups=False)
    st.info(
        f"**Interpretação:** o pico anual do período filtrado foi **{anos_taxa.idxmax()}** ({anos_taxa.max():.2f}%) "
        f"e o menor nível, **{anos_taxa.idxmin()}** ({anos_taxa.min():.2f}%). A faixa vermelha marca 2020–2021: "
        "nesse intervalo as curvas de todas as regiões sobem, e voltam a cair em 2022."
    )

# ---------------------------------------------------------------- Comparativos
with tabs[2]:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Distribuição por região")
        fig, ax = plt.subplots(figsize=(6, 4))
        sns.boxplot(data=df, x="regiao", y="taxa_desemprego", hue="regiao", palette="Set2", legend=False, ax=ax)
        ax.set_xlabel("")
        ax.set_ylabel("Taxa (%)")
        st.pyplot(fig)
        plt.close(fig)
    with c2:
        st.subheader("Fase econômica × região")
        fase = df.groupby(["fase", "regiao"]).apply(taxa_ponderada, include_groups=False).rename("taxa").reset_index()
        ordem = ["Pré-pandemia (2015-19)", "Pandemia (2020-21)", "Pós-pandemia (2022-24)"]
        fig = px.bar(fase, x="regiao", y="taxa", color="fase", barmode="group", category_orders={"fase": ordem},
                     labels={"taxa": "Taxa (%)", "regiao": ""})
        fig.update_layout(height=400, margin=dict(t=10))
        st.plotly_chart(fig, width="stretch")
    c3, c4 = st.columns(2)
    with c3:
        st.subheader("Setor predominante")
        st_ = df.groupby("setor_predominante")["taxa_desemprego"].mean().sort_values().reset_index()
        fig = px.bar(st_, x="setor_predominante", y="taxa_desemprego", labels={"taxa_desemprego": "Taxa média (%)", "setor_predominante": ""})
        fig.update_layout(height=380)
        st.plotly_chart(fig, width="stretch")
    with c4:
        st.subheader("Níveis de risco por ano")
        ra = df.groupby(["ano", "nivel_risco"]).size().reset_index(name="n")
        fig = px.bar(ra, x="ano", y="n", color="nivel_risco", barmode="relative", color_discrete_map=CORES_RISCO,
                     category_orders={"nivel_risco": ORDEM_RISCO}, labels={"n": "Observações", "ano": ""})
        fig.update_layout(height=380)
        st.plotly_chart(fig, width="stretch")
    reg_t = df.groupby("regiao").apply(taxa_ponderada, include_groups=False).sort_values()
    st.info(
        f"**Interpretação:** a região com menor desemprego é **{reg_t.index[0]}** ({reg_t.iloc[0]:.1f}%) e a maior é "
        f"**{reg_t.index[-1]}** ({reg_t.iloc[-1]:.1f}%). O setor predominante muda pouco a taxa média — a "
        "diferença territorial pesa bem mais do que a composição setorial. Os níveis Crítico e Alto concentram-se em 2020–2021."
    )

# ---------------------------------------------------------------- Mapa
with tabs[3]:
    st.subheader("Mapa interativo por UF")
    ano_mapa = st.select_slider("Ano exibido", options=sorted(df["ano"].unique()), value=int(df["ano"].max()))
    m = (df[df["ano"] == ano_mapa].groupby(["uf", "regiao", "lat", "lon"])
         .agg(taxa=("taxa_desemprego", "mean"), ativa=("populacao_ativa", "mean"), renda=("renda_media", "mean"))
         .reset_index())
    fig = px.scatter_geo(m, lat="lat", lon="lon", size="ativa", color="taxa", hover_name="uf",
                         hover_data={"regiao": True, "taxa": ":.2f", "renda": ":.0f", "lat": False, "lon": False, "ativa": False},
                         color_continuous_scale="RdYlGn_r", size_max=35, text="uf", scope="south america",
                         labels={"taxa": "Taxa (%)"})
    fig.update_geos(fitbounds="locations", showcountries=True, showland=True, landcolor="#f1f1f1")
    fig.update_traces(textposition="middle center", textfont_size=9)
    fig.update_layout(height=600, margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig, width="stretch")
    top = m.sort_values("taxa", ascending=False).iloc[0]
    st.info(f"**Interpretação:** em {ano_mapa}, a UF mais crítica entre as selecionadas é **{top['uf']}** "
            f"({top['taxa']:.1f}%). O tamanho da bolha representa a população ativa média; a cor, a taxa de desemprego.")

# ---------------------------------------------------------------- Correlação
with tabs[4]:
    st.subheader("Correlação estatística")
    metodo = st.radio("Método", ["pearson", "spearman"], horizontal=True)
    c1, c2 = st.columns([1, 1])
    with c1:
        fig, ax = plt.subplots(figsize=(6, 4.5))
        sns.heatmap(df[COLS_NUM].corr(method=metodo), annot=True, fmt=".2f", cmap="coolwarm", center=0, vmin=-1, vmax=1, ax=ax)
        st.pyplot(fig)
        plt.close(fig)
    with c2:
        x = st.selectbox("Variável explicativa", [c for c in COLS_NUM if c != "taxa_desemprego"], index=3)
        r, p = (stats.pearsonr if metodo == "pearson" else stats.spearmanr)(df[x], df["taxa_desemprego"])
        fig = px.scatter(df, x=x, y="taxa_desemprego", color="regiao", opacity=.6, labels={"taxa_desemprego": "Taxa (%)"})
        b, a = np.polyfit(df[x], df["taxa_desemprego"], 1)
        xs = np.linspace(df[x].min(), df[x].max(), 50)
        fig.add_trace(go.Scatter(x=xs, y=a + b * xs, mode="lines", name="Tendência", line=dict(color="black", dash="dash")))
        fig.update_layout(height=420, margin=dict(t=10))
        st.plotly_chart(fig, width="stretch")
        st.metric(f"Coeficiente ({metodo})", f"{r:+.3f}", f"p-valor = {p:.3f}", delta_color="off")
    forca = "desprezível" if abs(r) < .1 else "fraca" if abs(r) < .3 else "moderada" if abs(r) < .6 else "forte"
    sig = "estatisticamente significativa" if p < .05 else "**não** significativa (p ≥ 0,05)"
    st.info(f"**Interpretação:** entre `{x}` e a taxa de desemprego, a correlação é **{forca}** (r = {r:+.3f}) e {sig}. "
            "Correlação não implica causalidade; em bases simuladas, relações independentes entre variáveis são esperadas.")

# ---------------------------------------------------------------- Dados
with tabs[5]:
    st.subheader("Resumo por UF")
    resumo = (df.groupby(["regiao", "uf"]).agg(
        taxa_media=("taxa_desemprego", "mean"), taxa_max=("taxa_desemprego", "max"), renda_media=("renda_media", "mean"),
        vagas_media=("vagas_formais", "mean"), inflacao_media=("inflacao", "mean")).round(2).reset_index()
        .sort_values("taxa_media", ascending=False))
    st.dataframe(resumo, width="stretch", hide_index=True)
    st.subheader("Dados filtrados")
    st.dataframe(df.drop(columns=["lat", "lon"]), width="stretch", hide_index=True)
    st.download_button("⬇️ Baixar CSV filtrado", df.to_csv(index=False).encode("utf-8"), "desemprego_filtrado.csv", "text/csv")

# ---------------------------------------------------------------- Conclusão (dinâmica)
reg_c = df.groupby("regiao").apply(taxa_ponderada, include_groups=False).sort_values()
gap_setor = df.groupby("setor_predominante")["taxa_desemprego"].mean()
corr_fortes = df[COLS_NUM].corr()["taxa_desemprego"].drop("taxa_desemprego").abs()
ORDEM_FASE = ["Pré-pandemia (2015-19)", "Pandemia (2020-21)", "Pós-pandemia (2022-24)"]
fase_t = df.groupby("fase").apply(taxa_ponderada, include_groups=False)
fase_t = fase_t.reindex([f for f in ORDEM_FASE if f in fase_t.index])
texto_fase = " → ".join(f"{f.split(' (')[0]}: {v:.1f}%" for f, v in fase_t.items())

st.divider()
st.header("📌 Conclusão executiva")
st.markdown(
    f"""
Com base nos filtros atualmente selecionados:

- **Território:** **{reg_c.index[-1]}** tem a maior taxa regional ({reg_c.iloc[-1]:.1f}%) e **{reg_c.index[0]}** a menor
  ({reg_c.iloc[0]:.1f}%). Entre UFs, **{por_uf.index[-1]}** ({por_uf.iloc[-1]:.1f}%) vs. **{por_uf.index[0]}** ({por_uf.iloc[0]:.1f}%):
  **{por_uf.iloc[-1] - por_uf.iloc[0]:.1f} p.p.** de diferença. Entre setores, a variação das médias é de apenas
  **{gap_setor.max() - gap_setor.min():.1f} p.p.**
- **Evolução:** taxa por fase econômica — {texto_fase}. O último trimestre filtrado fechou em **{taxa_ult:.2f}%**
  ({delta:+.2f} p.p. vs. o primeiro).
- **Risco:** **{pct_critico:.1f}%** das observações selecionadas estão em nível Crítico.
- **Fatores explicativos:** a maior correlação absoluta com a taxa é **{corr_fortes.idxmax()}** (|r| = {corr_fortes.max():.2f}) — 
  {"relação fraca, pouco explicativa" if corr_fortes.max() < .3 else "relação relevante que merece investigação"}. Correlação não implica causalidade.
- **Limitação:** dados simulados; recomenda-se repetir a análise com a PNAD Contínua/IBGE para decisões reais.
"""
)
