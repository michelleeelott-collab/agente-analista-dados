"""
Motor de análise seguro.
Recebe um PLANO (dicionário JSON gerado pelo agente) e executa com pandas.
Nunca executa código arbitrário: só operações pré-definidas e confiáveis.
Valores monetários são formatados no padrão brasileiro (R$ 1.234,56).
"""
import unicodedata
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import pandas as pd

AZUL, AMBAR, CINZA = "#1F4E79", "#E0902A", "#4A5560"
plt.rcParams.update({"axes.edgecolor": "#C9CCD1", "axes.linewidth": 0.8,
                     "figure.facecolor": "white", "axes.facecolor": "white"})

AGG = {"soma": "sum", "media": "mean", "contagem": "count",
       "maximo": "max", "minimo": "min"}

# Palavras que indicam que a coluna é de dinheiro
MOEDA_KEYS = ("valor", "faturament", "receita", "preco", "custo", "ticket",
              "montante", "salario", "lucro", "gasto", "despesa", "renda",
              "pagamento", "frete", "total")


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return s.lower().strip()


def _eh_moeda(nome):
    n = _norm(nome)
    return any(k in n for k in MOEDA_KEYS)


def fmt_br(x, moeda=False, casas=2):
    """Formata número no padrão BR: 1.234.567,89 (e R$ na frente se moeda)."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return str(x)
    s = f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}" if moeda else s


def _casas_rotulo(valores, moeda):
    if moeda:
        return 2
    return 0 if all(float(v).is_integer() for v in valores) else 2


def _achar_coluna(df, nome):
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


def _grafico_barra(serie, titulo, horizontal=False, moeda=False):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    eixo_fmt = FuncFormatter(lambda v, _: fmt_br(v, moeda, 0))
    casas = _casas_rotulo(serie.values, moeda)
    rotulos = [fmt_br(v, moeda, casas) for v in serie.values]
    if horizontal:
        s = serie[::-1]
        rot = [fmt_br(v, moeda, casas) for v in s.values]
        cores = [AMBAR if i == len(s) - 1 else AZUL for i in range(len(s))]
        bars = ax.barh(s.index.astype(str), s.values, color=cores)
        ax.bar_label(bars, labels=rot, padding=3, fontsize=8.5, color="#16202B")
        ax.xaxis.set_major_formatter(eixo_fmt)
        ax.margins(x=0.18)
        ax.grid(axis="x", color="#EEE")
    else:
        cores = [AMBAR if i == 0 else AZUL for i in range(len(serie))]
        bars = ax.bar(serie.index.astype(str), serie.values, color=cores)
        ax.bar_label(bars, labels=rotulos, padding=3, fontsize=8.5, color="#16202B")
        ax.yaxis.set_major_formatter(eixo_fmt)
        ax.margins(y=0.18)
        plt.xticks(rotation=30, ha="right")
        ax.grid(axis="y", color="#EEE")
    ax.set_title(titulo, fontweight="bold", color="#16202B", loc="left")
    fig.tight_layout()
    return fig


def _grafico_linha(serie, titulo, moeda=False):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = range(len(serie))
    ax.plot(x, serie.values, marker="o", color=AZUL, lw=2.2)
    ax.fill_between(x, serie.values, alpha=0.08, color=AZUL)
    ax.set_xticks(list(x))
    ax.set_xticklabels(serie.index.astype(str), rotation=30, ha="right")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: fmt_br(v, moeda, 0)))
    ax.set_title(titulo, fontweight="bold", color="#16202B", loc="left")
    ax.grid(color="#EEE")
    fig.tight_layout()
    return fig


def _grafico_pizza(serie, titulo, moeda=False):
    fig, ax = plt.subplots(figsize=(6, 5))
    cores = [AZUL, AMBAR, CINZA, "#5E86AB", "#C0392B", "#7FA9CE", "#E8B563"]
    ax.pie(serie.values, labels=serie.index.astype(str), autopct="%1.1f%%",
           colors=[cores[i % len(cores)] for i in range(len(serie))],
           textprops={"fontsize": 9})
    ax.set_title(titulo, fontweight="bold", color="#16202B")
    fig.tight_layout()
    return fig


def _formatar_coluna(tabela, coluna, moeda, casas=2):
    tabela = tabela.copy()
    tabela[coluna] = tabela[coluna].apply(lambda v: fmt_br(v, moeda, casas))
    return tabela


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
        moeda = _eh_moeda(col)
        desc = dff[col].describe()
        tabela = desc.reset_index()
        tabela.columns = ["Métrica", col]
        tabela[col] = tabela.apply(
            lambda r: fmt_br(r[col], moeda and r["Métrica"] != "count",
                             0 if r["Métrica"] == "count" else 2), axis=1)
        return tabela, None, f"Resumo estatístico de {col}."

    # ---- Contagem de categorias ----
    if op == "contar_categorias":
        cat = _achar_coluna(dff, plano.get("coluna_categoria"))
        serie = dff[cat].value_counts()
        if plano.get("top_n"):
            serie = serie.head(int(plano["top_n"]))
        fig = (_grafico_pizza(serie, titulo) if graf == "pizza"
               else _grafico_barra(serie, titulo, horizontal=(graf == "barra_horizontal")))
        tabela = serie.reset_index()
        tabela.columns = [cat, "quantidade"]
        tabela = _formatar_coluna(tabela, "quantidade", moeda=False, casas=0)
        return tabela, fig, f"Contagem por {cat}."

    # ---- Tendência temporal ----
    if op == "tendencia_temporal":
        tcol = _achar_coluna(dff, plano.get("coluna_tempo"))
        val = _achar_coluna(dff, plano.get("coluna_valor"))
        moeda = _eh_moeda(val) and ag != "count"
        tmp = dff.copy()
        tmp[tcol] = pd.to_datetime(tmp[tcol], errors="coerce")
        tmp = tmp.dropna(subset=[tcol])
        serie = tmp.groupby(tmp[tcol].dt.to_period("M"))[val].agg(ag)
        serie.index = serie.index.astype(str)
        fig = _grafico_linha(serie, titulo, moeda=moeda)
        tabela = serie.reset_index()
        col_nome = f"{plano.get('agregacao','soma')}_{val}"
        tabela.columns = ["mês", col_nome]
        tabela = _formatar_coluna(tabela, col_nome, moeda=moeda)
        return tabela, fig, f"Evolução de {val} ao longo do tempo."

    # ---- Agrupar / Top N (padrão) ----
    cat = _achar_coluna(dff, plano.get("coluna_categoria"))
    val = _achar_coluna(dff, plano.get("coluna_valor"))
    moeda = _eh_moeda(val) and ag != "count"
    serie = dff.groupby(cat)[val].agg(ag)
    ordem = plano.get("ordenar", "desc")
    serie = serie.sort_values(ascending=(ordem == "asc"))
    if plano.get("top_n"):
        serie = serie.head(int(plano["top_n"]))
    if graf == "pizza":
        fig = _grafico_pizza(serie, titulo, moeda=moeda)
    elif graf == "linha":
        fig = _grafico_linha(serie, titulo, moeda=moeda)
    elif graf == "nenhum":
        fig = None
    else:
        fig = _grafico_barra(serie, titulo, horizontal=(graf == "barra_horizontal"), moeda=moeda)
    tabela = serie.reset_index()
    col_nome = f"{plano.get('agregacao','soma')}_{val}"
    tabela.columns = [cat, col_nome]
    tabela = _formatar_coluna(tabela, col_nome, moeda=moeda,
                              casas=_casas_rotulo(serie.values, moeda))
    return tabela, fig, f"{plano.get('agregacao','soma')} de {val} por {cat}."
