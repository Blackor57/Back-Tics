# chatbot_service/Dockerfile
# Microservicio 5: Asistente Conversacional y Auditor de Inteligencia Web (Streamlit + Whisper)

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instalar utilitarios básicos para healthcheck y librerías
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar requerimientos e instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar código del microservicio
COPY . .

# Puerto expuesto por Streamlit
EXPOSE 8501

# Healthcheck nativo de Streamlit
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Arrancar la aplicación Streamlit accesible para la red interna y externa de Docker
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.enableCORS=false", "--server.enableXsrfProtection=false"]
