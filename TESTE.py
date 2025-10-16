import streamlit as st
import streamlit.components.v1 as components
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
@st.cache_data(ttl=60)
def carregar_checklists():
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

@st.cache_data(ttl=60)
def carregar_apontamentos():
    response = supabase.table("apontamentos").select("*").limit(1000).execute()
    df = pd.DataFrame(response.data)
    if not df.empty:
        df["data_hora"] = pd.to_datetime(df["data_hora"], utc=True, format="ISO8601").dt.tz_convert(TZ)
    return df

# ==============================
# Painel Dashboard
# ==============================
def painel_dashboard(modo_tv=False):
    hoje = datetime.datetime.now(TZ).date()

    if not modo_tv:
        st.sidebar.markdown("### Filtro de Data")
        data_inicio = st.sidebar.date_input("Data Início", hoje)
        data_fim = st.sidebar.date_input("Data Fim", hoje)
    else:
        data_inicio = data_fim = hoje

    df_apont = carregar_apontamentos()
    df_checks = carregar_checklists()

    if not df_apont.empty:
        df_apont = df_apont[(df_apont["data_hora"].dt.date >= data_inicio) & (df_apont["data_hora"].dt.date <= data_fim)]
    if not df_checks.empty:
        df_checks = df_checks[(df_checks["data_hora"].dt.date >= data_inicio) & (df_checks["data_hora"].dt.date <= data_fim)]

    # ======= Cálculo de Atraso =======
    meta_hora = {
        datetime.time(6,0):22, datetime.time(7,0):22, datetime.time(8,0):22,
        datetime.time(9,0):22, datetime.time(10,0):22, datetime.time(11,0):4,
        datetime.time(12,0):18, datetime.time(13,0):22, datetime.time(14,0):22, datetime.time(15,0):12
    }
    total_lidos = len(df_apont)
    meta_acumulada = 0
    hora_atual = datetime.datetime.now(TZ)
    for h, m in meta_hora.items():
        horario_fechado = TZ.localize(datetime.datetime.combine(hoje, h)) + datetime.timedelta(hours=1)
        if hora_atual >= horario_fechado:
            meta_acumulada += m
    atraso = max(meta_acumulada - total_lidos, 0)

    # ======= % Aprovação =======
    if not df_checks.empty and not df_apont.empty:
        df_checks_filtrado = df_checks[df_checks["numero_serie"].isin(df_apont["numero_serie"].unique())]
    else:
        df_checks_filtrado = pd.DataFrame()

    aprovacao_perc = total_inspecionado = total_reprovados = 0
    if not df_checks_filtrado.empty:
        series_with_checks = df_checks_filtrado["numero_serie"].unique()
        aprovados = 0
        total_reprovados = 0
        for serie in series_with_checks:
            checks = df_checks_filtrado[df_checks_filtrado["numero_serie"] == serie]
            teve_reinspecao = (checks["reinspecao"] == "Sim").any()
            aprovado = False if teve_reinspecao else (checks.tail(1).iloc[0]["produto_reprovado"] == "Não")
            if aprovado:
                aprovados += 1
            else:
                total_reprovados += 1
        total_inspecionado = len(series_with_checks)
        aprovacao_perc = (aprovados / total_inspecionado) * 100 if total_inspecionado > 0 else 0

    # ======= Esteira / Rodagem =======
    total_esteira = total_rodagem = 0
    if not df_apont.empty:
        df_esteira = df_apont[df_apont["tipo_producao"].str.contains("ESTEIRA", case=False, na=False)]
        df_rodagem = df_apont[df_apont["tipo_producao"].str.contains("RODAGEM", case=False, na=False)]
        total_esteira = len(df_esteira)
        total_rodagem = len(df_rodagem)

    # ======= Cartões Resumo =======
    col1, col2, col3 = st.columns(3)
    altura = "220px" if not modo_tv else "280px"
    fonte = "18px" if not modo_tv else "28px"

    with col1:
        st.markdown(f"""
        <div style="background-color:#2b6cb0;height:{altura};display:flex;flex-direction:column;justify-content:center;align-items:center;border-radius:20px;text-align:center;padding:10px;">
        <h3 style="color:white;font-size:{fonte}">TOTAL PRODUZIDO</h3><h1 style="color:white;font-size:{fonte}">{total_lidos}</h1>
        <p style="color:#E3E3E3;font-size:{fonte}">Esteira: {total_esteira} | Rodagem: {total_rodagem}</p></div>""", unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div style="background-color:#2f855a;height:{altura};display:flex;flex-direction:column;justify-content:center;align-items:center;border-radius:20px;text-align:center;padding:10px;">
        <h3 style="color:white;font-size:{fonte}">% APROVAÇÃO</h3><h1 style="color:white;font-size:{fonte}">{aprovacao_perc:.2f}%</h1>
        <p style="color:#E3E3E3;font-size:{fonte}">Inspecionado: {total_inspecionado}</p></div>""", unsafe_allow_html=True)
    with col3:
        cor = "#c53030" if atraso > 0 else "#38a169"
        texto = f"Atraso: {atraso}" if atraso > 0 else "Dentro da Meta"
        st.markdown(f"""
        <div style="background-color:{cor};height:{altura};display:flex;flex-direction:column;justify-content:center;align-items:center;border-radius:20px;text-align:center;padding:10px;">
        <h3 style="color:white;font-size:{fonte}">STATUS</h3><h1 style="color:white;font-size:{fonte}">{texto}</h1></div>""", unsafe_allow_html=True)

    # ======= Pareto NC =======
    if not modo_tv:
        st.markdown("### 📊 Pareto das Não Conformidades")
        df_nc = []
        if not df_checks_filtrado.empty:
            for _, row in df_checks_filtrado.iterrows():
                if row["status"] == "Não Conforme":
                    df_nc.append({"item": row["item"], "numero_serie": row["numero_serie"]})
        df_nc = pd.DataFrame(df_nc)
        if not df_nc.empty:
            pareto = df_nc.groupby("item")["numero_serie"].count().sort_values(ascending=False).reset_index()
            pareto.columns = ["Item", "Quantidade"]
            pareto["%"] = pareto["Quantidade"].cumsum() / pareto["Quantidade"].sum() * 100
            fig = go.Figure()
            fig.add_trace(go.Bar(x=pareto["Item"], y=pareto["Quantidade"], name="NC"))
            fig.add_trace(go.Scatter(x=pareto["Item"], y=pareto["%"], mode="lines+markers", name="% Acumulado", yaxis="y2"))
            fig.update_layout(yaxis2=dict(title="%", overlaying="y", side="right", range=[0, 110]))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Nenhuma não conformidade registrada.")

# ==============================
# Modo TV e Principal
# ==============================
def main():
    st.set_page_config(page_title="Dashboard Produção", layout="wide")

    # --- Detecção de modo TV via parâmetro de URL ---
    query_params = st.experimental_get_query_params()
    modo_tv = query_params.get("view", [""])[0].lower() == "tv"

    if modo_tv:
        st.markdown("""
        <style>
        #MainMenu, header, footer, .stSidebar {display: none;}
        html, body, [class*="block-container"] {padding: 0; margin: 0;}
        h1, h2, h3, p {color: white; text-align: center;}
        body {background-color: #0e1117;}
        </style>
        """, unsafe_allow_html=True)

        # Auto refresh a cada 1 minuto (60000 ms)
        if AUTORELOAD_AVAILABLE:
            st_autorefresh(interval=60000, key="tv_refresh")

        st.markdown("<h1>📺 Painel de Produção - Modo TV</h1>", unsafe_allow_html=True)
        painel_dashboard(modo_tv=True)

        hora = datetime.datetime.now(TZ).strftime("%H:%M:%S")
        st.markdown(f"<p style='color:#ccc;text-align:center;'>Atualizado às <b>{hora}</b></p>", unsafe_allow_html=True)

    else:
        st.title("📊 Dashboard de Produção")
        painel_dashboard()

if __name__ == "__main__":
    main()
