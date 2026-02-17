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
# ✅ PAGE CONFIG (TEM QUE SER A PRIMEIRA CHAMADA STREAMLIT)
# ==============================
st.set_page_config(
    page_title="Dashboard Produção",
    layout="wide",
    initial_sidebar_state="collapsed"  # melhor pra TV
)

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

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL / SUPABASE_KEY não encontrados no teste.env")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==============================
# Configurações iniciais
# ==============================
TZ = pytz.timezone("America/Sao_Paulo")

# ==============================
# ✅ CSS MODO TV (TIRA PADDING E EVITA CORTE)
# ==============================
def aplicar_css_tv(hide_sidebar=True):
    st.markdown(
        f"""
        <style>
        /* reduz padding padrão (TV costuma cortar embaixo) */
        .block-container {{
            padding-top: 0.6rem;
            padding-bottom: 1.2rem;
            padding-left: 1.2rem;
            padding-right: 1.2rem;
            max-width: 100%;
        }}

        /* remove header e toolbar */
        header[data-testid="stHeader"] {{
            display: none;
        }}
        div[data-testid="stToolbar"] {{
            visibility: hidden;
            height: 0%;
            position: fixed;
        }}

        /* opcional: some com sidebar pra virar painel */
        {"section[data-testid='stSidebar']{display:none;}" if hide_sidebar else ""}
        </style>
        """,
        unsafe_allow_html=True
    )

# ==============================
# ✅ Captura altura de tela (pra dimensionar pareto)
# ==============================
def capturar_screen_height():
    if "screen_height" not in st.session_state:
        st.session_state.screen_height = 980  # padrão

    st.markdown(
        """
        <script>
        const height = window.screen.height;
        window.parent.postMessage(
          {isStreamlitMessage: true, type: "streamlit:setComponentValue", key: "screen_height", value: height},
          "*"
        );
        </script>
        """,
        unsafe_allow_html=True
    )

# ==============================
# ✅ Helper Pareto (layout seguro pra TV)
# ==============================
def aplicar_layout_pareto(fig: go.Figure):
    screen_height = st.session_state.get("screen_height", 1080)

    # altura proporcional + limites
    pareto_height = int(screen_height * 0.34)
    pareto_height = max(360, min(pareto_height, 520))

    fig.update_layout(
        height=pareto_height,
        autosize=True,
        margin=dict(l=20, r=30, t=30, b=300),  # ✅ b maior evita corte na TV
        yaxis=dict(showticklabels=False, showgrid=False),
        yaxis2=dict(
            overlaying="y",
            side="right",
            range=[0, 150],
            showticklabels=False,
            showgrid=False
        ),
        xaxis=dict(automargin=True),          # ✅ evita cortar eixo/labels
        bargap=0.25,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

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
    data_total = []
    inicio = 0
    passo = 1000

    while True:
        response = supabase.table("apontamentos").select("*").range(inicio, inicio + passo - 1).execute()
        dados = response.data
        if not dados:
            break
        data_total.extend(dados)
        inicio += passo

    df = pd.DataFrame(data_total)

    if not df.empty:
        df["data_hora"] = pd.to_datetime(df["data_hora"], errors="coerce", utc=True).dt.tz_convert(TZ)

    return df

# ==============================
# Funções Supabase para apontamento_mola
# ==============================
def carregar_apontamentos_mola(force_reload=False):
    if not force_reload:
        @st.cache_data(ttl=60)
        def _carregar():
            return _load_apontamentos_mola()
        return _carregar()
    else:
        return _load_apontamentos_mola()

def _load_apontamentos_mola():
    data_total = []
    inicio = 0
    passo = 1000

    while True:
        response = supabase.table("apontamentos_mola").select("*").range(inicio, inicio + passo - 1).execute()
        dados = response.data
        if not dados:
            break
        data_total.extend(dados)
        inicio += passo

    df = pd.DataFrame(data_total)

    if not df.empty and "data_hora" in df.columns:
        df["data_hora"] = pd.to_datetime(df["data_hora"], errors="coerce", utc=True).dt.tz_convert(TZ)

    return df

# ==============================
# Funções Supabase para checklist de mola
# ==============================
def carregar_checklists_mola(force_reload=False):
    if not force_reload:
        @st.cache_data(ttl=60)
        def _carregar():
            return _load_checklists_mola()
        return _carregar()
    else:
        return _load_checklists_mola()

def _load_checklists_mola():
    data_total = []
    inicio = 0
    passo = 1000

    while True:
        response = supabase.table("checklists_mola_detalhes").select("*").range(inicio, inicio + passo - 1).execute()
        dados = response.data
        if not dados:
            break
        data_total.extend(dados)
        inicio += passo

    df = pd.DataFrame(data_total)

    if not df.empty and "data_hora" in df.columns:
        df["data_hora"] = pd.to_datetime(df["data_hora"], errors="coerce", utc=True).dt.tz_convert(TZ)

    return df

# ==============================
# Funções Supabase para apontamentos Manga/PNM
# ==============================
def carregar_apontamentos_manga_pnm(force_reload=False):
    if not force_reload:
        @st.cache_data(ttl=60)
        def _carregar():
            return _load_apontamentos_manga_pnm()
        return _carregar()
    else:
        return _load_apontamentos_manga_pnm()

def _load_apontamentos_manga_pnm():
    data_total = []
    inicio = 0
    passo = 1000

    while True:
        response = supabase.table("apontamentos_manga_pnm").select("*").range(inicio, inicio + passo - 1).execute()
        dados = response.data
        if not dados:
            break
        data_total.extend(dados)
        inicio += passo

    df = pd.DataFrame(data_total)

    if not df.empty and "data_hora" in df.columns:
        df["data_hora"] = pd.to_datetime(df["data_hora"], errors="coerce", utc=True).dt.tz_convert(TZ)

    return df

# ==============================
# Funções Supabase para checklists Manga/PNM
# ==============================
def carregar_checklists_manga_pnm(force_reload=False):
    if not force_reload:
        @st.cache_data(ttl=60)
        def _carregar():
            return _load_checklists_manga_pnm()
        return _carregar()
    else:
        return _load_checklists_manga_pnm()

def _load_checklists_manga_pnm():
    data_total = []
    inicio = 0
    passo = 1000

    while True:
        response = supabase.table("checklists_manga_pnm_detalhes").select("*").range(inicio, inicio + passo - 1).execute()
        dados = response.data
        if not dados:
            break
        data_total.extend(dados)
        inicio += passo

    df = pd.DataFrame(data_total)

    if not df.empty and "data_hora" in df.columns:
        df["data_hora"] = pd.to_datetime(df["data_hora"], errors="coerce", utc=True).dt.tz_convert(TZ)

    return df

# ==============================
# Painel Dashboard (Produção Geral)
# ==============================
def painel_dashboard():
    hoje = datetime.datetime.now(TZ).date()
    hora_atual = datetime.datetime.now(TZ)

    capturar_screen_height()

    st.sidebar.markdown("### Filtro de Data")
    data_inicio = st.sidebar.date_input("Data Início", hoje)
    data_fim = st.sidebar.date_input("Data Fim", hoje)
    force_reload = False

    df_apont = carregar_apontamentos(force_reload=force_reload)
    df_checks = carregar_checklists(force_reload=force_reload)

    if not df_apont.empty:
        df_apont = df_apont[
            (df_apont["data_hora"].dt.date >= data_inicio) &
            (df_apont["data_hora"].dt.date <= data_fim)
        ]

    if not df_checks.empty:
        df_checks = df_checks[
            (df_checks["data_hora"].dt.date >= data_inicio) &
            (df_checks["data_hora"].dt.date <= data_fim)
        ]

    meta_hora = {
        datetime.time(6,0):30, datetime.time(7,0):30, datetime.time(8,0):30,
        datetime.time(9,0):30, datetime.time(10,0):30, datetime.time(11,0):6,
        datetime.time(12,0):30, datetime.time(13,0):30, datetime.time(14,0):30,
        datetime.time(15,0):12
    }

    total_lidos = len(df_apont)
    meta_acumulada = 0

    for h, m in meta_hora.items():
        horario_fim = datetime.datetime.combine(hoje, h) + datetime.timedelta(hours=1)
        if horario_fim.tzinfo is None:
            horario_fim = TZ.localize(horario_fim)
        if hora_atual >= horario_fim:
            meta_acumulada += m

    atraso = max(meta_acumulada - total_lidos, 0)

    if not df_checks.empty and not df_apont.empty:
        df_checks_filtrado = df_checks[
            df_checks["numero_serie"].isin(df_apont["numero_serie"].unique())
        ]
    else:
        df_checks_filtrado = pd.DataFrame()

    aprovacao_perc = total_inspecionado = total_reprovados = 0

    if not df_checks_filtrado.empty:
        series_with_checks = df_checks_filtrado["numero_serie"].unique()
        aprovados = 0
        total_reprovados = 0

        for serie in series_with_checks:
            checks = df_checks_filtrado[df_checks_filtrado["numero_serie"] == serie]
            teve_reinspecao = (
                (checks.get("reinspecao") == "Sim").any()
                if "reinspecao" in checks.columns else False
            )

            if "produto_reprovado" in checks.columns:
                ultimo_produto_reprovado = checks.tail(1).iloc[0].get("produto_reprovado", "Não")
                aprovado = False if teve_reinspecao else (
                    str(ultimo_produto_reprovado).strip().lower() == "não"
                )
            else:
                ultimo_status = checks.tail(1).iloc[0].get("status", "")
                aprovado = False if teve_reinspecao else (
                    str(ultimo_status).strip().str.lower() != "não conforme"
                )

            if aprovado:
                aprovados += 1
            else:
                total_reprovados += 1

        total_inspecionado = len(series_with_checks)
        aprovacao_perc = (aprovados / total_inspecionado) * 100 if total_inspecionado > 0 else 0

    # ✅ Totais no rodapé do card (Eixo / Manga / PNM)
    total_eixo = total_manga = total_pnm = 0
    if not df_apont.empty and "tipo_producao" in df_apont.columns:
        df_eixo = df_apont[df_apont["tipo_producao"].str.contains("EIXO|ESTEIRA", case=False, na=False)]
        df_manga = df_apont[df_apont["tipo_producao"].str.contains("MANGA", case=False, na=False)]
        df_pnm = df_apont[df_apont["tipo_producao"].str.contains("PNM", case=False, na=False)]
        total_eixo = len(df_eixo)
        total_manga = len(df_manga)
        total_pnm = len(df_pnm)

    performance_fraction = max(1 - (atraso / meta_acumulada), 0) if meta_acumulada > 0 else 1
    performance_percent = performance_fraction * 100
    quality_fraction = (aprovacao_perc / 100) if aprovacao_perc > 0 else 1
    oee_percent = performance_fraction * quality_fraction * 100

    col1, col2, col3, col4 = st.columns(4)
    altura = 180
    fonte = "18px"

    with col1:
        st.markdown(f"""
        <div style="background-color:#2b6cb0;height:{altura}px;display:flex;flex-direction:column;justify-content:center;align-items:center;border-radius:20px;text-align:center;padding:10px;">
        <h3 style="color:white;font-size:{fonte}">TOTAL PRODUZIDO</h3>
        <h1 style="color:white;font-size:{fonte}">{total_lidos}</h1>
        <p style="color:#E3E3E3;font-size:{fonte}">
        Eixo: {total_eixo} | Manga: {total_manga} | PNM: {total_pnm}
        </p></div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div style="background-color:#2f855a;height:{altura}px;display:flex;flex-direction:column;justify-content:center;align-items:center;border-radius:20px;text-align:center;padding:10px;">
        <h3 style="color:white;font-size:{fonte}">% APROVAÇÃO</h3>
        <h1 style="color:white;font-size:{fonte}">{aprovacao_perc:.2f}%</h1>
        <p style="color:#E3E3E3;font-size:{fonte}">Inspecionado: {total_inspecionado}</p>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        cor = "#c53030" if atraso > 0 else "#38a169"
        texto = f"Atraso: {atraso}" if atraso > 0 else "Dentro da Meta"
        st.markdown(f"""
        <div style="background-color:{cor};height:{altura}px;display:flex;flex-direction:column;justify-content:center;align-items:center;border-radius:20px;text-align:center;padding:10px;">
        <h3 style="color:white;font-size:{fonte}">STATUS</h3>
        <h1 style="color:white;font-size:{fonte}">{texto}</h1>
        </div>
        """, unsafe_allow_html=True)

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
                'threshold': {'line': {'color': "black", 'width': 4}, 'thickness': 0.75, 'value': 85}
            }
        ))
        fig_oee.update_layout(height=altura, margin={'l':10,'r':10,'t':30,'b':10}, paper_bgcolor='rgba(0,0,0,0)')
        fig_oee.add_annotation(
            x=0.5, y=-0.08, xref='paper', yref='paper',
            text=f"Perf: {performance_percent:.2f}% | Qualid: {aprovacao_perc:.2f}%",
            showarrow=False, font={'size': 12, 'color': '#E3E3E3'}
        )
        st.plotly_chart(fig_oee, use_container_width=True, config={"displayModeBar": False, "responsive": True})

    st.markdown("### 📊 Pareto das Não Conformidades")

    if not df_checks_filtrado.empty:
        df_nc = df_checks_filtrado[
            df_checks_filtrado["status"].str.strip().str.lower() == "não conforme"
        ][["item", "numero_serie"]].dropna()

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
            fig.add_trace(go.Bar(
                x=pareto["Item"],
                y=pareto["Quantidade"],
                text=pareto["Quantidade"],
                textposition="auto",
                textfont=dict(size=14, color="white", family="Arial Black"),
                marker_color="lightskyblue"
            ))
            fig.add_trace(go.Scatter(
                x=pareto["Item"],
                y=pareto["%"],
                mode="lines+markers+text",
                yaxis="y2",
                text=[f"{v:.1f}%" for v in pareto["%"]],
                textposition="top center",
                textfont=dict(size=13, color="white", family="Arial Black"),
                line=dict(width=3, color="white"),
                marker=dict(size=8, color="white")
            ))

            aplicar_layout_pareto(fig)

            st.plotly_chart(
                fig,
                use_container_width=True,
                config={"displayModeBar": False, "responsive": True}
            )
        else:
            st.info("Nenhuma não conformidade registrada.")
    else:
        st.warning("⚠️ Nenhum checklist disponível para gerar o Pareto.")

# ==============================
# Painel Dashboard (Mola)
# ==============================
def painel_dashboard_mola():
    hoje = datetime.datetime.now(TZ).date()
    hora_atual = datetime.datetime.now(TZ)

    capturar_screen_height()

    st.sidebar.markdown("### Filtro de Data - Mola")
    data_inicio = st.sidebar.date_input("Data Início (Mola)", hoje, key="mola_inicio")
    data_fim = st.sidebar.date_input("Data Fim (Mola)", hoje, key="mola_fim")
    force_reload = False

    df_mola = carregar_apontamentos_mola(force_reload=force_reload)
    df_checks_mola = carregar_checklists_mola(force_reload=force_reload)

    if not df_mola.empty:
        df_mola = df_mola[
            (df_mola["data_hora"].dt.date >= data_inicio) &
            (df_mola["data_hora"].dt.date <= data_fim)
        ]

    if not df_checks_mola.empty:
        df_checks_mola = df_checks_mola[
            (df_checks_mola["data_hora"].dt.date >= data_inicio) &
            (df_checks_mola["data_hora"].dt.date <= data_fim)
        ]

    meta_hora = {
        datetime.time(6, 0): 14,
        datetime.time(7, 0): 14,
        datetime.time(8, 0): 14,
        datetime.time(9, 0): 14,
        datetime.time(10, 0): 14,
        datetime.time(11, 0): 14,
        datetime.time(12, 0): 0,
        datetime.time(13, 0): 14,
        datetime.time(14, 0): 14,
        datetime.time(15, 0): 8,
        datetime.time(16, 0): 14,
        datetime.time(17, 0): 1,
    }

    total_lidos = len(df_mola)
    meta_acumulada = 0

    hora_atual_fechada = hora_atual.replace(minute=0, second=0, microsecond=0)

    for h, m in meta_hora.items():
        horario_inicio = datetime.datetime.combine(hoje, h)
        if horario_inicio.tzinfo is None:
            horario_inicio = TZ.localize(horario_inicio)
        if horario_inicio < hora_atual_fechada:
            meta_acumulada += m

    atraso = max(meta_acumulada - total_lidos, 0)

    aprovacao_perc = 0.0
    total_inspecionado = 0
    total_reprovados = 0

    if not df_checks_mola.empty and not df_mola.empty:
        df_checks_filtrado = df_checks_mola[
            df_checks_mola["numero_serie"].isin(df_mola["numero_serie"].unique())
        ]
    else:
        df_checks_filtrado = pd.DataFrame()

    if not df_checks_filtrado.empty:
        series_unicas = df_checks_filtrado["numero_serie"].unique()
        aprovados = 0
        total_reprovados = 0

        for serie in series_unicas:
            checks = df_checks_filtrado[df_checks_filtrado["numero_serie"] == serie]
            teve_reinspecao = (checks.get("reinspecao") == "Sim").any() if "reinspecao" in checks.columns else False

            if "produto_reprovado" in checks.columns:
                ultimo_produto_reprovado = checks.tail(1).iloc[0].get("produto_reprovado", "Não")
                aprovado = False if teve_reinspecao else (str(ultimo_produto_reprovado).strip().lower() == "não")
            else:
                ultimo_status = checks.tail(1).iloc[0].get("status", "")
                aprovado = False if teve_reinspecao else (str(ultimo_status).strip().lower() != "não conforme")

            if aprovado:
                aprovados += 1
            else:
                total_reprovados += 1

        total_inspecionado = len(series_unicas)
        aprovacao_perc = (aprovados / total_inspecionado) * 100 if total_inspecionado > 0 else 0.0

    if meta_acumulada > 0:
        performance_fraction = total_lidos / meta_acumulada
        performance_fraction = max(min(performance_fraction, 1), 0)
    else:
        performance_fraction = 0

    performance_percent = performance_fraction * 100
    quality_fraction = (aprovacao_perc / 100) if aprovacao_perc > 0 else 1
    oee_percent = performance_fraction * quality_fraction * 100

    col1, col2, col3, col4 = st.columns(4)
    altura = 180
    fonte = "18px"

    with col1:
        st.markdown(f"""
        <div style="background-color:#2b6cb0;height:{altura}px;display:flex;flex-direction:column;
        justify-content:center;align-items:center;border-radius:20px;text-align:center;padding:10px;">
        <h3 style="color:white;font-size:{fonte}">TOTAL PRODUZIDO</h3>
        <h1 style="color:white;font-size:{fonte}">{total_lidos}</h1></div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div style="background-color:#2f855a;height:{altura}px;display:flex;flex-direction:column;
        justify-content:center;align-items:center;border-radius:20px;text-align:center;padding:10px;">
        <h3 style="color:white;font-size:{fonte}">% APROVAÇÃO</h3>
        <h1 style="color:white;font-size:{fonte}">{aprovacao_perc:.2f}%</h1>
        <p style="color:#E3E3E3;font-size:{fonte}">Inspecionado: {total_inspecionado}</p></div>
        """, unsafe_allow_html=True)

    with col3:
        cor = "#c53030" if atraso > 0 else "#38a169"
        texto = f"Atraso: {atraso}" if atraso > 0 else "Dentro da Meta"
        st.markdown(f"""
        <div style="background-color:{cor};height:{altura}px;display:flex;flex-direction:column;
        justify-content:center;align-items:center;border-radius:20px;text-align:center;padding:10px;">
        <h3 style="color:white;font-size:{fonte}">STATUS</h3>
        <h1 style="color:white;font-size:{fonte}">{texto}</h1></div>
        """, unsafe_allow_html=True)

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
                'threshold': {'line': {'color': "black", 'width': 4}, 'thickness': 0.75, 'value': 85}
            }
        ))
        fig_oee.update_layout(height=altura, margin={'l':10,'r':10,'t':30,'b':10}, paper_bgcolor='rgba(0,0,0,0)')
        fig_oee.add_annotation(
            x=0.5, y=-0.08, xref='paper', yref='paper',
            text=f"Perf: {performance_percent:.2f}% | Qualid: {aprovacao_perc:.2f}%",
            showarrow=False, font={'size': 12, 'color': '#E3E3E3'}
        )
        st.plotly_chart(fig_oee, use_container_width=True, config={"displayModeBar": False, "responsive": True})

    st.markdown("### 📊 Pareto das Não Conformidades – Mola")

    if not df_checks_filtrado.empty:
        df_nc = df_checks_filtrado[
            df_checks_filtrado["status"].str.strip().str.lower() == "não conforme"
        ][["item", "numero_serie"]].dropna()

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
            fig.add_trace(go.Bar(
                x=pareto["Item"],
                y=pareto["Quantidade"],
                text=pareto["Quantidade"],
                textposition="auto",
                textfont=dict(size=14, color="white", family="Arial Black"),
                marker_color="lightskyblue"
            ))
            fig.add_trace(go.Scatter(
                x=pareto["Item"],
                y=pareto["%"],
                mode="lines+markers+text",
                text=[f"{v:.1f}%" for v in pareto["%"]],
                textposition="top center",
                textfont=dict(size=13, color="white", family="Arial Black"),
                yaxis="y2",
                line=dict(width=3, color="white"),
                marker=dict(size=8, color="white")
            ))

            aplicar_layout_pareto(fig)

            st.plotly_chart(
                fig,
                use_container_width=True,
                config={"displayModeBar": False, "responsive": True}
            )
        else:
            st.info("Nenhuma não conformidade registrada na Mola.")
    else:
        st.warning("Nenhum checklist disponível para gerar Pareto da Mola.")

# ==============================
# Painel Dashboard (Manga / PNM)
# ==============================
def painel_dashboard_manga_pnm():
    hoje = datetime.datetime.now(TZ).date()
    hora_atual = datetime.datetime.now(TZ)

    capturar_screen_height()

    st.sidebar.markdown("### Filtro de Data - Manga/PNM")
    data_inicio = st.sidebar.date_input("Data Início (Manga/PNM)", hoje, key="manga_inicio")
    data_fim = st.sidebar.date_input("Data Fim (Manga/PNM)", hoje, key="manga_fim")
    force_reload = False

    df_apont = carregar_apontamentos_manga_pnm(force_reload=force_reload)
    df_checks = carregar_checklists_manga_pnm(force_reload=force_reload)

    if not df_apont.empty:
        df_apont = df_apont[
            (df_apont["data_hora"].dt.date >= data_inicio) &
            (df_apont["data_hora"].dt.date <= data_fim)
        ]

    if not df_checks.empty:
        df_checks = df_checks[
            (df_checks["data_hora"].dt.date >= data_inicio) &
            (df_checks["data_hora"].dt.date <= data_fim)
        ]

    meta_hora = {
        datetime.time(6, 0): 4,
        datetime.time(7, 0): 4,
        datetime.time(8, 0): 4,
        datetime.time(9, 0): 4,
        datetime.time(10, 0): 4,
        datetime.time(11, 0): 0,
        datetime.time(12, 0): 4,
        datetime.time(13, 0): 4,
        datetime.time(14, 0): 4,
        datetime.time(15, 0): 4,
    }

    total_lidos = len(df_apont)
    meta_acumulada = 0

    for h, m in meta_hora.items():
        horario_inicio = datetime.datetime.combine(hoje, h)
        if horario_inicio.tzinfo is None:
            horario_inicio = TZ.localize(horario_inicio)
        horario_fim = horario_inicio + datetime.timedelta(hours=1)
        if hora_atual >= horario_fim:
            meta_acumulada += m

    atraso = max(meta_acumulada - total_lidos, 0)

    if not df_checks.empty and not df_apont.empty:
        df_checks_filtrado = df_checks[
            df_checks["numero_serie"].isin(df_apont["numero_serie"].unique())
        ]
    else:
        df_checks_filtrado = pd.DataFrame()

    aprovacao_perc = total_inspecionado = total_reprovados = 0

    if not df_checks_filtrado.empty:
        series_with_checks = df_checks_filtrado["numero_serie"].unique()
        aprovados = 0
        total_reprovados = 0

        for serie in series_with_checks:
            checks = df_checks_filtrado[df_checks_filtrado["numero_serie"] == serie]
            teve_reinspecao = (
                (checks.get("reinspecao") == "Sim").any()
                if "reinspecao" in checks.columns else False
            )

            if "produto_reprovado" in checks.columns:
                ultimo_produto_reprovado = checks.tail(1).iloc[0].get("produto_reprovado", "Não")
                aprovado = False if teve_reinspecao else (
                    str(ultimo_produto_reprovado).strip().lower() == "não"
                )
            else:
                ultimo_status = checks.tail(1).iloc[0].get("status", "")
                aprovado = False if teve_reinspecao else (
                    str(ultimo_status).strip().lower() != "não conforme"
                )

            if aprovado:
                aprovados += 1
            else:
                total_reprovados += 1

        total_inspecionado = len(series_with_checks)
        aprovacao_perc = (aprovados / total_inspecionado) * 100 if total_inspecionado > 0 else 0

    # ✅ Totais separados (MANGA e PNM) para o rodapé do card
    total_manga = 0
    total_pnm = 0
    if not df_apont.empty and "tipo_producao" in df_apont.columns:
        df_manga = df_apont[df_apont["tipo_producao"].str.contains("MANGA", case=False, na=False)]
        df_pnm = df_apont[df_apont["tipo_producao"].str.contains("PNM", case=False, na=False)]
        total_manga = len(df_manga)
        total_pnm = len(df_pnm)

    performance_fraction = max(1 - (atraso / meta_acumulada), 0) if meta_acumulada > 0 else 1
    performance_percent = performance_fraction * 100
    quality_fraction = (aprovacao_perc / 100) if aprovacao_perc > 0 else 1
    oee_percent = performance_fraction * quality_fraction * 100

    col1, col2, col3, col4 = st.columns(4)
    altura = 180
    fonte = "18px"

    with col1:
        st.markdown(f"""
        <div style="background-color:#2b6cb0;height:{altura}px;display:flex;flex-direction:column;
        justify-content:center;align-items:center;border-radius:20px;text-align:center;padding:10px;">
        <h3 style="color:white;font-size:{fonte}">TOTAL PRODUZIDO</h3>
        <h1 style="color:white;font-size:{fonte}">{total_lidos}</h1>
        <p style="color:#E3E3E3;font-size:{fonte}">
        MANGA: {total_manga} | PNM: {total_pnm}
        </p></div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div style="background-color:#2f855a;height:{altura}px;display:flex;flex-direction:column;
        justify-content:center;align-items:center;border-radius:20px;text-align:center;padding:10px;">
        <h3 style="color:white;font-size:{fonte}">% APROVAÇÃO</h3>
        <h1 style="color:white;font-size:{fonte}">{aprovacao_perc:.2f}%</h1>
        <p style="color:#E3E3E3;font-size:{fonte}">
        Inspecionado: {total_inspecionado}
        </p></div>
        """, unsafe_allow_html=True)

    with col3:
        cor = "#c53030" if atraso > 0 else "#38a169"
        texto = f"Atraso: {atraso}" if atraso > 0 else "Dentro da Meta"
        st.markdown(f"""
        <div style="background-color:{cor};height:{altura}px;display:flex;flex-direction:column;
        justify-content:center;align-items:center;border-radius:20px;text-align:center;padding:10px;">
        <h3 style="color:white;font-size:{fonte}">STATUS</h3>
        <h1 style="color:white;font-size:{fonte}">{texto}</h1>
        </div>
        """, unsafe_allow_html=True)

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
                'threshold': {'line': {'color': "black", 'width': 4}, 'value': 85}
            }
        ))
        fig_oee.update_layout(
            height=altura,
            margin={'l': 10, 'r': 10, 't': 30, 'b': 10},
            paper_bgcolor='rgba(0,0,0,0)'
        )
        fig_oee.add_annotation(
            x=0.5, y=-0.08, xref='paper', yref='paper',
            text=f"Perf: {performance_percent:.2f}% | Qualid: {aprovacao_perc:.2f}%",
            showarrow=False, font={'size': 12, 'color': '#E3E3E3'}
        )
        st.plotly_chart(
            fig_oee,
            use_container_width=True,
            config={"displayModeBar": False, "responsive": True}
        )

    st.markdown("### 📊 Pareto das Não Conformidades - Manga/PNM")

    if not df_checks_filtrado.empty:
        df_nc = df_checks_filtrado[
            df_checks_filtrado["status"].str.strip().str.lower() == "não conforme"
        ][["item", "numero_serie"]].dropna()

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
            fig.add_bar(
                x=pareto["Item"],
                y=pareto["Quantidade"],
                text=pareto["Quantidade"],
                textposition="auto"
            )
            fig.add_scatter(
                x=pareto["Item"],
                y=pareto["%"],
                yaxis="y2",
                mode="lines+markers+text",
                text=[f"{v:.1f}%" for v in pareto["%"]],
                textposition="top center"
            )

            aplicar_layout_pareto(fig)

            st.plotly_chart(
                fig,
                use_container_width=True,
                config={"displayModeBar": False, "responsive": True}
            )
        else:
            st.info("Nenhuma não conformidade registrada no Manga/PNM.")
    else:
        st.warning("⚠️ Nenhum checklist disponível para gerar o Pareto Manga/PNM.")

# ==============================
# Main
# ==============================
def main():
    # ✅ aplica CSS pra TV
    aplicar_css_tv(hide_sidebar=True)

    # 🔹 Atualiza automaticamente a cada 1 minuto (60.000 ms)
    if AUTORELOAD_AVAILABLE:
        st_autorefresh(interval=60000, key="dashboard_refresh")

    params = st.query_params

    if "painel" in params:
        painel_param = params["painel"].lower()
    else:
        painel_param = "geral"

    painel_opcoes = ["Produção Geral", "Mola", "Manga/PNM"]

    if painel_param == "mola":
        painel_default = "Mola"
    elif painel_param == "manga_pnm":
        painel_default = "Manga/PNM"
    else:
        painel_default = "Produção Geral"

    painel = st.sidebar.selectbox(
        "Escolha o Painel",
        painel_opcoes,
        key="select_painel_dashboard",
        index=painel_opcoes.index(painel_default)
    )

    if painel == "Mola":
        st.query_params["painel"] = "mola"
    elif painel == "Manga/PNM":
        st.query_params["painel"] = "manga_pnm"
    else:
        st.query_params["painel"] = "geral"

    if painel == "Produção Geral":
        painel_dashboard()
    elif painel == "Mola":
        painel_dashboard_mola()
    else:
        painel_dashboard_manga_pnm()

    hora = datetime.datetime.now(TZ).strftime("%H:%M:%S")
    st.markdown(
        f"<p style='color:#555;text-align:center;'>Atualizado às <b>{hora}</b></p>",
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()


