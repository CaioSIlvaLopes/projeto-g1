"""Camada de dados: modelo relacional (SQLAlchemy + SQLite), limpeza e engenharia de atributos."""
from pathlib import Path

import pandas as pd
from sqlalchemy import Float, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

RAIZ = Path(__file__).resolve().parent.parent
CSV = RAIZ / "dados" / "simulacao_desemprego_brasil.csv"
DB_PATH = RAIZ / "database" / "desemprego.db"

# Centroides aproximados das UFs (lat, lon) para o mapa interativo
COORDS = {
    "AM": (-3.47, -65.10), "PA": (-3.79, -52.48), "RO": (-10.83, -63.34), "TO": (-10.18, -48.33),
    "BA": (-12.58, -41.70), "PE": (-8.38, -37.86), "CE": (-5.50, -39.32), "MA": (-5.42, -45.44),
    "PB": (-7.24, -36.78), "DF": (-15.78, -47.93), "GO": (-15.83, -49.84), "MT": (-12.64, -55.42),
    "MS": (-20.51, -54.54), "SP": (-22.19, -48.79), "RJ": (-22.25, -42.66), "MG": (-18.10, -44.38),
    "ES": (-19.19, -40.34), "PR": (-24.89, -51.55), "SC": (-27.45, -50.95), "RS": (-30.17, -53.50),
}
ORDEM_RISCO = ["Baixo", "Médio", "Alto", "Crítico"]


class Base(DeclarativeBase):
    pass


class Regiao(Base):
    __tablename__ = "regioes"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(20), unique=True)
    ufs: Mapped[list["UF"]] = relationship(back_populates="regiao")


class UF(Base):
    __tablename__ = "ufs"
    sigla: Mapped[str] = mapped_column(String(2), primary_key=True)
    regiao_id: Mapped[int] = mapped_column(ForeignKey("regioes.id"))
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    regiao: Mapped["Regiao"] = relationship(back_populates="ufs")


class Observacao(Base):
    __tablename__ = "observacoes"
    id: Mapped[int] = mapped_column(primary_key=True)
    data: Mapped[str] = mapped_column(String(10))
    ano: Mapped[int] = mapped_column(Integer)
    trimestre: Mapped[int] = mapped_column(Integer)
    uf_sigla: Mapped[str] = mapped_column(ForeignKey("ufs.sigla"))
    populacao_ativa: Mapped[int] = mapped_column(Integer)
    empregados: Mapped[int] = mapped_column(Integer)
    desempregados: Mapped[int] = mapped_column(Integer)
    taxa_desemprego: Mapped[float] = mapped_column(Float)
    renda_media: Mapped[float] = mapped_column(Float)
    setor_predominante: Mapped[str] = mapped_column(String(20))
    vagas_formais: Mapped[int] = mapped_column(Integer)
    inflacao: Mapped[float] = mapped_column(Float)
    nivel_risco: Mapped[str] = mapped_column(String(10))


def limpar(df: pd.DataFrame) -> pd.DataFrame:
    """Limpeza: tipos, duplicatas, textos padronizados e valores inválidos."""
    df = df.copy()
    df["data"] = pd.to_datetime(df["data"])
    for c in ["regiao", "uf", "setor_predominante", "nivel_risco"]:
        df[c] = df[c].astype(str).str.strip()
    df["uf"] = df["uf"].str.upper()
    df = df.drop_duplicates(["data", "uf"]).dropna()
    df = df[(df["populacao_ativa"] > 0) & (df["taxa_desemprego"].between(0, 100))]
    return df.reset_index(drop=True)


def engenharia(df: pd.DataFrame) -> pd.DataFrame:
    """Novos atributos: período, fase econômica, vagas por mil ativos, média móvel e variação anual."""
    df = df.sort_values(["uf", "data"]).copy()
    df["periodo"] = df["ano"].astype(str) + "-T" + df["trimestre"].astype(str)
    df["fase"] = pd.cut(
        df["ano"], [2014, 2019, 2021, 2100],
        labels=["Pré-pandemia (2015-19)", "Pandemia (2020-21)", "Pós-pandemia (2022-24)"],
    ).astype(str)
    df["vagas_por_mil"] = df["vagas_formais"] / df["populacao_ativa"] * 1000
    df["renda_real_proxy"] = df["renda_media"] / (1 + df["inflacao"] / 100)
    df["mm4_taxa"] = df.groupby("uf")["taxa_desemprego"].transform(lambda s: s.rolling(4, min_periods=1).mean())
    df["var_anual_pp"] = df.groupby("uf")["taxa_desemprego"].diff(4)
    df["lat"] = df["uf"].map(lambda u: COORDS[u][0])
    df["lon"] = df["uf"].map(lambda u: COORDS[u][1])
    df["nivel_risco"] = pd.Categorical(df["nivel_risco"], ORDEM_RISCO, ordered=True)
    return df.sort_values(["data", "regiao", "uf"]).reset_index(drop=True)


def taxa_ponderada(g: pd.DataFrame) -> float:
    """Taxa agregada correta: soma dos desempregados / soma da população ativa."""
    return g["desempregados"].sum() / g["populacao_ativa"].sum() * 100


def criar_banco(csv: Path = CSV, db_path: Path = DB_PATH) -> None:
    """Lê o CSV, limpa e persiste em 3 tabelas relacionadas no SQLite."""
    df = limpar(pd.read_csv(csv))
    db_path.parent.mkdir(exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        regs = {n: Regiao(nome=n) for n in sorted(df["regiao"].unique())}
        s.add_all(regs.values())
        s.flush()
        for uf, reg in df.drop_duplicates("uf")[["uf", "regiao"]].itertuples(index=False):
            s.add(UF(sigla=uf, regiao_id=regs[reg].id, lat=COORDS[uf][0], lon=COORDS[uf][1]))
        s.flush()
        cols = ["ano", "trimestre", "populacao_ativa", "empregados", "desempregados", "taxa_desemprego",
                "renda_media", "setor_predominante", "vagas_formais", "inflacao", "nivel_risco"]
        s.add_all(
            Observacao(data=r.data.strftime("%Y-%m-%d"), uf_sigla=r.uf, **{c: getattr(r, c) for c in cols})
            for r in df.itertuples()
        )
        s.commit()


CONSULTA = """
SELECT o.data, o.ano, o.trimestre, r.nome AS regiao, o.uf_sigla AS uf, o.populacao_ativa, o.empregados,
       o.desempregados, o.taxa_desemprego, o.renda_media, o.setor_predominante, o.vagas_formais,
       o.inflacao, o.nivel_risco
FROM observacoes o JOIN ufs u ON u.sigla = o.uf_sigla JOIN regioes r ON r.id = u.regiao_id
"""


def carregar_do_banco() -> pd.DataFrame:
    """Integra as 3 tabelas via JOIN e devolve o DataFrame já com atributos derivados."""
    if not DB_PATH.exists():
        criar_banco()
    engine = create_engine(f"sqlite:///{DB_PATH}")
    df = pd.read_sql(CONSULTA, engine, parse_dates=["data"])
    return engenharia(df)


if __name__ == "__main__":
    criar_banco()
    print(f"Banco criado em {DB_PATH} com {len(carregar_do_banco())} observações.")
