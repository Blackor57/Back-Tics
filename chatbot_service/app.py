# chatbot_service/app.py
"""
🕷️ Universal Web Intelligence - Microservicio de Chatbot Auditor & Voz
Microservicio 5 de la arquitectura SIMAP.
Consume el Core API (Microservicio 1), Google Gemini API y Ollama (Microservicio 3).
"""

import os
import sys
import json
import base64
import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

import streamlit as st
from openai import OpenAI

# =====================================================================
# CONFIGURACIÓN DE VARIABLES DE ENTORNO (MICROSERVICIOS)
# =====================================================================
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000").rstrip("/")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
DEFAULT_GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

# =====================================================================
# CONFIGURACIÓN DE PÁGINA Y ESTILOS
# =====================================================================
st.set_page_config(
    page_title="SIMAP - Chatbot Auditor de Inteligencia Web",
    page_icon="🕷️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    /* Ocultar barra lateral y botón de expansión por completo */
    [data-testid="stSidebar"],
    [data-testid="collapsedControl"],
    section[data-testid="stSidebar"] {
        display: none !important;
    }
    .stApp > header {
        display: none !important;
    }
    .block-container {
        padding-top: 0.8rem !important;
        padding-bottom: 2rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        max-width: 100% !important;
    }
    .main-header {
        font-size: 1.3rem;
        font-weight: 700;
        background: linear-gradient(90deg, #4f46e5, #06b6d4);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.1rem;
    }
    .sub-header {
        font-size: 0.78rem;
        color: #94a3b8;
        margin-bottom: 0.5rem;
    }
    .context-card {
        background-color: rgba(30, 41, 59, 0.75);
        border: 1px solid rgba(148, 163, 184, 0.2);
        border-radius: 10px;
        padding: 8px 12px;
        margin-bottom: 10px;
    }
    .badge-tag {
        display: inline-block;
        background: #1e293b;
        color: #38bdf8;
        border: 1px solid #38bdf8;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.72rem;
        font-weight: 600;
        margin-right: 5px;
        margin-top: 2px;
    }
    .badge-warning {
        background: #451a03;
        color: #fb923c;
        border: 1px solid #f97316;
    }
    .badge-success {
        background: #064e3b;
        color: #34d399;
        border: 1px solid #059669;
    }
    .badge-neutral {
        background: #334155;
        color: #cbd5e1;
        border: 1px solid #475569;
    }
</style>
""", unsafe_allow_html=True)

# =====================================================================
# COMUNICACIÓN CON CORE API (REST HTTPX)
# =====================================================================
def consultar_contexto_activo_backend(api_url: str, sid: str) -> Optional[Dict[str, Any]]:
    """Consulta el scraping activo para la sesión actual (Modo Invitado / En Vivo)."""
    if not sid:
        return None
    try:
        url = f"{api_url}/api/v1/chat/active-context/{sid}"
        resp = httpx.get(url, timeout=3.5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("active"):
                return data.get("context")
    except Exception:
        pass
    return None

def consultar_historial_usuario_backend(api_url: str, token: str, sid: str) -> Optional[Dict[str, Any]]:
    """Consulta los reportes históricos del usuario autenticado y su contexto activo."""
    if not token:
        return None
    try:
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{api_url}/api/v1/chat/user-history"
        if sid:
            url += f"?session_id={sid}"
        resp = httpx.get(url, headers=headers, timeout=5.0)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None

def transcribir_audio_con_gemini(audio_bytes: bytes, mime_type: str, api_key: str) -> Optional[str]:
    """Transcribe audio usando la API multimodal de Google Gemini sin requerir OpenAI ni Whisper."""
    try:
        b64_audio = base64.b64encode(audio_bytes).decode("utf-8")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key={api_key}"
        payload = {
            "contents": [{
                "parts": [
                    {"text": "Transcribe exactamente las palabras dichas en este audio al español. Responde única y exclusivamente con el texto transcrito, sin explicaciones ni comillas."},
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": b64_audio
                        }
                    }
                ]
            }]
        }
        res = httpx.post(url, json=payload, timeout=30.0)
        if res.status_code == 200:
            data = res.json()
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                for p in parts:
                    if "text" in p:
                        return p["text"].strip()
        else:
            st.error(f"Error de Gemini al transcribir ({res.status_code}): {res.text}")
    except Exception as e:
        st.error(f"Error al procesar audio con Gemini: {str(e)}")
    return None

# =====================================================================
# LECTURA DE PARÁMETROS DE CONSULTA (URL QUERY PARAMS)
# =====================================================================
url_model = st.query_params.get("model", "")
url_provider = st.query_params.get("provider", "")
url_reset = st.query_params.get("reset", "")
url_auth = st.query_params.get("auth", "0")
auth_token = st.query_params.get("token", "")
session_id = st.query_params.get("sid", "")
url_user = st.query_params.get("user", "")

is_authenticated = (url_auth == "1" or url_auth.lower() == "true")

# Selección de motor LLM: Gemini u Ollama
es_ollama = (url_provider == "ollama") or (url_model and any(url_model.startswith(p) for p in ["llama", "qwen", "nomic"]))

if es_ollama:
    proveedor = "Ollama Local"
    modelo_seleccionado = url_model or "llama3.1:latest"
    client = OpenAI(
        base_url=f"{OLLAMA_BASE_URL}/v1",
        api_key="ollama"
    )
else:
    proveedor = "Google Gemini"
    modelo_seleccionado = url_model or DEFAULT_GEMINI_MODEL
    if DEFAULT_GEMINI_KEY:
        client = OpenAI(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=DEFAULT_GEMINI_KEY
        )
    else:
        # Fallback a Ollama si no se configuró clave de Gemini
        proveedor = "Ollama Local"
        modelo_seleccionado = "llama3.1:latest"
        client = OpenAI(
            base_url=f"{OLLAMA_BASE_URL}/v1",
            api_key="ollama"
        )

# =====================================================================
# RESOLUCIÓN DE CONTEXTO SEGÚN ESTADO DE AUTENTICACIÓN
# =====================================================================
usuario_info = None
historial_reportes: List[Dict[str, Any]] = []
active_scrape: Optional[Dict[str, Any]] = None

if is_authenticated and auth_token:
    hist_data = consultar_historial_usuario_backend(BACKEND_API_URL, auth_token, session_id)
    if hist_data and hist_data.get("authenticated"):
        usuario_info = hist_data.get("user", {})
        historial_reportes = hist_data.get("reports", [])
        active_scrape = hist_data.get("active_context")
    else:
        # Si el token falló o expiró, degradar a modo no autenticado
        is_authenticated = False

if not is_authenticated:
    # Modo no autenticado (Invitado): SOLO puede acceder al scraping activo en esta sesión
    if session_id:
        active_scrape = consultar_contexto_activo_backend(BACKEND_API_URL, session_id)

# Control de reinicio de estado cuando cambia el contexto o usuario solicita limpiar
context_key = (
    is_authenticated,
    auth_token[:15] if auth_token else "",
    session_id,
    active_scrape.get("url") if active_scrape else None,
    len(historial_reportes),
    url_reset
)

if "last_context_key" not in st.session_state or st.session_state.last_context_key != context_key:
    st.session_state.last_context_key = context_key
    st.session_state.messages = []

# =====================================================================
# SISTEMA DE PROMPT ENGINEERING DIFERENCIADO
# =====================================================================
def construir_prompt_modo_invitado(active_scrape: Dict[str, Any]) -> str:
    """Prompt estricto para modo anónimo: solo puede responder sobre la extracción actual."""
    datos_items = active_scrape.get("items", [])
    if isinstance(datos_items, (list, dict)):
        items_str = json.dumps(datos_items, ensure_ascii=False, indent=2)
    else:
        items_str = str(datos_items)
    
    analisis_ia = active_scrape.get("analisis_ia", {})
    delta = active_scrape.get("delta", {})

    return f"""Eres un **Auditor Senior de Inteligencia Web y Analista Estratégico de Datos Scrapeados** de la plataforma SIMAP.
Tu labor es examinar la información extraída de la web y emitir una opinión analítica, crítica y fundamentada.

### REGLA ESTRICTA DE PRIVACIDAD Y ALCANCE (MODO INVITADO):
- El usuario NO ha iniciado sesión.
- Tu conocimiento y análisis están **ESTRICTAMENTE LIMITADOS** a los datos de la extracción en vivo que se presenta a continuación.
- NO tienes acceso a análisis previos ni a ningún historial. Si el usuario te pregunta por otros sitios no incluidos aquí o por análisis anteriores, indícale amablemente que en modo invitado solo puedes auditar la extracción actual ({active_scrape.get('url')}) y que debe iniciar sesión para ver o comparar análisis anteriores.

### DATOS DE LA EXTRACCIÓN EN VIVO:
- **URL Objetivo:** {active_scrape.get("url")}
- **Título del Portal:** {active_scrape.get("site_title")}
- **Fecha de Captura:** {active_scrape.get("created_at")}
- **Total de Elementos:** {active_scrape.get("total_items")}
- **Resumen Preliminar:** {analisis_ia.get("resumen_ejecutivo", "N/A")}
- **Categorías Detectadas:** {json.dumps(analisis_ia.get("categorias", {}), ensure_ascii=False)}
- **Sentimientos:** {json.dumps(analisis_ia.get("sentimientos", {}), ensure_ascii=False)}
- **Cambios Temporales (Delta):** {json.dumps(delta, ensure_ascii=False) if delta else "Línea base (sin cambios detectados)"}

### CONTENIDO EXTRAÍDO EN VIVO:
{items_str}
### FIN DE CONTENIDO EXTRAÍDO ###

METODOLOGÍA DE RESPUESTA:
1. Responde siempre en español.
2. Analiza el tono, sentimientos, alertas y riesgos basándote exclusivamente en estos datos.
3. Sé profesional, estructurado con viñetas y emite conclusiones estratégicas de valor añadido."""


def construir_prompt_modo_autenticado(usuario: Dict[str, Any], reportes: List[Dict[str, Any]], active_scrape: Optional[Dict[str, Any]]) -> str:
    """Prompt enriquecido para usuario autenticado: acceso a todo su historial y extracción activa."""
    user_name = usuario.get("nombre", "Usuario")
    
    historial_text = ""
    if reportes:
        for idx, r in enumerate(reportes, 1):
            articulos_txt = ""
            if r.get("muestra_articulos"):
                articulos_txt = "\n      Muestra de títulos: " + ", ".join([f'"{a.get("titulo")}"' for a in r["muestra_articulos"][:5]])
            
            historial_text += f"""
--- REPORTE #{idx} (ID: {r.get('id')}) ---
- **URL:** {r.get('url')}
- **Portal/Título:** {r.get('site_title')}
- **Fecha de Análisis:** {r.get('created_at')}
- **Total Registros:** {r.get('total_items')}
- **Resumen Ejecutivo:** {r.get('resumen_ejecutivo')}
- **Métricas:** {json.dumps(r.get('metricas', {}), ensure_ascii=False)}
- **Delta/Cambios:** {json.dumps(r.get('diferencias_delta', {}), ensure_ascii=False)}{articulos_txt}
"""
    else:
        historial_text = "El usuario aún no tiene análisis previos almacenados en su cuenta."

    active_text = ""
    if active_scrape:
        items_preview = json.dumps(active_scrape.get("items", [])[:10] if isinstance(active_scrape.get("items"), list) else str(active_scrape.get("items", "")), ensure_ascii=False)
        active_text = f"""
### ANÁLISIS EN VIVO ACTUAL (SESIÓN ACTIVA) ###
- **URL:** {active_scrape.get('url')}
- **Título:** {active_scrape.get('site_title')}
- **Fecha:** {active_scrape.get('created_at')}
- **Total Registros:** {active_scrape.get('total_items')}
- **Resumen IA:** {active_scrape.get('analisis_ia', {}).get('resumen_ejecutivo', 'N/A')}
- **Contenido:** {items_preview}
################################################
"""

    return f"""Eres el **Copiloto de Inteligencia Web SIMAP** personal de {user_name}.
El usuario se encuentra **AUTENTICADO** y tiene acceso completo a su base histórica de análisis y a su sesión en vivo.

### CAPACIDADES DEL COPILOTO AUTENTICADO:
1. **Consultas Históricas:** Puedes responder sobre CUALQUIERA de los análisis que el usuario realizó previamente. Si te pregunta "¿Qué encontramos en RPP?", "¿Cuáles fueron los riesgos de El Comercio?", "¿Qué resumen hubo de tal fecha?", busca en el historial de reportes abajo y responde con precisión.
2. **Comparación Temporal:** Puedes comparar dos o más análisis del historial (por ejemplo, cambios entre fechas, evolución de sentimiento, nuevas noticias o riesgos que surgieron).
3. **Auditoría en Vivo:** Si hay un análisis en vivo activo, puedes responder sobre él y compararlo con sus versiones anteriores en el historial.

{active_text}
### BASE HISTÓRICA DE ANÁLISIS PREVIOS DEL USUARIO ({len(reportes)} reportes disponibles):
{historial_text}
### FIN DEL HISTORIAL ###

Responde siempre en español, con postura de auditor experto y respaldando tus respuestas con los datos de sus reportes."""

# =====================================================================
# ENCABEZADO Y TARJETA DE CONTEXTO VISUAL
# =====================================================================
st.markdown('<div class="main-header">🕷️ SIMAP Copiloto</div>', unsafe_allow_html=True)

if is_authenticated:
    nombre_user = usuario_info.get("nombre") if usuario_info else (url_user or "Usuario")
    st.markdown(
        f'<div class="sub-header">Usuario: <b>{nombre_user}</b> · Historial completo habilitado · Motor: <b>{modelo_seleccionado}</b></div>',
        unsafe_allow_html=True
    )
    # Tarjeta de contexto autenticado
    live_badge = f'<span class="badge-tag">🌐 En Vivo: {active_scrape.get("site_title", "")[:20]}</span>' if active_scrape else ''
    card_html = (
        f'<div class="context-card" style="border-left: 3px solid #10b981;">'
        f'<span class="badge-tag badge-success">👤 {nombre_user}</span>'
        f'<span class="badge-tag">📚 {len(historial_reportes)} análisis guardados</span>'
        f'{live_badge}'
        f'<span class="badge-tag badge-success">🤖 {modelo_seleccionado}</span>'
        f'</div>'
    )
    st.markdown(card_html, unsafe_allow_html=True)

else:
    # Modo no autenticado (Invitado)
    st.markdown(
        f'<div class="sub-header">Modo Invitado: Solo datos en vivo · Motor: <b>{modelo_seleccionado}</b></div>',
        unsafe_allow_html=True
    )
    if active_scrape:
        title_disp = active_scrape.get("site_title", "Página Web")[:28]
        items_cnt = active_scrape.get("total_items", 0)
        card_html = (
            f'<div class="context-card" style="border-left: 3px solid #06b6d4;">'
            f'<span class="badge-tag badge-warning">🔒 Modo Invitado (En Vivo)</span>'
            f'<span class="badge-tag">🌐 {title_disp}</span>'
            f'<span class="badge-tag">📊 {items_cnt} registros</span>'
            f'<span class="badge-tag badge-success">🤖 {modelo_seleccionado}</span>'
            f'</div>'
        )
        st.markdown(card_html, unsafe_allow_html=True)
    else:
        card_html = (
            f'<div class="context-card" style="border-left: 3px solid #f59e0b;">'
            f'<span class="badge-tag badge-warning">🔒 Modo Invitado</span>'
            f'<span class="badge-tag badge-neutral">⚠️ Sin análisis activo</span>'
            f'<span class="badge-tag badge-success">🤖 {modelo_seleccionado}</span>'
            f'</div>'
        )
        st.markdown(card_html, unsafe_allow_html=True)


# =====================================================================
# INICIALIZACIÓN DE MENSAJES (GREETING)
# =====================================================================
if "messages" not in st.session_state or len(st.session_state.messages) == 0:
    if not is_authenticated:
        if not active_scrape:
            initial_msg = (
                "⚠️ **No se ha detectado ningún análisis activo.**\n\n"
                "Como usuario invitado (sin iniciar sesión), el copiloto funciona **exclusivamente auditando los datos que extraigas en tiempo real**.\n\n"
                "👉 **Para comenzar:** Ingresa una URL en el panel principal y haz clic en **'Analizar'**.\n\n"
                "💡 *O inicia sesión en la barra superior si deseas consultar y comparar tus análisis históricos guardados.*"
            )
        else:
            site_name = active_scrape.get("site_title", "Página Web")
            site_url = active_scrape.get("url", "")
            items_num = active_scrape.get("total_items", 0)
            initial_msg = (
                f"👋 **Hola, he cargado los datos del análisis en vivo de:**\n"
                f"🌐 **{site_name}** (`{site_url}`)\n\n"
                f"Como usuario invitado, mis respuestas están **estrictamente delimitadas a los datos de esta extracción en tiempo real** ({items_num} registros procesados).\n\n"
                f"Puedes preguntarme sobre conclusiones estratégicas, riesgos detectados, análisis de sentimiento o detalles de este portal. ¿Qué deseas auditar?"
            )
    else:
        nombre_user = usuario_info.get("nombre") if usuario_info else (url_user or "Usuario")
        num_reportes = len(historial_reportes)
        live_suffix = f" además de la auditoría activa de **{active_scrape.get('site_title', 'Página Web')}**" if active_scrape else ""
        initial_msg = (
            f"👋 **Hola {nombre_user}, bienvenido a tu Copiloto SIMAP.**\n\n"
            f"Tienes acceso completo a tu historial con **{num_reportes} análisis previos** registrados en tu cuenta{live_suffix}.\n\n"
            f"Puedes preguntarme sobre **cualquiera de tus análisis anteriores**, comparar cambios temporales, consultar riesgos detectados o auditar la información. ¿Qué deseas consultar hoy?"
        )
    
    st.session_state.messages = [{"role": "assistant", "content": initial_msg}]

# =====================================================================
# BOTONES DE SUGERENCIA RÁPIDA (QUICK PROMPTS)
# =====================================================================
col1, col2, col3, col4 = st.columns(4)

prompt_sugerido = None
with col1:
    if st.button("📊 Conclusiones", use_container_width=True):
        prompt_sugerido = "¿Cuál es tu opinión crítica general sobre estos datos? ¿Qué conclusiones estratégicas sacas?"
with col2:
    if st.button("⚠️ Riesgos", use_container_width=True):
        prompt_sugerido = "¿Detectas alguna señal de alarma, conflicto social o riesgo urgente en estas publicaciones?"
with col3:
    if st.button("🎭 Sentimiento", use_container_width=True):
        prompt_sugerido = "Realiza un análisis de sentimiento e infiere el tono predominante de los comunicados extraídos."
with col4:
    if st.button("📑 Resumen", use_container_width=True):
        prompt_sugerido = "Sintetiza un resumen ejecutivo estructurado en 3 puntos clave con recomendaciones de acción."

# Mostrar historial de chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# =====================================================================
# ENTRADA DE TEXTO Y AUDIO (MICRÓFONO AL COSTADO DEL BOTÓN DE ENVIAR)
# =====================================================================
user_input = st.chat_input(
    "Escribe tu consulta o usa el micrófono para hablar...",
    accept_audio=True
)

prompt_final = None

if prompt_sugerido:
    prompt_final = prompt_sugerido
elif user_input:
    input_dict = user_input.to_dict() if hasattr(user_input, "to_dict") else {}
    texto_usuario = ""
    if isinstance(user_input, str):
        texto_usuario = user_input.strip()
    elif "text" in input_dict:
        texto_usuario = (input_dict.get("text") or "").strip()
    
    audio_obj = input_dict.get("audio")
    
    if audio_obj is not None:
        try:
            with st.spinner("🎙️ Transcribiendo audio con Google Gemini..."):
                audio_bytes = audio_obj.read()
                mime_type = getattr(audio_obj, "type", "audio/wav") or "audio/wav"
                transcrito = transcribir_audio_con_gemini(audio_bytes, mime_type, DEFAULT_GEMINI_KEY)
                if transcrito:
                    if texto_usuario:
                        prompt_final = f"{texto_usuario}\n\n🎙️ [Audio transcrito]: {transcrito}"
                    else:
                        prompt_final = f"🎙️ [Consulta por voz]: {transcrito}"
                else:
                    prompt_final = texto_usuario
        except Exception as e:
            st.error(f"Error procesando audio: {str(e)}")
            prompt_final = texto_usuario
    else:
        prompt_final = texto_usuario

if prompt_final:
    # 1. Registrar mensaje del usuario
    st.session_state.messages.append({"role": "user", "content": prompt_final})
    with st.chat_message("user"):
        st.markdown(prompt_final)

    # 2. Generar respuesta
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        # Validar si el usuario no autenticado no tiene datos de scraping
        if not is_authenticated and not active_scrape:
            no_data_reply = (
                "⚠️ **No se ha detectado ningún análisis activo en tu sesión.**\n\n"
                "Como usuario invitado, funciono **exclusivamente auditando los datos que extraigas en tiempo real**.\n\n"
                "👉 Por favor, ingresa una URL en el panel principal y haz clic en **'Analizar'** para auditar sus datos en vivo, "
                "o **inicia sesión** en la barra superior si deseas consultar y comparar tus análisis históricos guardados."
            )
            message_placeholder.markdown(no_data_reply)
            st.session_state.messages.append({"role": "assistant", "content": no_data_reply})

        elif client is None:
            error_msg = f"⚠️ **Cliente LLM no inicializado**: No se pudo conectar con {modelo_seleccionado} ({proveedor})."
            message_placeholder.markdown(error_msg)
            st.session_state.messages.append({"role": "assistant", "content": error_msg})

        else:
            try:
                # Construir System Prompt adaptado según el estado de autenticación
                if is_authenticated:
                    system_prompt = construir_prompt_modo_autenticado(
                        usuario_info or {"nombre": url_user or "Usuario"},
                        historial_reportes,
                        active_scrape
                    )
                else:
                    system_prompt = construir_prompt_modo_invitado(active_scrape)
                
                api_messages = [{"role": "system", "content": system_prompt}]
                for m in st.session_state.messages[-6:]:
                    api_messages.append({"role": m["role"], "content": m["content"]})

                with st.spinner(f"Analizando con {modelo_seleccionado}..."):
                    response_stream = client.chat.completions.create(
                        model=modelo_seleccionado,
                        messages=api_messages,
                        temperature=0.4,
                        stream=True
                    )
                    
                    for chunk in response_stream:
                        delta = chunk.choices[0].delta.content if chunk.choices else ""
                        if delta:
                            full_response += delta
                            message_placeholder.markdown(full_response + "▌")
                            
                    message_placeholder.markdown(full_response)
                
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                
            except Exception as e:
                err_text = f"❌ **Error al consultar el modelo ({modelo_seleccionado}):**\n`{str(e)}`\n\n*Puedes cambiar de modelo en el selector superior si este modelo presenta fallas.*"
                message_placeholder.markdown(err_text)
                st.session_state.messages.append({"role": "assistant", "content": err_text})
