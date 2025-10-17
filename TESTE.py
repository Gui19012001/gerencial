import streamlit as st
import pandas as pd
import datetime
import pytz
import base64
from supabase import create_client
import os
from dotenv import load_dotenv
from pathlib import Path
import plotly.graph_objects as go

# ==============================
# Verificação do autorefresh
# ==============================
try:
    from streamlit_autorefresh import st_autorefresh
    AUTORELOAD_AVAILABLE = True
except ImportError:
    AUTORELOAD_AVAILABLE = False

# ==============================
# Carregar variáveis de ambiente
# ==============================
env_path = Path(__file__).parent / "teste.env"
load_dotenv(dotenv_path=env_path)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==============================
# Configurações iniciais
# ==============================
TZ = pytz.timezone("America/Sao_Paulo")

# ==============================
# Funções Supabase
# ==============================
def carregar_checklists(force_reload=False):
    if not force_reload:
        @st.cache_data(ttl=60)
        def _carregar():
            return _load_checklists()
        return _carregar()
    else:
        return _load_checklists()

def _load_checklists():
    data_total = []
    inicio = 0
    passo = 1000
    while True:
        response = supabase.table("checklists").select("*").range(inicio, inicio + passo - 1).execute()
        dados = response.data
        if not dados:
            break
        data_total.extend(dados)
        inicio += passo
    df = pd.DataFrame(data_total)
    if not df.empty and "data_hora" in df.columns:
        df["data_hora"] = pd.to_datetime(df["data_hora"], utc=True).dt.tz_convert(TZ)
    return df

def carregar_apontamentos(force_reload=False):
    if not force_reload:
        @st.cache_data(ttl=60)
        def _carregar():
            return _load_apontamentos()
        return _carregar()
    else:
        return _load_apontamentos()

def _load_apontamentos():
    response = supabase.table("apontamentos").select("*").limit(1000).execute()
    df = pd.DataFrame(response.data)
    if not df.empty:
        df["data_hora"] = pd.to_datetime(df["data_hora"], utc=True, format="ISO8601").dt.tz_convert(TZ)
    return df

# ==============================
# Painel Dashboard
# ==============================

def painel_dashboard():
    st.markdown("## 📊 Painel de Produção")

    # ================== CÁLCULOS ==================
    meta_total = sum(meta_hora.values())  # Exemplo: 188
    total_lidos = len(df_apont)  # Produzido
    aprovacao_perc = (df_apont['aprovado'].sum() / total_lidos * 100) if total_lidos > 0 else 0

    performance = (total_lidos / meta_total * 100) if meta_total > 0 else 0
    qualidade = aprovacao_perc
    disponibilidade = 100
    oee = (performance/100) * (qualidade/100) * (disponibilidade/100) * 100

    # ================== LAYOUT ==================
    col1, col2, col3, col4 = st.columns([1,1,1,2])  # OEE maior para o gauge
    altura = "220px"
    fonte = "18px"

    # ---------- CARD: Total Produzido ----------
    with col1:
        st.markdown(f"""
        <div style="background-color:#2B6CB0;height:{altura};
        display:flex;flex-direction:column;justify-content:center;align-items:center;
        border-radius:20px;text-align:center;padding:10px;">
        <h3 style="color:white;font-size:{fonte}">Total Produzido</h3>
        <h1 style="color:white;font-size:{fonte}">{total_lidos}</h1>
        </div>""", unsafe_allow_html=True)

    # ---------- CARD: % Aprovação ----------
    with col2:
        st.markdown(f"""
        <div style="background-color:#38A169;height:{altura};
        display:flex;flex-direction:column;justify-content:center;align-items:center;
        border-radius:20px;text-align:center;padding:10px;">
        <h3 style="color:white;font-size:{fonte}">% Aprovação</h3>
        <h1 style="color:white;font-size:{fonte}">{aprovacao_perc:.2f}%</h1>
        </div>""", unsafe_allow_html=True)

    # ---------- CARD: Status ----------
    with col3:
        atraso = meta_total - total_lidos
        status = "Dentro da meta" if atraso <= 0 else f"Atraso: {atraso}"
        cor = "#805AD5" if atraso <= 0 else "#E53E3E"
        st.markdown(f"""
        <div style="background-color:{cor};height:{altura};
        display:flex;flex-direction:column;justify-content:center;align-items:center;
        border-radius:20px;text-align:center;padding:10px;">
        <h3 style="color:white;font-size:{fonte}">Status</h3>
        <h1 style="color:white;font-size:{fonte}">{status}</h1>
        </div>""", unsafe_allow_html=True)

    # ---------- GAUGE: OEE ----------
    with col4:
        fig = go.Figure(go.Indicator(
            mode = "gauge+number+delta",
            value = oee,
            delta = {'reference': 85, "increasing": {"color":"green"}, "decreasing": {"color":"red"}},
            title = {'text': "OEE (%)"},
            gauge = {
                'axis': {'range': [0,100]},
                'bar': {'color': "blue"},
                'steps': [
                    {'range': [0, 60], 'color': "#FF4C4C"},   # vermelho
                    {'range': [60, 85], 'color': "#FFD700"},  # amarelo
                    {'range': [85, 100], 'color': "#4CAF50"}  # verde
                ],
                'threshold': {
                    'line': {'color': "black", 'width': 4},
                    'thickness': 0.75,
                    'value': 85  # meta
                }
            }
        ))
        st.plotly_chart(fig, use_container_width=True)


# ==============================
# Main
# ==============================
def main():
    st.set_page_config(page_title="Dashboard Produção", layout="wide")

    # Atualiza automaticamente a cada 1 minuto
    if AUTORELOAD_AVAILABLE:
        st_autorefresh(interval=10000, key="dashboard_refresh")

    st.title("📊 Dashboard de Produção")
    painel_dashboard()

    # Hora da última atualização
    hora = datetime.datetime.now(TZ).strftime("%H:%M:%S")
    st.markdown(f"<p style='color:#555;text-align:center;'>Atualizado às <b>{hora}</b></p>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
