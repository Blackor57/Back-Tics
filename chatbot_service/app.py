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

# =====================================================================
# CONFIGURACIÓN DE PÁGINA Y ESTILOS
# =====================================================================
st.set_page_config(
    page_title="SIMAP - Chatbot Auditor de Inteligencia Web",
    page_icon="🕷️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header {
        font-size: 2.1rem;
        font-weight: 700;
        background: linear-gradient(90deg, #4f46e5, #06b6d4);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 0.95rem;
        color: #94a3b8;
        margin-bottom: 1.2rem;
    }
    .context-card {
        background-color: rgba(30, 41, 59, 0.7);
        border: 1px solid rgba(148, 163, 184, 0.2);
        border-radius: 10px;
        padding: 12px 18px;
        margin-bottom: 15px;
    }
    .badge-tag {
        display: inline-block;
        background: #1e293b;
        color: #38bdf8;
        border: 1px solid #38bdf8;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-right: 6px;
        margin-top: 4px;
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
</style>
""", unsafe_allow_html=True)

# =====================================================================
# DATOS DE RESPALDO / DEMOSTRACIÓN
# =====================================================================
SAMPLE_SCRAPED_DATA = {
    "url": "https://www.gob.pe/noticias-minem",
    "site_title": "Ministerio de Energía y Minas - Portal Institucional",
    "fecha_captura": datetime.now().strftime("%Y-%m-%d %H:%M"),
    "tipo": "Portal Institucional / Noticias",
    "items": [
        {
            "titulo": "MINEM aprueba nuevo cronograma de transición energética y subsidios solares",
            "url": "https://www.gob.pe/noticias/minem-transicion-energetica",
            "resumen": "Se asigna un fondo extraordinario de 150 millones para la electrificación rural mediante paneles solares. Las empresas distribuidoras tendrán 90 días para adaptarse a los nuevos estándares.",
            "fecha": "2026-09-20"
        },
        {
            "titulo": "Conflictos sociales en corredor minero del sur reducen despacho de cobre en un 12%",
            "url": "https://www.gob.pe/noticias/minem-corredor-minero-alerta",
            "resumen": "Comunidades locales bloquean el tramo del kilómetro 45 exigiendo adelanto de canon y remediación ambiental. El ministerio convoca a mesa de diálogo de urgencia.",
            "fecha": "2026-09-21"
        },
        {
            "titulo": "Actualización de tarifas eléctricas industriales entrará en vigencia a fin de mes",
            "url": "https://www.gob.pe/noticias/minem-tarifas-electricas",
            "resumen": "Osinergmin y Minem comunican un ajuste promedio del 3.4% en tarifas industriales debido al incremento de costos en transmisión en alta tensión.",
            "fecha": "2026-09-21"
        },
        {
            "titulo": "Convocatoria pública para auditoría externa de concesiones de hidrocarburos",
            "url": "https://www.gob.pe/noticias/minem-licitacion-hidrocarburos",
            "resumen": "Plazo límite de postulación vence en 15 días calendario. Se auditarán los contratos de explotación vigentes entre 2020 y 2025.",
            "fecha": "2026-09-19"
        }
    ]
}

# =====================================================================
# COMUNICACIÓN CON OTROS MICROSERVICIOS (REST HTTPX)
# =====================================================================
@st.cache_data(ttl=20)
def consultar_snapshots_backend(api_url: str) -> List[Dict[str, Any]]:
    """Consulta los últimos snapshots al Microservicio Core API (FastAPI)."""
    try:
        url = f"{api_url}/api/v1/snapshots/latest"
        resp = httpx.get(url, timeout=3.0)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return []

@st.cache_data(ttl=20)
def consultar_modelos_ollama(base_url: str) -> List[str]:
    """Consulta los modelos disponibles al Microservicio de Ollama."""
    try:
        url = f"{base_url}/api/tags"
        resp = httpx.get(url, timeout=2.0)
        if resp.status_code == 200:
            data = resp.json()
            return [m.get("name") for m in data.get("models", [])]
    except Exception:
        pass
    return []

def solicitar_scraping_en_vivo(api_url: str, target_url: str) -> Optional[Dict[str, Any]]:
    """Pide al Microservicio Core API que ordene al worker de Playwright scrapear una URL."""
    try:
        url = f"{api_url}/api/v1/scrape/index"
        payload = {"url": target_url, "guardar_snapshot": True}
        resp = httpx.post(url, json=payload, timeout=60.0)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        st.error(f"Error al comunicar con Core API ({api_url}): {str(e)}")
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
# BARRA LATERAL: CONFIGURACIÓN DE MICROSERVICIOS Y MODELOS
# =====================================================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/8649/8649595.png", width=55)
    st.markdown("### ⚙️ Motor de IA (LLM)")
    
    proveedor = st.radio(
        "Proveedor del LLM:",
        ["Google Gemini (Recomendado)", "Ollama (Microservicio Local)"],
        index=0,
        help="Google Gemini es el motor principal activo. También puedes alternar a Ollama local."
    )
    
    api_key = DEFAULT_GEMINI_KEY
    client: Optional[OpenAI] = None
    modelo_seleccionado = ""
    
    if proveedor == "Google Gemini (Recomendado)":
        api_key = st.text_input(
            "Gemini API Key:",
            value=DEFAULT_GEMINI_KEY,
            type="password",
            placeholder="AQ.Ab8...",
            help="Clave de API de Google Gemini para inferencia del chatbot."
        )
        modelo_seleccionado = st.selectbox(
            "Modelo Gemini:",
            ["gemini-3.1-flash-lite", "gemini-3.8-flash", "gemini-3.5-flash", "gemini-flash-latest"],
            index=0
        )
        if api_key:
            client = OpenAI(
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                api_key=api_key
            )
            st.markdown(f'<span class="badge-tag badge-success">🟢 Gemini Conectado ({modelo_seleccionado})</span>', unsafe_allow_html=True)
        else:
            st.info("💡 Ingresa tu Gemini API Key para chatear.")

    else:
        ollama_endpoint = st.text_input("URL de Ollama:", value=OLLAMA_BASE_URL)
        modelos_locales = consultar_modelos_ollama(ollama_endpoint)
        
        if modelos_locales:
            st.markdown(f'<span class="badge-tag badge-success">🟢 Ollama Conectado ({len(modelos_locales)} modelos)</span>', unsafe_allow_html=True)
            modelo_seleccionado = st.selectbox("Modelo Ollama detectado:", modelos_locales)
        else:
            st.markdown('<span class="badge-tag badge-warning">🔴 Ollama no detectado</span>', unsafe_allow_html=True)
            st.caption(f"Verifica el contenedor de Ollama en `{ollama_endpoint}`.")
            modelo_seleccionado = st.text_input("Nombre de Modelo Ollama:", value="llama3.1:latest")
            
        client = OpenAI(
            base_url=f"{ollama_endpoint}/v1",
            api_key="ollama"
        )

    st.markdown("---")
    
    # 2. Origen de Datos Scrapeados (Consumo de Microservicio Core API)
    st.markdown("### 📂 Datos Scrapeados a Auditar")
    backend_endpoint = st.text_input("Core API URL:", value=BACKEND_API_URL, help="Endpoint del Microservicio 1 (FastAPI)")
    
    origen_datos = st.selectbox(
        "Fuente de los datos:",
        ["Capturas de Core API (PostgreSQL)", "Scraping en Vivo (Playwright)", "Ejemplo Precargado (MINEM)", "Texto Libre / JSON"]
    )
    
    contexto_actual = SAMPLE_SCRAPED_DATA
    
    if origen_datos == "Capturas de Core API (PostgreSQL)":
        snapshots = consultar_snapshots_backend(backend_endpoint)
        if snapshots:
            st.markdown('<span class="badge-tag badge-success">🟢 Core API Conectada</span>', unsafe_allow_html=True)
            opciones_snap = {
                f"[{s['id']}] {s['site_title']} ({s['total_items']} items)": s 
                for s in snapshots
            }
            elegido = st.selectbox("Seleccionar Captura:", list(opciones_snap.keys()))
            snap = opciones_snap[elegido]
            contexto_actual = {
                "url": snap["url"],
                "site_title": snap["site_title"],
                "fecha_captura": snap["created_at"],
                "tipo": snap["tipo_contenido"],
                "items": snap["data"]
            }
        else:
            st.markdown('<span class="badge-tag badge-warning">⚠️ Sin snapshots en Core API</span>', unsafe_allow_html=True)
            st.caption(f"No se pudo consultar `{backend_endpoint}/api/v1/snapshots/latest` o la BD está vacía. Usando datos de demostración.")
            contexto_actual = SAMPLE_SCRAPED_DATA
            
    elif origen_datos == "Scraping en Vivo (Playwright)":
        url_input = st.text_input("URL para scrapear en tiempo real:", value="https://news.ycombinator.com")
        if st.button("🚀 Disparar Scraping en Vivo", use_container_width=True):
            with st.spinner("El Microservicio 1 (FastAPI) y Microservicio 2 (Playwright) están scrapeando la página..."):
                resultado_scraped = solicitar_scraping_en_vivo(backend_endpoint, url_input)
                if resultado_scraped:
                    st.success("✅ Scraping completado con éxito!")
                    contexto_actual = {
                        "url": resultado_scraped.get("url", url_input),
                        "site_title": resultado_scraped.get("site_title", "Página Scrapeada"),
                        "fecha_captura": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "tipo": resultado_scraped.get("tipo_contenido", "Index"),
                        "items": resultado_scraped.get("data", [])
                    }
                    st.session_state.contexto_en_vivo = contexto_actual
        if "contexto_en_vivo" in st.session_state:
            contexto_actual = st.session_state.contexto_en_vivo

    elif origen_datos == "Texto Libre / JSON":
        texto_custom = st.text_area(
            "Pega aquí datos de productos, artículos o noticias:",
            value=json.dumps(SAMPLE_SCRAPED_DATA["items"], indent=2, ensure_ascii=False),
            height=130
        )
        contexto_actual = {
            "url": "Ingreso Manual de Analista",
            "site_title": "Dataset personalizado",
            "fecha_captura": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "tipo": "Personalizado",
            "items": texto_custom
        }

    st.markdown("---")
    
    # 3. Transcripción de Audio por Voz (Google Gemini Multimodal)
    st.markdown("### 🎙️ Comandos por Voz")
    st.caption("Graba tu voz o sube un audio para consultar al bot.")
    
    audio_transcrito_prompt = None
    
    mic_audio = st.audio_input("Grabar desde el micrófono:")
    archivo_audio = st.file_uploader("O subir archivo de audio:", type=["mp3", "wav", "m4a", "ogg"])
    
    audio_seleccionado = mic_audio or archivo_audio
    
    if audio_seleccionado is not None:
        if st.button("Transcribir Audio con Gemini 🎧", use_container_width=True):
            if not api_key or proveedor != "Google Gemini (Recomendado)":
                st.error("Se requiere Gemini API Key en la barra lateral para transcribir audio.")
            else:
                try:
                    with st.spinner("Transcribiendo audio con Google Gemini..."):
                        audio_bytes = audio_seleccionado.read()
                        mime_type = getattr(audio_seleccionado, "type", "audio/wav") or "audio/wav"
                        texto_transcrito = transcribir_audio_con_gemini(audio_bytes, mime_type, api_key)
                        if texto_transcrito:
                            audio_transcrito_prompt = texto_transcrito
                            st.success("¡Transcripción completada con éxito!")
                            st.info(f'"{audio_transcrito_prompt}"')
                except Exception as e:
                    st.error(f"Error en transcripción: {str(e)}")

    st.markdown("---")
    if st.button("🧹 Limpiar Historial de Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# =====================================================================
# SISTEMA DE PROMPT ENGINEERING (RÚBRICA DE EVALUACIÓN)
# =====================================================================
def construir_system_prompt(contexto: Dict[str, Any]) -> str:
    """
    Construye el System Prompt aplicando formalmente los principios de Prompt Engineering:
    - Delimitadores (###)
    - Definición de Rol y Personalidad
    - Chain of Thought (Pasos de razonamiento previo)
    - Inferencia, Análisis de Sentimiento y Emisión de Opinión Crítica
    """
    datos_serializados = json.dumps(contexto.get("items", []), ensure_ascii=False, indent=2) if isinstance(contexto.get("items"), (list, dict)) else str(contexto.get("items", ""))
    
    return f"""Eres un **Auditor Senior de Inteligencia Web y Analista Estratégico de Datos Scrapeados**.
Tu labor es examinar la información extraída de la web y emitir una **opinión analítica, crítica y fundamentada**.

### METODOLOGÍA DE RAZONAMIENTO (Chain of Thought):
1. **Inspección:** Lee atentamente los datos en la sección delimitada.
2. **Inferencia y Sentimiento:** Evalúa el trasfondo de las publicaciones. Detecta si el tono es optimista, alarmante, institucional o defensivo.
3. **Detección de Riesgos y Alertas:** Identifica conflictos, ajustes tarifarios, cambios regulatorios, fechas límite o discrepancias.
4. **Opinión Crítica:** No seas un loro que solo repite las noticias. Ofrece conclusiones con valor añadido: qué implicancias tienen estos hechos, qué riesgos conllevan y qué acciones recomiendas.
5. **Formato:** Utiliza formato Markdown profesional, viñetas y estructuración clara.

### DELIMITADORES DE CONTEXTO:
Los datos que has recibido del proceso de scraping se encuentran estrictamente delimitados a continuación:

### CONTEXTO DE DATOS SCRAPEADOS ###
- **URL Objetivo:** {contexto.get("url")}
- **Título del Portal:** {contexto.get("site_title")}
- **Fecha de Captura:** {contexto.get("fecha_captura")}
- **Categoría/Tipo:** {contexto.get("tipo")}

CONTENIDO EXTRAÍDO:
{datos_serializados}
### FIN DE DATOS SCRAPEADOS ###

Responde siempre en español, manteniendo tu postura de auditor experto y respaldando tu opinión con los datos disponibles."""

# =====================================================================
# PANTALLA PRINCIPAL: CHATBOT AUDITOR
# =====================================================================
st.markdown('<div class="main-header">🕷️ SIMAP - Chatbot Auditor de Inteligencia Web</div>', unsafe_allow_html=True)
st.markdown(
    f'<div class="sub-header">Microservicio 5: Asistente Conversacional & Voz (Whisper) | Conectado a Core API ({BACKEND_API_URL})</div>',
    unsafe_allow_html=True
)

# Tarjeta de contexto activo
items_count = len(contexto_actual["items"]) if isinstance(contexto_actual["items"], list) else "Contenido directo"
st.markdown(f"""
<div class="context-card">
    <span class="badge-tag">🌐 Portal: {contexto_actual.get('site_title', 'Sin título')}</span>
    <span class="badge-tag">🔗 URL: {contexto_actual.get('url', 'N/A')}</span>
    <span class="badge-tag">📊 Registros: {items_count}</span>
    <span class="badge-tag badge-warning">🤖 Motor: {modelo_seleccionado} ({proveedor.split()[0]})</span>
</div>
""", unsafe_allow_html=True)

# Inicializar historial de mensajes
if "messages" not in st.session_state or len(st.session_state.messages) == 0:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": f"👋 **Hola, soy tu Auditor de Inteligencia Web.** He cargado los datos scrapeados de **{contexto_actual.get('site_title')}**.\n\nPuedo responder cualquier pregunta, evaluar el sentimiento de las noticias, identificar posibles alertas o emitir mi **opinión analítica** sobre esta información. ¿Qué deseas analizar?"
        }
    ]

# Botones de sugerencia rápida (Quick Prompts)
st.markdown("**💡 Consultas analíticas rápidas:**")
col1, col2, col3, col4 = st.columns(4)

prompt_sugerido = None
with col1:
    if st.button("📊 Opinión y Conclusiones", use_container_width=True):
        prompt_sugerido = "¿Cuál es tu opinión crítica general sobre estos datos scrapeados? ¿Qué conclusiones estratégicas sacas?"
with col2:
    if st.button("⚠️ Detectar Alertas y Riesgos", use_container_width=True):
        prompt_sugerido = "¿Detectas alguna señal de alarma, conflicto social o riesgo operativo urgente en estas publicaciones?"
with col3:
    if st.button("🎭 Análisis de Sentimiento", use_container_width=True):
        prompt_sugerido = "Realiza un análisis de sentimiento e infiere el tono predominante de los comunicados extraídos."
with col4:
    if st.button("📑 Resumen Ejecutivo", use_container_width=True):
        prompt_sugerido = "Sintetiza un resumen ejecutivo estructurado en 3 puntos clave con recomendaciones de acción."

# Si hubo audio transcrito por Whisper, asignarlo como prompt
if audio_transcrito_prompt:
    prompt_sugerido = f"🎙️ [Consulta por Voz vía Whisper]: {audio_transcrito_prompt}"

# Mostrar historial de chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Entrada de texto del usuario
user_query = st.chat_input("Escribe tu consulta o pide una opinión sobre los datos scrapeados...")

prompt_final = user_query or prompt_sugerido

if prompt_final:
    # 1. Registrar mensaje del usuario
    st.session_state.messages.append({"role": "user", "content": prompt_final})
    with st.chat_message("user"):
        st.markdown(prompt_final)

    # 2. Generar respuesta
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        if proveedor == "Google Gemini (Recomendado)" and not api_key:
            error_msg = "⚠️ **Gemini API Key requerida**: Por favor, ingresa tu clave de Google Gemini en la barra lateral para poder interactuar."
            message_placeholder.markdown(error_msg)
            st.session_state.messages.append({"role": "assistant", "content": error_msg})
        elif client is None:
            error_msg = "⚠️ **Cliente LLM no inicializado**: Revisa la configuración en la barra lateral."
            message_placeholder.markdown(error_msg)
            st.session_state.messages.append({"role": "assistant", "content": error_msg})
        else:
            try:
                system_prompt = construir_system_prompt(contexto_actual)
                
                api_messages = [{"role": "system", "content": system_prompt}]
                for m in st.session_state.messages[-6:]:
                    api_messages.append({"role": m["role"], "content": m["content"]})

                with st.spinner(f"Analizando datos con {modelo_seleccionado}..."):
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
                err_text = f"❌ **Error al consultar el modelo ({modelo_seleccionado}):**\n`{str(e)}`\n\n*Si estás usando Google Gemini, verifica tu API Key. Si estás usando Ollama, verifica que esté corriendo en tu equipo (`ollama serve`) o dentro del contenedor.*"
                message_placeholder.markdown(err_text)
                st.session_state.messages.append({"role": "assistant", "content": err_text})
