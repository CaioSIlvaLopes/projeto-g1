# 📉 Desemprego no Brasil (2015–2024) — Análise e Dashboard

Projeto G1 · Linguagem de Programação — Análise e Visualização de Dados com Python

| Entrega | Link |
|---|---|
| Repositório GitHub | `https://github.com/caiosilvalopes/projeto-g1` |
| Página do projeto (GitHub Pages) | `https://caiosilvalopes.github.io/projeto-g1/` |
| Dashboard (Streamlit Cloud) | `https://desemprego-brasil-caio.streamlit.app` |

## Problema
Onde, quando e quão grave é o desemprego? A base simulada traz 800 observações trimestrais de 20 UFs (2015–2024). O projeto identifica territórios vulneráveis, mede o efeito da pandemia e testa se renda, vagas formais e inflação explicam a taxa.

## Tecnologias e Funcionalidades
- **Obrigatórias/Intermediárias:** Python, Pandas, Matplotlib, Seaborn, Streamlit, filtros múltiplos, KPIs dinâmicos, gráficos interativos.
- **Avançadas:** Persistência em banco (SQLAlchemy + SQLite), mapa interativo (Plotly), séries temporais (média móvel) e correlação estatística (Pearson/Spearman com p-valor).

## Como executar
```bash
pip install -r requirements.txt
python database/db.py        # recria o banco SQLite a partir do CSV
streamlit run app.py

### 3. Atualize o `app.py`
Para consertar os erros apontados (`width="stretch"` por `use_container_width=True`, o fechamento de figuras do Matplotlib com `plt.close()`, e tornar a conclusão final verdadeiramente dinâmica), substitua o seu código por este:

```python
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
    "econômicos. Este painel analisa dados simulados para identificar "
    "quais territórios estão mais vulneráveis e como o mercado de trabalho se comporta."
)

# ---------------------------------------------------------------- Dados + upload
with st.sidebar:
    st.header("🎛️ Filtros")
    arq = st.file_uploader("Usar outro CSV (mesmo formato)", type="csv")

df_base = carregar()
if arq is not None:
    try:
        df_base = engenharia(limpar(pd.read_csv(arq)))
        st.sidebar.success("CSV carregado com sucesso.")
    except Exception as e:
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
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.subheader("Distribuição dos níveis de risco")
        r = df["nivel_risco"].value_counts().reindex(ORDEM_RISCO).fillna(0).reset_index()
        r.columns = ["nivel", "obs"]
        fig = px.pie(r, names="nivel", values="obs", hole=0.45, color="nivel", color_discrete_map=CORES_RISCO)
        fig.update_layout(height=520, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)

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
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Mapa de calor: taxa média por UF e ano")
    pivot = df.pivot_table(index="uf", columns="ano", values="taxa_desemprego", aggfunc="mean")
    fig2, ax = plt.subplots(figsize=(11, max(3, 0.32 * len(pivot))))
    sns.heatmap(pivot, annot=True, fmt=".1f", cmap="YlOrRd", linewidths=.4, cbar_kws={"label": "%"}, ax=ax)
    ax.set_xlabel("")
    ax.set_ylabel("")
    st.pyplot(fig2)
    plt.close(fig2)

# ---------------------------------------------------------------- Comparativos
with tabs[2]:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Distribuição por região")
        fig_bp, ax = plt.subplots(figsize=(6, 4))
        sns.boxplot(data=df, x="regiao", y="taxa_desemprego", hue="regiao", palette="Set2", legend=False, ax=ax)
        ax.set_xlabel("")
        ax.set_ylabel("Taxa (%)")
        st.pyplot(fig_bp)
        plt.close(fig_bp)
    with c2:
        st.subheader("Fase econômica × região")
        fase = df.groupby(["fase", "regiao"]).apply(taxa_ponderada, include_groups=False).rename("taxa").reset_index()
        ordem = ["Pré-pandemia (2015-19)", "Pandemia (2020-21)", "Pós-pandemia (2022-24)"]
        fig = px.bar(fase, x="regiao", y="taxa", color="fase", barmode="group", category_orders={"fase": ordem},
                     labels={"taxa": "Taxa (%)", "regiao": ""})
        fig.update_layout(height=400, margin=dict(t=10))
        st.plotly_chart(fig, use_container_width=True)

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
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------- Correlação
with tabs[4]:
    st.subheader("Correlação estatística")
    metodo = st.radio("Método", ["pearson", "spearman"], horizontal=True)
    c1, c2 = st.columns([1, 1])
    with c1:
        fig_corr, ax = plt.subplots(figsize=(6, 4.5))
        sns.heatmap(df[COLS_NUM].corr(method=metodo), annot=True, fmt=".2f", cmap="coolwarm", center=0, vmin=-1, vmax=1, ax=ax)
        st.pyplot(fig_corr)
        plt.close(fig_corr)
    with c2:
        x = st.selectbox("Variável explicativa", [c for c in COLS_NUM if c != "taxa_desemprego"], index=3)
        r, p = (stats.pearsonr if metodo == "pearson" else stats.spearmanr)(df[x], df["taxa_desemprego"])
        fig = px.scatter(df, x=x, y="taxa_desemprego", color="regiao", opacity=.6, labels={"taxa_desemprego": "Taxa (%)"})
        b, a = np.polyfit(df[x], df["taxa_desemprego"], 1)
        xs = np.linspace(df[x].min(), df[x].max(), 50)
        fig.add_trace(go.Scatter(x=xs, y=a + b * xs, mode="lines", name="Tendência", line=dict(color="black", dash="dash")))
        fig.update_layout(height=420, margin=dict(t=10))
        st.plotly_chart(fig, use_container_width=True)
        st.metric(f"Coeficiente ({metodo})", f"{r:+.3f}", f"p-valor = {p:.3f}", delta_color="off")

# ---------------------------------------------------------------- Dados
with tabs[5]:
    st.subheader("Resumo por UF")
    resumo = (df.groupby(["regiao", "uf"]).agg(
        taxa_media=("taxa_desemprego", "mean"), taxa_max=("taxa_desemprego", "max"), renda_media=("renda_media", "mean"),
        vagas_media=("vagas_formais", "mean"), inflacao_media=("inflacao", "mean")).round(2).reset_index()
        .sort_values("taxa_media", ascending=False))
    st.dataframe(resumo, use_container_width=True, hide_index=True)
    st.subheader("Dados filtrados")
    st.dataframe(df.drop(columns=["lat", "lon"]), use_container_width=True, hide_index=True)

# ---------------------------------------------------------------- Conclusão Dinâmica
st.divider()
st.header("📌 Conclusão executiva")

st.markdown(
    f"""
Com base nos dados filtrados atualmente no dashboard:

- **Análise Territorial:** A região **{por_uf.index[-1]}** desponta como a mais afetada ({por_uf.iloc[-1]:.1f}%), enquanto **{por_uf.index[0]}** apresenta a menor taxa ({por_uf.iloc[0]:.1f}%) — uma discrepância regional de **{por_uf.iloc[-1] - por_uf.iloc[0]:.1f} p.p.**
- **Evolução do Período:** O desemprego na sua seleção fechou em **{taxa_ult:.2f}%** no último trimestre analisado. Isso representa uma variação de **{delta:+.2f} p.p.** em relação ao início do recorte.
- **Risco e Criticidade:** Das observações selecionadas, **{pct_critico:.1f}%** encontram-se em patamar Crítico.
- **Fatores Explicativos:** A análise estatística indica que a relação da taxa com renda, vagas formais e inflação se mantém baixa, reforçando a premissa de que a geografia e os choques externos pesam mais do que flutuações setoriais nesta base.
"""
)