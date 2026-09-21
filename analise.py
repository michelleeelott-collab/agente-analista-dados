"""
Motor de análise seguro.
Recebe um PLANO (dicionário JSON gerado pelo agente) e executa com pandas.
Nunca executa código arbitrário: só operações pré-definidas e confiáveis.
"""
import unicodedata
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

AZUL, AMBAR, CINZA = "#1F4E79", "#E0902A", "#4A5560"
plt.rcParams.update({"axes.edgecolor": "#C9CCD1", "axes.linewidth": 0.8,
                     "figure.facecolor": "white", "axes.facecolor": "white"})

AGG = {"soma": "sum", "media": "mean", "contagem": "count",
       "maximo": "max", "minimo": "min"}


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return s.lower().strip()


def _achar_coluna(df, nome):
    """Encontra a coluna real correspondente (tolerante a acento/caixa)."""
    if nome is None:
        return None
    if nome in df.columns:
        return nome
    alvo = _norm(nome)
    for c in df.columns:
        if _norm(c) == alvo:
            return c
    raise ValueError(f"Coluna '{nome}' não existe. Disponíveis: {list(df.columns)}")


def _aplicar_filtro(df, filtro):
    if not filtro:
        return df
    col = _achar_coluna(df, filtro.get("coluna"))
    op = filtro.get("operador", "==")
    val = filtro.get("valor")
    serie = df[col]
    try:
        if op == "==":   return df[serie.astype(str) == str(val)]
        if op == "!=":   return df[serie.astype(str) != str(val)]
        if op == "contem": return df[serie.astype(str).str.contains(str(val), case=False, na=False)]
        val_num = float(val)
        if op == ">":  return df[pd.to_numeric(serie, errors="coerce") > val_num]
        if op == "<":  return df[pd.to_numeric(serie, errors="coerce") < val_num]
        if op == ">=": return df[pd.to_numeric(serie, errors="coerce") >= val_num]
        if op == "<=": return df[pd.to_numeric(serie, errors="coerce") <= val_num]
    except Exception:
        return df
    return df


def _grafico_barra(serie, titulo, horizontal=False):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    cores = [AMBAR if i == (len(serie) - 1 if horizontal else 0) else AZUL
             for i in range(len(serie))]
    if horizontal:
        serie = serie[::-1]
        ax.barh(serie.index.astype(str), serie.values, color=cores)
    else:
        ax.bar(serie.index.astype(str), serie.values, color=AZUL)
        plt.xticks(rotation=30, ha="right")
    ax.set_title(titulo, fontweight="bold", color="#16202B", loc="left")
    ax.grid(axis="x" if horizontal else "y", color="#EEE")
    fig.tight_layout()
    return fig


def _grafico_linha(serie, titulo):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(serie.index.astype(str), serie.values, marker="o", color=AZUL, lw=2.2)
    ax.fill_between(range(len(serie)), serie.values, alpha=0.08, color=AZUL)
    ax.set_title(titulo, fontweight="bold", color="#16202B", loc="left")
    plt.xticks(rotation=30, ha="right")
    ax.grid(color="#EEE")
    fig.tight_layout()
    return fig


def _grafico_pizza(serie, titulo):
    fig, ax = plt.subplots(figsize=(6, 5))
    cores = [AZUL, AMBAR, CINZA, "#5E86AB", "#C0392B", "#7FA9CE", "#E8B563"]
    ax.pie(serie.values, labels=serie.index.astype(str), autopct="%1.1f%%",
           colors=[cores[i % len(cores)] for i in range(len(serie))],
           textprops={"fontsize": 9})
    ax.set_title(titulo, fontweight="bold", color="#16202B")
    fig.tight_layout()
    return fig


def executar_plano(df, plano):
    """Executa o plano e devolve (tabela_resultado, figura, resumo_texto)."""
    op = plano.get("operacao", "agrupar")
    ag = AGG.get(plano.get("agregacao", "soma"), "sum")
    graf = plano.get("grafico", "barra")
    titulo = plano.get("titulo", "Resultado")
    dff = _aplicar_filtro(df, plano.get("filtro"))
    if len(dff) == 0:
        raise ValueError("Nenhum registro atende ao filtro pedido.")

    # ---- Resumo estatístico ----
    if op == "resumo":
        col = _achar_coluna(dff, plano.get("coluna_valor"))
        desc = dff[col].describe().round(2)
        tabela = desc.reset_index()
        tabela.columns = ["Métrica", col]
        return tabela, None, f"Resumo estatístico de {col}."

    # ---- Contagem de categorias ----
    if op == "contar_categorias":
        cat = _achar_coluna(dff, plano.get("coluna_categoria"))
        serie = dff[cat].value_counts()
        if plano.get("top_n"):
            serie = serie.head(int(plano["top_n"]))
        tabela = serie.reset_index()
        tabela.columns = [cat, "quantidade"]
        fig = (_grafico_pizza(serie, titulo) if graf == "pizza"
               else _grafico_barra(serie, titulo, horizontal=(graf == "barra_horizontal")))
        return tabela, fig, f"Contagem por {cat}."

    # ---- Tendência temporal ----
    if op == "tendencia_temporal":
        tcol = _achar_coluna(dff, plano.get("coluna_tempo"))
        val = _achar_coluna(dff, plano.get("coluna_valor"))
        tmp = dff.copy()
        tmp[tcol] = pd.to_datetime(tmp[tcol], errors="coerce")
        tmp = tmp.dropna(subset=[tcol])
        serie = tmp.groupby(tmp[tcol].dt.to_period("M"))[val].agg(ag)
        serie.index = serie.index.astype(str)
        tabela = serie.reset_index()
        tabela.columns = ["mês", f"{plano.get('agregacao','soma')}_{val}"]
        fig = _grafico_linha(serie, titulo)
        return tabela, fig, f"Evolução de {val} ao longo do tempo."

    # ---- Agrupar / Top N (padrão) ----
    cat = _achar_coluna(dff, plano.get("coluna_categoria"))
    val = _achar_coluna(dff, plano.get("coluna_valor"))
    serie = dff.groupby(cat)[val].agg(ag)
    ordem = plano.get("ordenar", "desc")
    serie = serie.sort_values(ascending=(ordem == "asc"))
    if plano.get("top_n"):
        serie = serie.head(int(plano["top_n"]))
    serie = serie.round(2)
    tabela = serie.reset_index()
    tabela.columns = [cat, f"{plano.get('agregacao','soma')}_{val}"]
    if graf == "pizza":
        fig = _grafico_pizza(serie, titulo)
    elif graf == "linha":
        fig = _grafico_linha(serie, titulo)
    elif graf == "nenhum":
        fig = None
    else:
        fig = _grafico_barra(serie, titulo, horizontal=(graf == "barra_horizontal"))
    return tabela, fig, f"{plano.get('agregacao','soma')} de {val} por {cat}."
