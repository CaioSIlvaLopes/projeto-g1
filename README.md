# 📉 Desemprego no Brasil (2015–2024) — Análise e Dashboard

Projeto G1 · Linguagem de Programação — Análise e Visualização de Dados com Python

| Entrega | Link |
|---|---|
| Repositório GitHub | `https://github.com/SEU-USUARIO/projeto-g1` |
| Página do projeto (GitHub Pages) | `https://SEU-USUARIO.github.io/projeto-g1/` |
| Dashboard (Streamlit Cloud) | `https://SEU-APP.streamlit.app` |

## Problema
Onde, quando e quão grave é o desemprego? A base simulada traz 800 observações trimestrais de 20 UFs (2015–2024). O projeto identifica territórios vulneráveis, mede o efeito da pandemia e testa se renda, vagas formais e inflação explicam a taxa.

## Tecnologias
Python · Pandas · Matplotlib · Seaborn · Streamlit · GitHub · **Plotly** · **SQLAlchemy + SQLite** · SciPy

## Funcionalidades
- **Intermediárias:** filtros múltiplos, KPIs dinâmicos, gráficos interativos, análise temporal, dashboard em abas, visualizações comparativas, análise geográfica, integração entre tabelas, upload de CSV.
- **Avançadas:** persistência em banco (SQLAlchemy + SQLite, 3 tabelas relacionadas), modelagem relacional, mapa interativo (Plotly), séries temporais (média móvel 4T, variação anual) e correlação estatística (Pearson/Spearman com p-valor).

## Estrutura
```
projeto-g1/
├── app.py                 # dashboard Streamlit
├── requirements.txt
├── README.md
├── index.html             # página do projeto (GitHub Pages)
├── dados/                 # CSV original
├── database/              # db.py (modelo, limpeza, features) e desemprego.db
├── notebooks/             # analise_desemprego.ipynb
└── imagens/               # gráficos exportados pelo notebook
```

## Como executar
```bash
pip install -r requirements.txt
python database/db.py        # (opcional) recria o banco SQLite a partir do CSV
streamlit run app.py
```

## Principais resultados
- Nordeste (13,2%) e Norte (10,9%) lideram; Sul (6,8%) tem a menor taxa. Extremos entre UFs: CE 13,7% vs. PR 6,7%.
- Pandemia: 9,9% → 11,3% (2020–21) → 9,0% (2022–24); níveis Críticos de 11% para 22,5%.
- Renda, vagas e inflação: correlação ≈ 0 (|r| < 0,03; p > 0,49).

> Base simulada para fins didáticos. Metodologia: taxas agregadas são **ponderadas** pela população ativa.
