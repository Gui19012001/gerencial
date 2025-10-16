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
import plotly.express as px
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
usuarios = {"admin": "admin","Maria": "maria","Catia": "catia", "Vera": "vera", "Bruno":"bruno"}

# ==============================
# Funções Supabase
# ==============================
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

def salvar_checklist(serie, resultados, usuario, foto_etiqueta=None, reinspecao=False):
    existe = supabase.table("checklists").select("numero_serie").eq("numero_serie", serie).execute()
    if not reinspecao and existe.data:
        st.error("⚠️ INVÁLIDO! DUPLICIDADE – Este Nº de Série já foi inspecionado.")
        return None
    reprovado = any(info['status'] == "Não Conforme" for info in resultados.values())
    data_hora_utc = datetime.datetime.now(TZ).astimezone(pytz.UTC).isoformat()
    foto_base64 = None
    if foto_etiqueta is not None:
        try:
            foto_bytes = foto_etiqueta.getvalue()
            foto_base64 = base64.b64encode(foto_bytes).decode()
        except Exception as e:
            st.error(f"Erro ao processar a foto: {e}")
            foto_base64 = None
    for item, info in resultados.items():
        payload = {
            "numero_serie": serie,
            "item": item,
            "status": info.get('status', ''),
            "observacoes": info.get('obs', ''),
            "inspetor": usuario,
            "data_hora": data_hora_utc,
            "produto_reprovado": "Sim" if reprovado else "Não",
            "reinspecao": "Sim" if reinspecao else "Não"
        }
        if item == "Etiqueta" and foto_base64:
            payload["foto_etiqueta"] = foto_base64
        try:
            supabase.table("checklists").insert(payload).execute()
        except Exception as e:
            st.error(f"Erro ao salvar no banco: {e}")
            raise
    st.success(f"✅ Checklist salvo com sucesso para o Nº de Série {serie}")
    return True

def carregar_apontamentos():
    response = supabase.table("apontamentos").select("*").limit(1000).execute()
    df = pd.DataFrame(response.data)
    if not df.empty:
        df["data_hora"] = pd.to_datetime(df["data_hora"], utc=True, format="ISO8601").dt.tz_convert(TZ)
    return df

def salvar_apontamento(serie, tipo_producao=None):
    agora_utc = datetime.datetime.now(datetime.timezone.utc)
    hoje_utc = agora_utc.date()
    inicio_utc = datetime.datetime.combine(hoje_utc, datetime.time.min).replace(tzinfo=datetime.timezone.utc)
    fim_utc = datetime.datetime.combine(hoje_utc, datetime.time.max).replace(tzinfo=datetime.timezone.utc)
    response = supabase.table("apontamentos")\
        .select("*")\
        .eq("numero_serie", serie)\
        .gte("data_hora", inicio_utc.isoformat())\
        .lte("data_hora", fim_utc.isoformat())\
        .execute()
    if response.data:
        return False
    dados = {"numero_serie": serie, "data_hora": agora_utc.isoformat()}
    if tipo_producao:
        dados["tipo_producao"] = tipo_producao
    res = supabase.table("apontamentos").insert(dados).execute()
    return True if res.data and not getattr(res, "error", None) else False

# ==============================
# Funções utilitárias
# ==============================
def status_emoji_para_texto(emoji):
    return "Conforme" if emoji=="✅" else "Não Conforme" if emoji=="❌" else "N/A"

# ==============================
# Dashboard Produção Gerencial
# ==============================
def painel_dashboard():
    import streamlit as st
    import pandas as pd
    import datetime
    import plotly.graph_objects as go
    from pytz import timezone
    from streamlit_autorefresh import st_autorefresh

    TZ = timezone("America/Sao_Paulo")
    AUTORELOAD_AVAILABLE = True  # ajustar conforme necessário

    if AUTORELOAD_AVAILABLE:
        st_autorefresh(interval=60 * 1000, key="dashboard_refresh")

    # Filtro de Data
    st.sidebar.markdown("### Filtro de Data")
    hoje = datetime.datetime.now(TZ).date()
    data_inicio = st.sidebar.date_input("Data Início", hoje)
    data_fim = st.sidebar.date_input("Data Fim", hoje)

    # Carrega dados
    df_apont = carregar_apontamentos()
    df_checks = carregar_checklists()

    # Filtra pelo intervalo de datas
    if not df_apont.empty:
        df_apont = df_apont[(df_apont["data_hora"].dt.date >= data_inicio) & (df_apont["data_hora"].dt.date <= data_fim)]
    if not df_checks.empty:
        df_checks = df_checks[(df_checks["data_hora"].dt.date >= data_inicio) & (df_checks["data_hora"].dt.date <= data_fim)]

    # =======================
    # Cálculo de Atraso
    # =======================
    meta_hora = {
        datetime.time(6,0):22, datetime.time(7,0):22, datetime.time(8,0):22, datetime.time(9,0):22, datetime.time(10,0):22,
        datetime.time(11,0):4, datetime.time(12,0):18, datetime.time(13,0):22, datetime.time(14,0):22, datetime.time(15,0):12
    }
    total_lidos = len(df_apont)
    meta_acumulada = 0
    hora_atual = datetime.datetime.now(TZ)
    for h, m in meta_hora.items():
        horario_fechado = TZ.localize(datetime.datetime.combine(hoje, h)) + datetime.timedelta(hours=1)
        if hora_atual >= horario_fechado:
            meta_acumulada += m
    atraso = max(meta_acumulada - total_lidos,0)

    # =======================
    # % Aprovação
    # =======================
    if not df_checks.empty and not df_apont.empty:
        df_checks_filtrado = df_checks[df_checks["numero_serie"].isin(df_apont["numero_serie"].unique())]
    else:
        df_checks_filtrado = pd.DataFrame()

    if not df_checks_filtrado.empty:
        series_with_checks = df_checks_filtrado["numero_serie"].unique()
        aprovados = 0
        total_reprovados = 0
        for serie in series_with_checks:
            checks_all_for_serie = df_checks_filtrado[df_checks_filtrado["numero_serie"]==serie].sort_values("data_hora")
            if checks_all_for_serie.empty: continue
            teve_reinspecao = (checks_all_for_serie["reinspecao"]=="Sim").any()
            approved = False if teve_reinspecao else (checks_all_for_serie.tail(1).iloc[0]["produto_reprovado"]=="Não")
            if approved: 
                aprovados += 1
            else: 
                total_reprovados += 1
        total_inspecionado = len(series_with_checks)
        aprovacao_perc = (aprovados/total_inspecionado)*100 if total_inspecionado>0 else 0.0
    else:
        aprovacao_perc = total_inspecionado = total_reprovados = 0

    # =======================
    # Esteira / Rodagem
    # =======================
    if not df_apont.empty:
        df_esteira = df_apont[df_apont["tipo_producao"].str.contains("ESTEIRA",case=False,na=False)]
        df_rodagem = df_apont[df_apont["tipo_producao"].str.contains("RODAGEM",case=False,na=False)]
        total_esteira = len(df_esteira)
        total_rodagem = len(df_rodagem)
    else:
        total_esteira = total_rodagem = 0

    # =======================
    # Cartões resumo
    # =======================
    col1,col2,col3 = st.columns(3)
    altura_cartao = "220px"
    with col1:
        st.markdown(f"""
        <div style="background-color:#DDE3FF;height:{altura_cartao};display:flex;flex-direction:column;justify-content:center;align-items:center;border-radius:15px;text-align:center;padding:10px;">
        <h3>TOTAL PRODUZIDO</h3><h1>{total_lidos}</h1><p>Esteira: {total_esteira}</p><p>Rodagem: {total_rodagem}</p></div>""",unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div style="background-color:#E5F5E5;height:{altura_cartao};display:flex;flex-direction:column;justify-content:center;align-items:center;border-radius:15px;text-align:center;padding:10px;">
        <h3>% APROVAÇÃO</h3><h1>{aprovacao_perc:.2f}%</h1><p>Total inspecionado: {total_inspecionado}</p><p>Total reprovado: {total_reprovados}</p></div>""",unsafe_allow_html=True)
    with col3:
        cor = "#FFCCCC" if atraso>0 else "#DFF2DD"
        texto = f"Atraso: {atraso}" if atraso>0 else "Dentro da Meta"
        st.markdown(f"""
        <div style="background-color:{cor};height:{altura_cartao};display:flex;flex-direction:column;justify-content:center;align-items:center;border-radius:15px;text-align:center;padding:10px;">
        <h3>ATRASO</h3><h1>{texto}</h1></div>""",unsafe_allow_html=True)

    # =======================
    # Produção hora a hora
    # =======================
    st.markdown("### ⏱️ Produção Hora a Hora")
    col_meta = st.columns(len(meta_hora))
    col_prod = st.columns(len(meta_hora))
    for i,(h,m) in enumerate(meta_hora.items()):
        produzido = len(df_apont[df_apont["data_hora"].dt.hour==h.hour]) if not df_apont.empty else 0
        col_meta[i].markdown(f"<div style='background-color:#4CAF50;color:white;padding:10px;border-radius:5px;text-align:center'><b>{h.strftime('%H:%M')}<br>{m}</b></div>",unsafe_allow_html=True)
        col_prod[i].markdown(f"<div style='background-color:#000000;color:white;padding:10px;border-radius:5px;text-align:center'><b>{h.strftime('%H:%M')}<br>{produzido}</b></div>",unsafe_allow_html=True)

    # =======================
    # Pareto das Não Conformidades
    # =======================
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
        fig.add_trace(go.Bar(
            x=pareto["Item"],
            y=pareto["Quantidade"],
            text=pareto["Quantidade"],
            textposition='auto',
            name="Quantidade NC"
        ))
        fig.add_trace(go.Scatter(
            x=pareto["Item"],
            y=pareto["%"],
            mode="lines+markers",
            name="% Acumulado",
            yaxis="y2"
        ))

        fig.update_layout(
            title="Pareto das Não Conformidades",
            yaxis2=dict(title="%", overlaying="y", side="right", range=[0, 110]),
            legend=dict(x=0.8, y=1.1)
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Nenhuma não conformidade registrada.")


# =========================================
# Ponto de entrada da aplicação
# =========================================
def main():
    st.set_page_config(page_title="Dashboard Produção", layout="wide")
    st.title("📊 Dashboard de Produção")
    
    # Chama o painel principal
    painel_dashboard()

if __name__ == "__main__":
    main()
