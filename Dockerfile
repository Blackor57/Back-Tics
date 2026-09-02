# Imagen base oficial de Playwright en Python (Ubuntu 22.04 LTS)
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Evitar escritura de bytecode y habilitar salida de logs en tiempo real
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copiar requerimientos e instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Asegurar la presencia de los binarios y dependencias de Chromium
RUN playwright install --with-deps chromium

# Copiar el código fuente
COPY . .

# Puerto expuesto por FastAPI
EXPOSE 8000

# Arrancar el servidor Uvicorn en todas las interfaces de red
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]