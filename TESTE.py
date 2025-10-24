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
    hoje = datetime.datetime.now(TZ).date()

    # Filtro de data no sidebar
    st.sidebar.markdown("### Filtro de Data")
    data_inicio = st.sidebar.date_input("Data Início", hoje)
    data_fim = st.sidebar.date_input("Data Fim", hoje)
    force_reload = False

    df_apont = carregar_apontamentos(force_reload=force_reload)
    df_checks = carregar_checklists(force_reload=force_reload)

    if not df_apont.empty:
        df_apont = df_apont[(df_apont["data_hora"].dt.date >= data_inicio) & (df_apont["data_hora"].dt.date <= data_fim)]
    if not df_checks.empty:
        df_checks = df_checks[(df_checks["data_hora"].dt.date >= data_inicio) & (df_checks["data_hora"].dt.date <= data_fim)]

    # ======= Cálculo de Atraso (lógica atualizada) =======
    meta_hora = {
        datetime.time(6,0):22, datetime.time(7,0):22, datetime.time(8,0):22,
        datetime.time(9,0):22, datetime.time(10,0):22, datetime.time(11,0):4,
        datetime.time(12,0):18, datetime.time(13,0):22, datetime.time(14,0):22, datetime.time(15,0):12
    }

    total_lidos = len(df_apont)
    meta_acumulada = 0
    hora_atual = datetime.datetime.now(TZ)

    # Soma a meta de todas as horas que já começaram
    for h, m in meta_hora.items():
        horario_inicio = datetime.datetime.combine(hoje, h)
        # Garante que o datetime está no mesmo fuso horário
        if horario_inicio.tzinfo is None:
            horario_inicio = TZ.localize(horario_inicio)

        if hora_atual >= horario_inicio:
            meta_acumulada += m

    # Atraso: diferença entre meta acumulada e total produzido
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

    # ======= Cálculo do OEE (inicia em 100% e cai conforme atraso) =======
    meta_total = 188  # meta diária
    if meta_acumulada > 0:
        performance_fraction = max(1 - (atraso / meta_acumulada), 0)
    else:
        performance_fraction = 1  # início do turno (sem meta ainda)

    performance_percent = performance_fraction * 100
    quality_fraction = (aprovacao_perc / 100) if aprovacao_perc > 0 else 1
    oee_fraction = performance_fraction * quality_fraction
    oee_percent = oee_fraction * 100

    # ======= Cartões Resumo + Gauge =======
    col1, col2, col3, col4 = st.columns(4)
    altura = 220
    fonte = "18px"

    with col1:
        st.markdown(f"""
        <div style="background-color:#2b6cb0;height:{altura}px;display:flex;flex-direction:column;justify-content:center;align-items:center;border-radius:20px;text-align:center;padding:10px;">
        <h3 style="color:white;font-size:{fonte}">TOTAL PRODUZIDO</h3><h1 style="color:white;font-size:{fonte}">{total_lidos}</h1>
        <p style="color:#E3E3E3;font-size:{fonte}">Esteira: {total_esteira} | Rodagem: {total_rodagem}</p></div>""", unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div style="background-color:#2f855a;height:{altura}px;display:flex;flex-direction:column;justify-content:center;align-items:center;border-radius:20px;text-align:center;padding:10px;">
        <h3 style="color:white;font-size:{fonte}">% APROVAÇÃO</h3><h1 style="color:white;font-size:{fonte}">{aprovacao_perc:.2f}%</h1>
        <p style="color:#E3E3E3;font-size:{fonte}">Inspecionado: {total_inspecionado}</p></div>""", unsafe_allow_html=True)

    with col3:
        cor = "#c53030" if atraso > 0 else "#38a169"
        texto = f"Atraso: {atraso}" if atraso > 0 else "Dentro da Meta"
        st.markdown(f"""
        <div style="background-color:{cor};height:{altura}px;display:flex;flex-direction:column;justify-content:center;align-items:center;border-radius:20px;text-align:center;padding:10px;">
        <h3 style="color:white;font-size:{fonte}">STATUS</h3><h1 style="color:white;font-size:{fonte}">{texto}</h1></div>""", unsafe_allow_html=True)

    with col4:
        fig_oee = go.Figure(go.Indicator(
            mode="gauge+number",
            value=oee_percent,
            number={'suffix': "%", 'font': {'size': 20}},
            title={'text': "OEE", 'font': {'size': 14}},
            gauge={
                'axis': {'range': [0, 100]},
                'bar': {'color': "#1E90FF"},
                'steps': [
                    {'range': [0, 60], 'color': "#FF4C4C"},
                    {'range': [60, 85], 'color': "#FFD700"},
                    {'range': [85, 100], 'color': "#4CAF50"}
                ],
                'threshold': {
                    'line': {'color': "black", 'width': 4},
                    'thickness': 0.75,
                    'value': 85
                }
            }
        ))
        fig_oee.update_layout(height=altura, margin={'l':10, 'r':10, 't':30, 'b':10}, paper_bgcolor='rgba(0,0,0,0)')
        fig_oee.add_annotation(
            x=0.5, y=-0.08, xref='paper', yref='paper',
            text=f"Perf: {performance_percent:.2f}% | Qualid: {aprovacao_perc:.2f}%",
            showarrow=False, font={'size': 12, 'color': '#E3E3E3'}
        )
        st.plotly_chart(fig_oee, use_container_width=True)

        # ======= Pareto NC =======
    st.markdown("### 📊 Pareto das Não Conformidades")
    df_nc = []
    if not df_checks_filtrado.empty:
        for _, row in df_checks_filtrado.iterrows():
            if row["status"] == "Não Conforme":
                df_nc.append({"item": row["item"], "numero_serie": row["numero_serie"]})
    df_nc = pd.DataFrame(df_nc)

    if not df_nc.empty:
        pareto = (
            df_nc.groupby("item")["numero_serie"]
            .count()
            .sort_values(ascending=False)
            .reset_index()
        )
        pareto.columns = ["Item", "Quantidade"]
        pareto["%"] = pareto["Quantidade"].cumsum() / pareto["Quantidade"].sum() * 100

        fig = go.Figure()

        # Barras com os números visíveis
        fig.add_trace(
            go.Bar(
                x=pareto["Item"],
                y=pareto["Quantidade"],
                name="NC",
                text=pareto["Quantidade"],
                textposition="outside",  # Mostra o número acima da barra
                marker_color="lightskyblue"
            )
        )

        # Linha de % acumulado
        fig.add_trace(
            go.Scatter(
                x=pareto["Item"],
                y=pareto["%"],
                mode="lines+markers+text",
                name="% Acumulado",
                yaxis="y2",
                text=[f"{v:.1f}%" for v in pareto["%"]],
                textposition="top center",
                textfont=dict(size=10, color="#E3E3E3")
            )
        )

        fig.update_layout(
            yaxis2=dict(title="%", overlaying="y", side="right", range=[0, 110]),
            yaxis=dict(title="Quantidade"),
            bargap=0.3,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            legend=dict(x=0.85, y=1.1),
            margin=dict(l=40, r=40, t=40, b=40),
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Nenhuma não conformidade registrada.")


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
