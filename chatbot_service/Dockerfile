# chatbot_service/Dockerfile
# Microservicio 5: SIMAP Chatbot RAG (FastAPI + Ollama + Redis + pgvector)

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Herramienta para healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Código del microservicio (main.py + paquete app/)
COPY . .

# Puerto expuesto por FastAPI
EXPOSE 8501

# Healthcheck contra /health
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl --fail http://localhost:8501/health || exit 1

# Arranque: Uvicorn con un solo worker (memoria compartida con Ollama)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8501", "--workers", "1", "--log-level", "info"]