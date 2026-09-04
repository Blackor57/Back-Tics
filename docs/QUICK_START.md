# 🚀 Inicio Rápido - Web Scraper API (Backend)

Este repositorio contiene exclusivamente el **Backend (API REST con FastAPI y Playwright)**. El Frontend se ejecuta en su propio repositorio independiente.

---

## ⚡ Formas de Iniciar el Backend

### Opción 1: Scripts Automáticos

#### En Windows
```cmd
scripts\iniciar.bat
```


#### En Linux/macOS
```bash
chmod +x scripts/iniciar.sh
./scripts/iniciar.sh
```

---

### Opción 2: Con Python directo

```bash
python run_local.py
```

o usando Uvicorn:

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

### Opción 3: Con Docker / Docker Compose

```bash
docker compose up --build
```

---

## 📚 URLs de la API

| Recurso | URL | Propósito |
|---|---|---|
| **API Base** | `http://localhost:8000` | Endpoint raíz con información y estado |
| **Health Check** | `http://localhost:8000/health` | Verificación de estado del servidor |
| **Documentación Swagger** | `http://localhost:8000/docs` | Interfaz interactiva para probar endpoints |
| **Documentación ReDoc** | `http://localhost:8000/redoc` | Especificación técnica OpenAPI |

---

## 🌐 Conexión con el Frontend Separado

Dado que el frontend está alojado en otro repositorio (por ejemplo en React, Vue, Vite, Next.js o un servidor web local):

1. **CORS:** El backend tiene CORS habilitado para todos los orígenes en desarrollo.
2. **URL Base para el Frontend:** Configura la variable de entorno o constante en tu frontend apuntando a:
   ```javascript
   const API_BASE_URL = 'http://localhost:8000';
   ```
3. **Endpoints Disponibles para el Frontend:**
   - `POST /api/v1/scrape/index`: Extrae el índice o portada de un sitio.
   - `POST /api/v1/scrape/deep`: Extrae el contenido en texto limpio de una o varias URLs.
   - `POST /api/v1/scrape/full-pipeline`: Pipeline automático que extrae índice y procesa los primeros $N$ artículos.
   - `POST /api/v1/intelligence/analyze`: Analiza con Ollama (local), calcula delta vs versión previa en PostgreSQL y genera Excel y Word con gráficos.
   - `GET /api/v1/reports/download/excel/{id}`: Descarga directa del archivo Excel (.xlsx).
   - `GET /api/v1/reports/download/word/{id}`: Descarga directa del informe Word (.docx).
   - `GET /api/v1/reports/list`: Listado del historial de análisis y reportes emitidos.
   - `GET /api/v1/snapshots/history`: Historial de capturas registradas de una URL.

---

## 📁 Estructura del Repositorio Backend

```
Backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       └── endpoint.py       # Endpoints REST (Scrape, Ollama Intelligence, Descargas)
│   ├── core/
│   │   ├── config.py             # Configuración de PostgreSQL, Ollama, Viewport y Rutas
│   │   └── database.py           # Conexión asíncrona a PostgreSQL con SQLAlchemy + asyncpg
│   ├── models/
│   │   └── entities.py           # Modelos ORM (Snapshots con JSONB y AnalysisReport)
│   ├── services/
│   │   ├── scraper.py            # Extractor de nivel 1 (Índices y portadas)
│   │   ├── deep_scraper.py       # Extractor de nivel 2 (Artículos en profundidad)
│   │   ├── snapshot_service.py   # Persistencia y cálculo Delta de rotación de noticias
│   │   ├── ollama_analyzer.py    # Cliente asíncrono Ollama (JSON mode, evolución temporal)
│   │   ├── chart_generator.py    # Generador de gráficos con Matplotlib (PNG)
│   │   ├── excel_reporter.py     # Generador de libros Excel (.xlsx) con tablas y gráficos
│   │   └── word_reporter.py      # Generador de informes Word (.docx) formales corporativos
│   ├── utils/
│   │   └── utils.py              # Limpieza de DOM, auto-scroll y Markdown
│   └── main.py                   # Instancia FastAPI central, CORS, Lifespan y DB Init
├── docs/
│   ├── EJEMPLOS.md               # Ejemplos de payloads y respuestas JSON
│   └── QUICK_START.md            # Esta guía
├── reports/                      # Almacenamiento de reportes generados (.xlsx, .docx)
├── scripts/                      # Scripts de ejecución (Windows / Linux)
├── tests/                        # Suite de pruebas unitarias automatizadas
├── Dockerfile                    # Configuración de contenedor Docker
├── docker-compose.yml            # Orquestación de servicios (Backend + PostgreSQL + Ollama)
├── init.sql                      # Inicializador de esquemas de BD con JSONB e índices
├── requirements.txt              # Dependencias Python actualizadas
├── run_local.py                  # Script de inicio rápido local
└── .env                          # Variables de entorno locales
```

---

## 🧪 Ejecución de Pruebas Unitarias

El proyecto cuenta con una suite oficial de **19 pruebas unitarias automatizadas** que validan la seguridad JWT, los esquemas de entrada, el motor de detección de cambios (Delta), la tolerancia a fallos del scraper y la integridad de los reportes.

Para ejecutarlas en cualquier terminal (Windows, Linux o macOS):

```bash
python -m unittest discover tests -v
```

