import streamlit as st
import pandas as pd
import datetime
import pytz
from supabase import create_client
import os
from dotenv import load_dotenv
from pathlib import Path
import plotly.graph_objects as go

# ==============================
# PAGE CONFIG
# ==============================
st.set_page_config(
    page_title="Dashboard Produção",
    layout="wide",
    initial_sidebar_state="collapsed"
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
# CSS DARK / TV
# ==============================
def aplicar_css_tv(hide_sidebar=False):
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-color: #0e1117;
            color: #fafafa;
        }}

        [data-testid="stAppViewContainer"] {{
            background-color: #0e1117;
        }}

        [data-testid="stMain"] {{
            background-color: #0e1117;
        }}

        .block-container {{
            padding-top: 0.6rem;
            padding-bottom: 1.2rem;
            padding-left: 1.2rem;
            padding-right: 1.2rem;
            max-width: 100%;
        }}

        header[data-testid="stHeader"] {{
            display: none;
        }}

        div[data-testid="stToolbar"] {{
            visibility: hidden;
            height: 0%;
            position: fixed;
        }}

        [data-testid="stSidebar"] {{
            background-color: #111827;
        }}

        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] > div,
        .stDateInput > div > div,
        .stSelectbox > div > div {{
            background-color: #1f2937 !important;
            color: #fafafa !important;
            border-color: #374151 !important;
        }}

        label, .stMarkdown, .stText, p, h1, h2, h3, h4, h5, h6, span {{
            color: #fafafa !important;
        }}

        .stAlert {{
            background-color: #111827 !important;
            color: #fafafa !important;
            border: 1px solid #374151 !important;
        }}

        {"section[data-testid='stSidebar']{display:none;}" if hide_sidebar else ""}
        </style>
        """,
        unsafe_allow_html=True
    )

# ==============================
# Captura altura de tela
# ==============================
def capturar_screen_height():
    if "screen_height" not in st.session_state:
        st.session_state.screen_height = 1070

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
# Helper Pareto
# ==============================
def aplicar_layout_pareto(fig: go.Figure):
    screen_height = st.session_state.get("screen_height", 1080)

    pareto_height = int(screen_height * 0.34)
    pareto_height = max(360, min(pareto_height, 520))

    fig.update_layout(
        height=pareto_height,
        autosize=True,
        margin=dict(l=20, r=20, t=30, b=200),
        yaxis=dict(showticklabels=False, showgrid=False),
        yaxis2=dict(
            overlaying="y",
            side="right",
            range=[0, 150],
            showticklabels=False,
            showgrid=False
        ),
        xaxis=dict(automargin=True),
        bargap=0.25,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="white")
    )

# ==============================
# Cálculo de aprovação
# ==============================
def calcular_aprovacao(df_checks_filtrado: pd.DataFrame):
    if df_checks_filtrado is None or df_checks_filtrado.empty:
        return 0.0, 0, 0

    if "numero_serie" not in df_checks_filtrado.columns:
        return 0.0, 0, 0

    df = df_checks_filtrado.copy()

    if "status" in df.columns:
        df["status_norm"] = df["status"].astype(str).str.strip().str.lower()
    else:
        df["status_norm"] = ""

    if "reinspecao" in df.columns:
        df["reinspecao_norm"] = df["reinspecao"].astype(str).str.strip().str.lower()
    else:
        df["reinspecao_norm"] = ""

    if "produto_reprovado" in df.columns:
        df["prod_rep_norm"] = df["produto_reprovado"].astype(str).str.strip().str.lower()
    else:
        df["prod_rep_norm"] = ""

    df["is_nc"] = df["status_norm"].isin(["não conforme", "nao conforme"])
    df["has_reinspecao"] = df["reinspecao_norm"].isin(["sim", "s", "yes", "y", "true", "1"])
    df["is_prod_reprovado"] = False

    if "produto_reprovado" in df_checks_filtrado.columns:
        df["is_prod_reprovado"] = (
            df["prod_rep_norm"].ne("não")
            & df["prod_rep_norm"].ne("nao")
            & df["prod_rep_norm"].ne("")
            & df["prod_rep_norm"].ne("nan")
        )

    aprovados = 0
    reprovados = 0

    for _, grp in df.groupby("numero_serie", dropna=True):
        teve_reinspecao = grp["has_reinspecao"].any()
        teve_nc = grp["is_nc"].any()
        teve_prod_reprovado = grp["is_prod_reprovado"].any()

        aprovado = not (teve_reinspecao or teve_nc or teve_prod_reprovado)

        if aprovado:
            aprovados += 1
        else:
            reprovados += 1

    total_inspecionado = aprovados + reprovados
    aprovacao_perc = (aprovados / total_inspecionado) * 100 if total_inspecionado > 0 else 0.0
    return aprovacao_perc, total_inspecionado, reprovados

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

    if not df.empty and "data_hora" in df.columns:
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
# Funções Supabase para Solda
# ==============================
def carregar_apontamentos_solda(force_reload=False):
    if not force_reload:
        @st.cache_data(ttl=60)
        def _carregar():
            return _load_apontamentos_solda()
        return _carregar()
    else:
        return _load_apontamentos_solda()

def _load_apontamentos_solda():
    data_total = []
    inicio = 0
    passo = 1000

    while True:
        response = supabase.table("apontamento.solda").select("*").range(inicio, inicio + passo - 1).execute()
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
# Grade horária da solda
# ==============================
def renderizar_grade_horaria_solda(df_solda: pd.DataFrame, meta_hora: dict):
    realizado = {h.strftime("%H:%M"): 0 for h in meta_hora.keys()}

    if not df_solda.empty and "data_hora" in df_solda.columns:
        df_aux = df_solda.dropna(subset=["data_hora"]).copy()
        df_aux["hora_ref"] = df_aux["data_hora"].dt.floor("h").dt.strftime("%H:%M")
        contagem = df_aux.groupby("hora_ref").size().to_dict()

        for h in realizado.keys():
            realizado[h] = int(contagem.get(h, 0))

    st.markdown("### 📊 Produção por Hora - Solda")

    cols_top = st.columns(len(meta_hora))
    for col, (hora_obj, meta) in zip(cols_top, meta_hora.items()):
        hora = hora_obj.strftime("%H:%M")
        with col:
            st.markdown(f"""
            <div style="
                background:#51b84d;
                border-radius:6px;
                padding:10px 6px;
                text-align:center;
                min-height:78px;
                display:flex;
                flex-direction:column;
                justify-content:center;
                box-shadow: inset 0 0 0 1px rgba(255,255,255,0.06);
            ">
                <div style="font-size:15px;font-weight:700;color:white;">{hora}</div>
                <div style="font-size:28px;font-weight:800;color:white;line-height:1.1;">{meta}</div>
            </div>
            """, unsafe_allow_html=True)

    cols_bottom = st.columns(len(meta_hora))
    for col, hora_obj in zip(cols_bottom, meta_hora.keys()):
        hora = hora_obj.strftime("%H:%M")
        valor = realizado[hora]
        with col:
            st.markdown(f"""
            <div style="
                background:#000000;
                border-radius:6px;
                padding:10px 6px;
                text-align:center;
                min-height:78px;
                display:flex;
                flex-direction:column;
                justify-content:center;
                border:1px solid #111827;
            ">
                <div style="font-size:15px;font-weight:700;color:white;">{hora}</div>
                <div style="font-size:28px;font-weight:800;color:white;line-height:1.1;">{valor}</div>
            </div>
            """, unsafe_allow_html=True)

# ==============================
# Painel Dashboard (Produção Geral)
# ==============================
def painel_dashboard():
    hoje = datetime.datetime.now(TZ).date()
    hora_atual = datetime.datetime.now(TZ)

    capturar_screen_height()

    st.sidebar.markdown("### Filtro de Data")
    data_inicio = st.sidebar.date_input("Data Início", hoje, key="geral_inicio")
    data_fim = st.sidebar.date_input("Data Fim", hoje, key="geral_fim")
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
        datetime.time(6, 0): 20, datetime.time(7, 0): 20, datetime.time(8, 0): 20,
        datetime.time(9, 0): 20, datetime.time(10, 0): 20, datetime.time(11, 0): 0,
        datetime.time(12, 0): 22, datetime.time(13, 0): 22, datetime.time(14, 0): 22,
        datetime.time(15, 0): 12
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

    if (
        not df_checks.empty
        and not df_apont.empty
        and "numero_serie" in df_checks.columns
        and "numero_serie" in df_apont.columns
    ):
        df_checks_filtrado = df_checks[
            df_checks["numero_serie"].isin(df_apont["numero_serie"].unique())
        ]
    else:
        df_checks_filtrado = pd.DataFrame()

    aprovacao_perc, total_inspecionado, total_reprovados = calcular_aprovacao(df_checks_filtrado)

    total_eixo = total_manga = total_pnm = 0
    if not df_apont.empty and "tipo_producao" in df_apont.columns:
        df_eixo = df_apont[df_apont["tipo_producao"].astype(str).str.contains("EIXO|ESTEIRA", case=False, na=False)]
        df_manga = df_apont[df_apont["tipo_producao"].astype(str).str.contains("MANGA", case=False, na=False)]
        df_pnm = df_apont[df_apont["tipo_producao"].astype(str).str.contains("PNM", case=False, na=False)]
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
        <p style="color:#E3E3E3;font-size:{fonte}">Inspecionado: {total_inspecionado} | Reprov: {total_reprovados}</p>
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
            number={'suffix': "%", 'font': {'size': 20, 'color': 'white'}},
            title={'text': "OEE", 'font': {'size': 14, 'color': 'white'}},
            gauge={
                'axis': {'range': [0, 100], 'tickcolor': 'white'},
                'bar': {'color': "#1E90FF"},
                'steps': [
                    {'range': [0, 60], 'color': "#FF4C4C"},
                    {'range': [60, 85], 'color': "#FFD700"},
                    {'range': [85, 100], 'color': "#4CAF50"}
                ],
                'threshold': {'line': {'color': "white", 'width': 4}, 'thickness': 0.75, 'value': 85}
            }
        ))
        fig_oee.update_layout(height=altura, margin={'l':10,'r':10,'t':30,'b':10}, paper_bgcolor='rgba(0,0,0,0)', font=dict(color="white"))
        fig_oee.add_annotation(
            x=0.5, y=-0.08, xref='paper', yref='paper',
            text=f"Perf: {performance_percent:.2f}% | Qualid: {aprovacao_perc:.2f}%",
            showarrow=False, font={'size': 12, 'color': '#E3E3E3'}
        )
        st.plotly_chart(fig_oee, use_container_width=True, config={"displayModeBar": False, "responsive": True})

    st.markdown("### 📊 Pareto das Não Conformidades")

    if not df_checks_filtrado.empty:
        df_nc = df_checks_filtrado[
            df_checks_filtrado["status"].astype(str).str.strip().str.lower().isin(["não conforme", "nao conforme"])
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
        datetime.time(17, 0): 14,
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

    if (
        not df_checks_mola.empty
        and not df_mola.empty
        and "numero_serie" in df_checks_mola.columns
        and "numero_serie" in df_mola.columns
    ):
        df_checks_filtrado = df_checks_mola[
            df_checks_mola["numero_serie"].isin(df_mola["numero_serie"].unique())
        ]
    else:
        df_checks_filtrado = pd.DataFrame()

    aprovacao_perc, total_inspecionado, total_reprovados = calcular_aprovacao(df_checks_filtrado)

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
        <p style="color:#E3E3E3;font-size:{fonte}">Inspecionado: {total_inspecionado} | Reprov: {total_reprovados}</p></div>
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
            number={'suffix': "%", 'font': {'size': 20, 'color': 'white'}},
            title={'text': "OEE", 'font': {'size': 14, 'color': 'white'}},
            gauge={
                'axis': {'range': [0, 100], 'tickcolor': 'white'},
                'bar': {'color': "#1E90FF"},
                'steps': [
                    {'range': [0, 60], 'color': "#FF4C4C"},
                    {'range': [60, 85], 'color': "#FFD700"},
                    {'range': [85, 100], 'color': "#4CAF50"}
                ],
                'threshold': {'line': {'color': "white", 'width': 4}, 'thickness': 0.75, 'value': 85}
            }
        ))
        fig_oee.update_layout(height=altura, margin={'l':10,'r':10,'t':30,'b':10}, paper_bgcolor='rgba(0,0,0,0)', font=dict(color="white"))
        fig_oee.add_annotation(
            x=0.5, y=-0.08, xref='paper', yref='paper',
            text=f"Perf: {performance_percent:.2f}% | Qualid: {aprovacao_perc:.2f}%",
            showarrow=False, font={'size': 12, 'color': '#E3E3E3'}
        )
        st.plotly_chart(fig_oee, use_container_width=True, config={"displayModeBar": False, "responsive": True})

    st.markdown("### 📊 Pareto das Não Conformidades – Mola")

    if not df_checks_filtrado.empty:
        df_nc = df_checks_filtrado[
            df_checks_filtrado["status"].astype(str).str.strip().str.lower().isin(["não conforme", "nao conforme"])
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
        datetime.time(15, 0): 2,
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

    if (
        not df_checks.empty
        and not df_apont.empty
        and "numero_serie" in df_checks.columns
        and "numero_serie" in df_apont.columns
    ):
        df_checks_filtrado = df_checks[
            df_checks["numero_serie"].isin(df_apont["numero_serie"].unique())
        ]
    else:
        df_checks_filtrado = pd.DataFrame()

    aprovacao_perc, total_inspecionado, total_reprovados = calcular_aprovacao(df_checks_filtrado)

    total_manga = 0
    total_pnm = 0
    if not df_apont.empty and "tipo_producao" in df_apont.columns:
        df_manga = df_apont[df_apont["tipo_producao"].astype(str).str.contains("MANGA", case=False, na=False)]
        df_pnm = df_apont[df_apont["tipo_producao"].astype(str).str.contains("PNM", case=False, na=False)]
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
        Inspecionado: {total_inspecionado} | Reprov: {total_reprovados}
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
            number={'suffix': "%", 'font': {'size': 20, 'color': 'white'}},
            title={'text': "OEE", 'font': {'size': 14, 'color': 'white'}},
            gauge={
                'axis': {'range': [0, 100], 'tickcolor': 'white'},
                'bar': {'color': "#1E90FF"},
                'steps': [
                    {'range': [0, 60], 'color': "#FF4C4C"},
                    {'range': [60, 85], 'color': "#FFD700"},
                    {'range': [85, 100], 'color': "#4CAF50"}
                ],
                'threshold': {'line': {'color': "white", 'width': 4}, 'value': 85}
            }
        ))
        fig_oee.update_layout(
            height=altura,
            margin={'l': 10, 'r': 10, 't': 30, 'b': 10},
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color="white")
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
            df_checks_filtrado["status"].astype(str).str.strip().str.lower().isin(["não conforme", "nao conforme"])
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
                textposition="auto",
                textfont=dict(color="white"),
                marker_color="lightskyblue"
            )
            fig.add_scatter(
                x=pareto["Item"],
                y=pareto["%"],
                yaxis="y2",
                mode="lines+markers+text",
                text=[f"{v:.1f}%" for v in pareto["%"]],
                textposition="top center",
                textfont=dict(color="white"),
                line=dict(color="white"),
                marker=dict(color="white")
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
# Painel Dashboard (Solda)
# ==============================
def painel_dashboard_solda():
    hoje = datetime.datetime.now(TZ).date()
    hora_atual = datetime.datetime.now(TZ)

    capturar_screen_height()

    st.sidebar.markdown("### Filtro de Data - Solda")
    data_inicio = st.sidebar.date_input("Data Início (Solda)", hoje, key="solda_inicio")
    data_fim = st.sidebar.date_input("Data Fim (Solda)", hoje, key="solda_fim")
    force_reload = False

    df_solda = carregar_apontamentos_solda(force_reload=force_reload)

    if not df_solda.empty:
        df_solda = df_solda[
            (df_solda["data_hora"].dt.date >= data_inicio) &
            (df_solda["data_hora"].dt.date <= data_fim)
        ].copy()

    meta_hora = {
        datetime.time(6, 0): 22,
        datetime.time(7, 0): 22,
        datetime.time(8, 0): 22,
        datetime.time(9, 0): 22,
        datetime.time(10, 0): 22,
        datetime.time(11, 0): 4,
        datetime.time(12, 0): 18,
        datetime.time(13, 0): 22,
        datetime.time(14, 0): 22,
        datetime.time(15, 0): 12,
    }

    total_lidos = len(df_solda)
    meta_dia = sum(meta_hora.values())
    meta_acumulada = 0

    for h, m in meta_hora.items():
        horario_fim = datetime.datetime.combine(hoje, h) + datetime.timedelta(hours=1)
        if horario_fim.tzinfo is None:
            horario_fim = TZ.localize(horario_fim)
        if hora_atual >= horario_fim:
            meta_acumulada += m

    atraso = max(meta_acumulada - total_lidos, 0)

    total_lotes = 0
    total_ops = 0

    if not df_solda.empty:
        if "lote" in df_solda.columns:
            total_lotes = df_solda["lote"].astype(str).replace("nan", pd.NA).dropna().nunique()
        if "op" in df_solda.columns:
            total_ops = df_solda["op"].astype(str).replace("nan", pd.NA).dropna().nunique()

    performance_fraction = (total_lidos / meta_acumulada) if meta_acumulada > 0 else 1
    performance_fraction = max(min(performance_fraction, 1), 0)
    performance_percent = performance_fraction * 100

    col1, col2, col3, col4 = st.columns(4)
    altura = 180
    fonte = "18px"

    with col1:
        st.markdown(f"""
        <div style="background-color:#2b6cb0;height:{altura}px;display:flex;flex-direction:column;justify-content:center;align-items:center;border-radius:20px;text-align:center;padding:10px;">
            <h3 style="color:white;font-size:{fonte}">TOTAL REGISTROS</h3>
            <h1 style="color:white;font-size:{fonte}">{total_lidos}</h1>
            <p style="color:#E3E3E3;font-size:{fonte}">
                Lotes: {total_lotes} | OPs: {total_ops}
            </p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div style="background-color:#38a169;height:{altura}px;display:flex;flex-direction:column;justify-content:center;align-items:center;border-radius:20px;text-align:center;padding:10px;">
            <h3 style="color:white;font-size:{fonte}">META DO DIA</h3>
            <h1 style="color:white;font-size:{fonte}">{meta_dia}</h1>
            <p style="color:#E3E3E3;font-size:{fonte}">
                Meta acumulada: {meta_acumulada}
            </p>
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
        fig_perf = go.Figure(go.Indicator(
            mode="gauge+number",
            value=performance_percent,
            number={'suffix': "%", 'font': {'size': 20, 'color': 'white'}},
            title={'text': "PERFORMANCE", 'font': {'size': 14, 'color': 'white'}},
            gauge={
                'axis': {'range': [0, 100], 'tickcolor': 'white'},
                'bar': {'color': "#1E90FF"},
                'steps': [
                    {'range': [0, 60], 'color': "#FF4C4C"},
                    {'range': [60, 85], 'color': "#FFD700"},
                    {'range': [85, 100], 'color': "#4CAF50"}
                ],
                'threshold': {'line': {'color': "white", 'width': 4}, 'thickness': 0.75, 'value': 85}
            }
        ))
        fig_perf.update_layout(
            height=altura,
            margin={'l': 10, 'r': 10, 't': 30, 'b': 10},
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color="white")
        )
        fig_perf.add_annotation(
            x=0.5, y=-0.08, xref='paper', yref='paper',
            text=f"Real: {total_lidos} | Meta acum.: {meta_acumulada}",
            showarrow=False, font={'size': 12, 'color': '#E3E3E3'}
        )
        st.plotly_chart(fig_perf, use_container_width=True, config={"displayModeBar": False, "responsive": True})

    renderizar_grade_horaria_solda(df_solda, meta_hora)

# ==============================
# Main
# ==============================
def main():
    aplicar_css_tv(hide_sidebar=False)

    if AUTORELOAD_AVAILABLE:
        st_autorefresh(interval=60000, key="dashboard_refresh")

    params = st.query_params

    if "painel" in params:
        painel_param = str(params["painel"]).lower()
    else:
        painel_param = "geral"

    painel_opcoes = ["Produção Geral", "Mola", "Manga/PNM", "Solda"]

    if painel_param == "mola":
        painel_default = "Mola"
    elif painel_param == "manga_pnm":
        painel_default = "Manga/PNM"
    elif painel_param == "solda":
        painel_default = "Solda"
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
    elif painel == "Solda":
        st.query_params["painel"] = "solda"
    else:
        st.query_params["painel"] = "geral"

    if painel == "Produção Geral":
        painel_dashboard()
    elif painel == "Mola":
        painel_dashboard_mola()
    elif painel == "Manga/PNM":
        painel_dashboard_manga_pnm()
    else:
        painel_dashboard_solda()

    hora = datetime.datetime.now(TZ).strftime("%H:%M:%S")
    st.markdown(
        f"<p style='color:#BDBDBD;text-align:center;'>Atualizado às <b>{hora}</b></p>",
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
