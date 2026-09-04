# 🌐 SIMAP - Universal Web Scraper & Intelligence Platform (Backend)

Plataforma empresarial de **inteligencia web, extracción distribuida con Playwright, análisis comparativo de deltas históricos, inferencia semántica local con LLM (Ollama / LLaMA 3.1), autenticación JWT, monitoreo continuo y generación de reportes ejecutivos en Word y Excel**.

---

## 📑 Tabla de Contenidos
- [🏗️ Arquitectura de Microservicios](#️-arquitectura-de-microservicios)
- [✨ Características Principales](#-características-principales)
- [📁 Estructura del Proyecto](#-estructura-del-proyecto)
- [⚙️ Variables de Entorno](#️-variables-de-entorno)
- [🚀 Cómo Ejecutar el Proyecto](#-cómo-ejecutar-el-proyecto)
  - [Opción 1: Con Docker Compose (Recomendada)](#opción-1-con-docker-compose-recomendada)
  - [Opción 2: Ejecución Local Nativa (Desarrollo)](#opción-2-ejecución-local-nativa-desarrollo)
- [📚 Endpoints de la API](#-endpoints-de-la-api)
- [🧪 Pruebas Automatizadas](#-pruebas-automatizadas)
- [☁️ Despliegue en Producción (AWS)](#️-despliegue-en-producción-aws)

---

## 🏗️ Arquitectura de Microservicios

El sistema implementa una arquitectura desacoplada y orientada a microservicios orquestada mediante Docker Compose:

```mermaid
graph TD
    Client["Cliente Web / Frontend (Repo Externo)"] -->|HTTP :8000| Core["1. Core Backend & Orquestador\n(FastAPI)"]
    
    Core -->|HTTP :8001| Scraper["2. Worker de Scraping\n(Playwright + Chromium)"]
    Core -->|HTTP :11434| Ollama["3. IA Local\n(Ollama - LLaMA 3.1)"]
    Core -->|TCP :5432| DB[("4. Base de Datos\n(PostgreSQL 16)")]
    
    Scraper -->|Renderiza & Extrae| Web["Internet / Páginas Web"]
    Core -->|Genera Reportes| Reports["Almacén de Reportes\n(.xlsx / .docx)"]
    Core -->|Alertas SMTP| Email["Notificaciones por Correo"]
```

### Los 4 Microservicios del Ecosistema:

1. **`simap_backend` (Core API & Orquestador - Puerto 8000)**:
   - Framework: **FastAPI** (Python 3.11).
   - Funciones: Enrutamiento REST, autenticación JWT, orquestación del flujo, comparativa histórica (*Delta Engine*), programación de monitoreo periódico ([`MonitorScheduler`](app/services/monitor_scheduler.py)), despacho de alertas por email y exportación de reportes ejecutivos con gráficos estadísticos.

2. **`simap_scraper_service` (Worker de Extracción Web - Puerto 8001)**:
   - Framework: **FastAPI + Playwright (Headless Chromium)**.
   - Funciones: Aislado en su propio contenedor para proteger memoria RAM y CPU. Se encarga de navegar sitios dinámicos, scroll de *lazy-loading*, bypass básico de bloqueos y extracción limpia de contenido estructurado en Markdown.

3. **`simap_ollama` (Motor de Inteligencia Artificial - Puerto 11434)**:
   - Motor: **Ollama** con modelo `llama3.1:latest` (8B).
   - Funciones: Inferencia semántica 100% local y privada. Clasifica noticias en categorías, analiza polaridad de sentimientos, detecta entidades y genera resúmenes ejecutivos sin enviar datos a APIs externas.

4. **`simap_postgres` (Persistencia Relacional - Puerto 5432)**:
   - Motor: **PostgreSQL 16 Alpine**.
   - Funciones: Persistencia de usuarios (`users`), instantáneas web (`snapshots`), URLs en monitoreo continuo (`tracked_targets`) y metadatos de reportes (`analysis_reports`). Inicializado automáticamente con [`init.sql`](init.sql).

---

## ✨ Características Principales

- **Scraping Híbrido Multicapa**:
  - *Nivel 1 (Índice)*: Detección inteligente de listas de artículos/novedades o contenido continuo.
  - *Nivel 2 (Deep Scraping)*: Extracción paralela del cuerpo completo de artículos en formato Markdown limpio.
  - *Pipeline Completo*: Flujo integrado que extrae el índice y profundiza automáticamente en los primeros $N$ enlaces.
- **Motor de Deltas Históricos**:
  - Compara la versión actual de una web contra la anterior guardada en PostgreSQL.
  - Detecta altas (nuevas noticias), bajas (noticias retiradas) y calcula la tasa de rotación informativa.
- **Reportes Ejecutivos Automáticos**:
  - **Excel (.xlsx)**: Tablas con diseño profesional, formato condicional, hojas de métricas y gráficos circulares y de barras generados dinámicamente.
  - **Word (.docx)**: Informes ejecutivos con portada formal, tablas tipografiadas, paleta corporativa e inserción de gráficos estadísticos generados con Matplotlib.
- **Monitoreo Continuo & Alertas**:
  - Monitoreo programable de 1 a 30 días con frecuencias configurables (cada 1, 6, 12, 24 horas).
  - Tareas en segundo plano que analizan cambios con IA y despachan correos automáticos si se detectan variaciones importantes.
- **Seguridad y Control de Acceso**:
  - Autenticación mediante tokens JWT (JSON Web Tokens).
  - Hashing seguro de contraseñas con `bcrypt`.

---

## 📁 Estructura del Proyecto

```text
Backend/
├── app/                          # Microservicio 1: Core Backend & API
│   ├── api/v1/                   # Endpoints REST modulares
│   │   ├── auth.py               # Registro, login y perfil JWT
│   │   ├── endpoint.py           # Endpoints de scraping, IA, reportes y snapshots
│   │   └── tracking.py           # Monitoreo continuo y programación de tareas
│   ├── core/                     # Configuraciones base, seguridad y base de datos
│   │   ├── config.py             # Variables de entorno y ajustes generales
│   │   ├── database.py           # Motor async SQLAlchemy y sesiones
│   │   └── security.py           # Hashing bcrypt y codificación/decodificación JWT
│   ├── models/                   # Modelos ORM SQLAlchemy
│   │   └── entities.py           # Tablas: User, Snapshot, AnalysisReport, TrackedTarget
│   ├── schemas/                  # Validación de esquemas Pydantic
│   │   ├── auth.py               # Esquemas de autenticación y usuarios
│   │   ├── schemas.py            # Esquemas de scraping y análisis
│   │   └── tracking.py           # Esquemas de seguimiento y alertas
│   ├── services/                 # Capa de lógica de negocio y servicios
│   │   ├── chart_generator.py    # Generación de gráficos con Matplotlib
│   │   ├── email_service.py      # Envío de alertas por correo (SMTP)
│   │   ├── excel_reporter.py     # Generador de informes en Excel (.xlsx)
│   │   ├── monitor_scheduler.py  # Scheduler en background para monitoreo continuo
│   │   ├── ollama_analyzer.py    # Cliente de inferencia con Ollama LLM
│   │   ├── scraper_client.py     # Cliente HTTP hacia el worker de scraping
│   │   ├── snapshot_service.py   # Gestión y persistencia de snapshots en DB
│   │   └── word_reporter.py      # Generador de reportes ejecutivos en Word (.docx)
│   └── main.py                   # Punto de entrada de la aplicación FastAPI
│
├── scraper_service/              # Microservicio 2: Worker de Scraping
│   ├── Dockerfile                # Imagen Docker con Playwright y Chromium
│   ├── config.py                 # Configuración de timeouts y navegador
│   ├── deep_scraper.py           # Extractor a profundidad de artículos (Markdown)
│   ├── main.py                   # API REST del worker (puerto 8001)
│   ├── requirements.txt          # Dependencias específicas de Playwright
│   ├── scraper.py                # Extractor de índices y detección de patrones
│   └── utils.py                  # Utilidades de limpieza de HTML y texto
│
├── docs/                         # Documentación técnica detallada
│   ├── DEPLOY_AWS.md             # Guía de despliegue en AWS EC2 con Docker
│   ├── EJEMPLOS.md               # Ejemplos exhaustivos de peticiones cURL y JSON
│   └── QUICK_START.md            # Guía de inicio rápido
│
├── reports/                      # Directorio de almacenamiento temporal de reportes
├── scripts/                      # Scripts para Windows y Linux
│   ├── iniciar.bat               # Inicio rápido en Windows
│   └── iniciar.sh                # Inicio rápido en Linux / macOS
├── tests/                        # Suite completa de pruebas con Pytest
│   ├── test_delta_engine.py      # Pruebas del motor de comparación histórica
│   ├── test_reporters.py         # Pruebas de generación de Word y Excel
│   ├── test_schemas.py           # Pruebas de validación de datos
│   ├── test_scraper_client.py    # Pruebas del cliente HTTP de scraping
│   └── test_security.py          # Pruebas de JWT y hashing de contraseñas
│
├── docker-compose.yml            # Orquestación de los 4 microservicios
├── Dockerfile                    # Dockerfile del Core Backend
├── init.sql                      # Inicialización del esquema de base de datos
├── requirements.txt              # Dependencias del Core Backend
└── run_local.py                  # Script de conveniencia para ejecución local
```

---

## ⚙️ Variables de Entorno

Crea un archivo `.env` en la raíz del proyecto tomando como referencia las siguientes variables:

```env
# =========================================================
# BASE DE DATOS (POSTGRESQL)
# =========================================================
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=simap_db
DATABASE_URL=postgresql+asyncpg://postgres:postgres_password@localhost:5432/simap_db

# =========================================================
# MICROSERVICIO DE IA (OLLAMA)
# =========================================================
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:latest
OLLAMA_TIMEOUT_SECONDS=180.0

# =========================================================
# MICROSERVICIO DE SCRAPING
# =========================================================
SCRAPER_SERVICE_URL=http://localhost:8001

# =========================================================
# AUTENTICACIÓN JWT
# =========================================================
JWT_SECRET_KEY=clave-secreta-super-segura-cambiala-en-produccion
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080

# =========================================================
# NOTIFICACIONES POR CORREO (SMTP)
# (Si se deja SMTP_HOST vacío, el sistema simula el envío en los logs)
# =========================================================
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tu_correo@gmail.com
SMTP_PASSWORD=tu_contraseña_de_aplicacion
SMTP_FROM_EMAIL=notificaciones@simap.com
SMTP_TLS=true
```

---

## 🚀 Cómo Ejecutar el Proyecto

### Opción 1: Con Docker Compose (Recomendada)

Levanta la arquitectura completa (Base de datos, Ollama, Worker de Scraping y Core Backend) con un solo comando:

```bash
# 1. Construir y levantar todos los contenedores en segundo plano
docker compose up --build -d

# 2. Descargar el modelo de IA en el contenedor de Ollama (solo la primera vez)
docker exec -it simap_ollama ollama pull llama3.1:latest
```

Verifica el estado de los contenedores:
```bash
docker compose ps
```

Para detener los servicios:
```bash
docker compose down
```

---

### Opción 2: Ejecución Local Nativa (Desarrollo)

Si prefieres correr los servicios directamente en tu máquina:

#### 1. Prerrequisitos
- Python 3.10+ o 3.11 instalado.
- Servidor **PostgreSQL** corriendo con una base de datos `simap_db`.
- **Ollama** instalado y corriendo (`ollama run llama3.1:latest`).

#### 2. Configurar el Entorno Virtual
```bash
python -m venv venv

# En Windows:
venv\Scripts\activate
# En Linux/macOS:
source venv/bin/activate

# Instalar dependencias del backend
pip install -r requirements.txt
```

#### 3. Iniciar el Microservicio de Scraping
En una terminal separada:
```bash
# Instalar dependencias del scraper y los binarios de Chromium
pip install -r scraper_service/requirements.txt
playwright install chromium

# Ejecutar worker en el puerto 8001
python -m uvicorn scraper_service.main:app --host 0.0.0.0 --port 8001 --reload
```

#### 4. Iniciar el Core Backend
En la terminal principal:
```bash
python run_local.py
```
O usando Uvicorn directamente:
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 📚 Endpoints de la API

Una vez iniciado el servidor, accede a la documentación interactiva en:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

### Resumen de Endpoints Principales:

| Módulo | Método | Endpoint | Descripción |
|---|---|---|---|
| **Salud** | `GET` | `/health` | Verificación de estado de la API |
| **Scraping** | `POST` | `/api/v1/scrape/index` | Extracción de índice/portada |
| **Scraping** | `POST` | `/api/v1/scrape/deep` | Extracción a profundidad en Markdown |
| **Scraping** | `POST` | `/api/v1/scrape/full-pipeline` | Extracción combinada (Índice + Detalle) |
| **Inteligencia** | `POST` | `/api/v1/intelligence/analyze` | Análisis IA, cálculo de Deltas y generación de reportes |
| **Reportes** | `GET` | `/api/v1/reports/download/excel/{id}` | Descarga de reporte en formato Excel (`.xlsx`) |
| **Reportes** | `GET` | `/api/v1/reports/download/word/{id}` | Descarga de reporte en formato Word (`.docx`) |
| **Reportes** | `GET` | `/api/v1/reports/list` | Listado histórico de reportes generados |
| **Snapshots** | `GET` | `/api/v1/snapshots/history` | Historial de capturas de una URL |
| **Auth** | `POST` | `/api/v1/auth/register` | Registro de nuevo usuario (JWT) |
| **Auth** | `POST` | `/api/v1/auth/login` | Inicio de sesión y obtención de token |
| **Auth** | `GET` | `/api/v1/auth/me` | Datos del usuario autenticado |
| **Monitoreo** | `POST` | `/api/v1/tracking/start` | Iniciar seguimiento continuo de una URL |
| **Monitoreo** | `GET` | `/api/v1/tracking/my-targets` | Listar objetivos de seguimiento del usuario |
| **Monitoreo** | `PATCH` | `/api/v1/tracking/{id}/toggle` | Pausar o reanudar seguimiento |
| **Monitoreo** | `DELETE` | `/api/v1/tracking/{id}` | Eliminar objetivo de monitoreo |

> [!TIP]
> Para consultar ejemplos completos de peticiones cURL, payloads JSON y respuestas, revisa [docs/EJEMPLOS.md](docs/EJEMPLOS.md).

---

## 🧪 Pruebas Automatizadas

El proyecto cuenta con una batería de tests unitarios y de integración para validar la seguridad, el procesamiento de esquemas, los motores de reportes y la comparación de deltas:

```bash
# Ejecutar todas las pruebas
pytest

# Ejecutar con reporte detallado
pytest -v -s
```

---

## ☁️ Despliegue en Producción (AWS)

Para desplegar este backend en una instancia **AWS EC2 (Ubuntu)** con Docker Compose, certificados SSL gratuitos (Let's Encrypt) y proxy inverso Nginx, consulta la guía paso a paso en:

👉 [docs/DEPLOY_AWS.md](docs/DEPLOY_AWS.md)
