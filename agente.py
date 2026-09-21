"""
Cérebro do agente: conversa com o LLM (Groq) em duas etapas.
1. PLANEJAR  -> transforma a pergunta em um plano estruturado (JSON).
2. EXPLICAR  -> lê o resultado calculado e escreve o insight em português.
"""
import json
from groq import Groq


def criar_cliente(api_key):
    return Groq(api_key=api_key)


def _descrever_dados(df, n=3):
    """Monta uma descrição compacta das colunas para o LLM entender a base."""
    linhas = []
    for col in df.columns:
        tipo = "número" if str(df[col].dtype).startswith(("int", "float")) else "texto/categoria"
        exemplos = ", ".join(map(str, df[col].dropna().unique()[:4]))
        linhas.append(f'- "{col}" ({tipo}); exemplos: {exemplos}')
    return "\n".join(linhas)


PROMPT_PLANEJADOR = """Você é um agente analista de dados. Sua tarefa é transformar a
pergunta do usuário em um PLANO de análise no formato JSON, escolhendo as colunas
reais da tabela. Responda APENAS com o JSON, sem texto antes ou depois.

Colunas disponíveis na tabela:
{schema}

Formato do JSON (use somente estes campos e valores):
{{
  "operacao": "agrupar" | "top_n" | "tendencia_temporal" | "contar_categorias" | "resumo",
  "coluna_valor": "<coluna numérica>" ou null,
  "coluna_categoria": "<coluna de texto>" ou null,
  "coluna_tempo": "<coluna de data>" ou null,
  "agregacao": "soma" | "media" | "contagem" | "maximo" | "minimo",
  "filtro": {{"coluna": "<coluna>", "operador": "==" | "!=" | ">" | "<" | "contem", "valor": <valor>}} ou null,
  "top_n": <número> ou null,
  "ordenar": "desc" | "asc",
  "grafico": "barra" | "barra_horizontal" | "linha" | "pizza" | "nenhum",
  "titulo": "<título curto do resultado>"
}}

Regras:
- Use "top_n" quando pedirem "os maiores", "top", "ranking".
- Use "tendencia_temporal" para evolução ao longo do tempo/meses (precisa de coluna_tempo).
- Use "contar_categorias" para "quantos por..." / "distribuição de...".
- Escolha "grafico" adequado (linha para tempo, barra para ranking, pizza para proporção).
- Só use nomes de coluna que existem na lista acima."""


def gerar_plano(client, modelo, pergunta, df):
    schema = _descrever_dados(df)
    resp = client.chat.completions.create(
        model=modelo,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": PROMPT_PLANEJADOR.format(schema=schema)},
            {"role": "user", "content": pergunta},
        ],
    )
    texto = resp.choices[0].message.content
    return json.loads(texto)


PROMPT_EXPLICADOR = """Você é um analista de dados. Com base na pergunta do usuário e na
tabela de resultado já calculada, escreva uma resposta curta e clara em português
(2 a 4 frases). Destaque o número ou a categoria mais importante. Não invente dados:
use apenas o que está na tabela. Não use travessão."""


def explicar_resultado(client, modelo, pergunta, tabela):
    tabela_txt = tabela.head(15).to_markdown(index=False)
    resp = client.chat.completions.create(
        model=modelo,
        temperature=0.3,
        messages=[
            {"role": "system", "content": PROMPT_EXPLICADOR},
            {"role": "user", "content": f"Pergunta: {pergunta}\n\nResultado:\n{tabela_txt}"},
        ],
    )
    return resp.choices[0].message.content.strip()
