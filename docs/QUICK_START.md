# 🚀 Inicio Rápido - Web Scraper API (Backend)

Este repositorio contiene exclusivamente el **Backend (API REST con FastAPI y Playwright)**. El Frontend se ejecuta en su propio repositorio independiente.

---

## ⚡ Formas de Iniciar el Backend

### Opción 1: Scripts Automáticos

#### En Windows
```cmd
scripts\iniciar.bat
```
*(o `scrips\iniciar.bat`)*

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

---

## 📁 Estructura del Repositorio Backend

```
Backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       └── endpoint.py       # Endpoints REST (Scrape Index, Deep, Full Pipeline)
│   ├── core/
│   │   └── config.py             # Parámetros del navegador, timeouts y viewport
│   ├── services/
│   │   ├── scraper.py            # Extractor de nivel 1 (Índices y portadas)
│   │   └── deep_scraper.py       # Extractor de nivel 2 (Artículos en profundidad)
│   ├── utils/
│   │   └── utils.py              # Limpieza de DOM, auto-scroll y Markdown
│   └── main.py                   # Instancia FastAPI central, CORS y Lifespan
├── docs/
│   ├── EJEMPLOS.md               # Ejemplos de payloads y respuestas JSON
│   └── QUICK_START.md            # Esta guía
├── scripts/                      # Scripts de ejecución (Windows / Linux)
├── Dockerfile                    # Configuración de contenedor Docker
├── docker-compose.yml            # Orquestación de servicios
├── requirements.txt              # Dependencias Python
└── run_local.py                  # Script de inicio rápido local
```
