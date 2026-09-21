"""
Converse com seus Dados — Agente Analista de Dados
Sobe uma planilha, pergunta em português e o agente responde com texto e gráfico.

Arquitetura (agente em 3 passos):
  1. PLANEJAR  -> o LLM (Groq) transforma a pergunta em um plano JSON.
  2. EXECUTAR  -> o app roda o plano com pandas (código seguro, sem exec).
  3. EXPLICAR  -> o LLM interpreta o resultado em linguagem natural.
"""
import json
import pandas as pd
import streamlit as st

from analise import executar_plano
from agente import criar_cliente, gerar_plano, explicar_resultado

st.set_page_config(page_title="Converse com seus Dados", page_icon="📊", layout="wide")

# ----------------------- Barra lateral -----------------------
with st.sidebar:
    st.title("📊 Converse com seus Dados")
    st.markdown("Um agente de IA que analisa planilhas e responde em português.")

    groq_api_key = st.text_input("🔑 API Key da Groq", type="password",
                                 help="Gratuita em https://console.groq.com/keys")
    modelo = st.selectbox("Modelo", ["llama-3.3-70b-versatile",
                                     "llama-3.1-8b-instant", "openai/gpt-oss-20b"])

    st.markdown("---")
    st.markdown("**Fonte dos dados**")
    fonte = st.radio("Escolha:", ["Usar dados de exemplo", "Enviar minha planilha (CSV)"],
                     label_visibility="collapsed")
    arquivo = None
    if fonte == "Enviar minha planilha (CSV)":
        arquivo = st.file_uploader("CSV", type=["csv"])

    st.markdown("---")
    st.caption("Desenvolvido por Michelle Lott. IA pode cometer erros; confira os resultados.")
    st.markdown("🔗 [Portfólio](https://michelleeelott-collab.github.io/)")

# ----------------------- Carregar dados -----------------------
@st.cache_data
def carregar_exemplo():
    return pd.read_csv("dados_exemplo.csv")

if arquivo is not None:
    df = pd.read_csv(arquivo)
    origem = "sua planilha"
else:
    df = carregar_exemplo()
    origem = "dados de exemplo (vendas fictícias)"

# ----------------------- Cabeçalho -----------------------
st.title("Converse com seus Dados 📊")
st.caption("Faça uma pergunta em português e o agente responde com análise e gráfico.")

with st.expander(f"👀 Ver a base carregada — {origem} ({len(df)} linhas, {len(df.columns)} colunas)"):
    st.dataframe(df.head(20), use_container_width=True)

# ----------------------- Sugestões -----------------------
st.markdown("**Experimente perguntar:**")
sugestoes = [
    "Quais os 5 produtos que mais faturaram?",
    "Qual o faturamento por região?",
    "Mostre a tendência de vendas ao longo dos meses",
    "Quantas vendas ficaram abaixo da meta em cada estado?",
]
cols = st.columns(len(sugestoes))
pergunta_clicada = None
for c, s in zip(cols, sugestoes):
    if c.button(s, use_container_width=True):
        pergunta_clicada = s

# ----------------------- Histórico -----------------------
if "hist" not in st.session_state:
    st.session_state.hist = []

pergunta = st.chat_input("Pergunte algo sobre os dados...") or pergunta_clicada

# ----------------------- Fluxo do agente -----------------------
if pergunta:
    if not groq_api_key:
        st.warning("Insira sua API Key da Groq na barra lateral para começar. "
                   "É gratuita em console.groq.com/keys")
        st.stop()

    with st.chat_message("user"):
        st.markdown(pergunta)

    with st.chat_message("assistant"):
        try:
            client = criar_cliente(groq_api_key)
            with st.spinner("🧠 O agente está planejando a análise..."):
                plano = gerar_plano(client, modelo, pergunta, df)
            with st.spinner("⚙️ Executando a análise..."):
                tabela, fig, _ = executar_plano(df, plano)
            with st.spinner("✍️ Interpretando o resultado..."):
                insight = explicar_resultado(client, modelo, pergunta, tabela)

            st.markdown("### " + insight.replace("$", "\\$"))
            if fig is not None:
                st.pyplot(fig)
            st.dataframe(tabela, use_container_width=True)
            with st.expander("🧠 Como o agente pensou (plano gerado)"):
                st.json(plano)

            st.session_state.hist.append((pergunta, insight))
        except json.JSONDecodeError:
            st.error("O agente não conseguiu montar um plano válido. Tente reformular a pergunta.")
        except Exception as e:
            st.error(f"Não consegui responder a essa pergunta. Detalhe: {e}")

# ----------------------- Rodapé -----------------------
st.markdown("---")
st.caption("Agente Analista de Dados · Python · Streamlit · Groq (LLM) · pandas")
