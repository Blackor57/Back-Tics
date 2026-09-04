# 📌 Ejemplos de Uso de la API - Web Scraper Backend

Este documento detalla los endpoints REST disponibles en la API para ser consumidos por cualquier cliente frontend o herramienta de pruebas (Postman, cURL, Fetch API, Axios).

---

## 🚀 Endpoints de la API

### 1. Extraer Índice (`POST /api/v1/scrape/index`)

Extrae la lista de novedades/artículos encontrados en la portada de un sitio o el texto continuo si es una página individual.

#### Petición (Payload)
```json
{
  "url": "https://rpp.pe/"
}
```

#### Respuesta Ejemplo
```json
{
  "url": "https://rpp.pe/",
  "site_title": "RPP Noticias - Noticias del Perú y el Mundo",
  "tipo_contenido": "lista_entidades",
  "total_items": 15,
  "data": [
    {
      "titulo": "Sismo de magnitud 4.5 se registró en Lima esta madrugada",
      "url": "https://rpp.pe/peru/actualidad/sismo-en-lima-noticia-123456"
    },
    {
      "titulo": "Presidente del Congreso convoca a pleno extraordinario",
      "url": "https://rpp.pe/politica/congreso/pleno-extraordinario-noticia-123457"
    }
  ]
}
```

---

### 2. Deep Scraping (`POST /api/v1/scrape/deep`)

Extrae el contenido textual y estructurado en Markdown limpio de una lista específica de URLs de artículos.

#### Petición (Payload)
```json
{
  "items": [
    {
      "titulo": "Título de referencia (opcional)",
      "url": "https://rpp.pe/peru/actualidad/sismo-en-lima-noticia-123456"
    }
  ]
}
```

#### Respuesta Ejemplo
```json
{
  "total_procesados": 1,
  "articulos": [
    {
      "url": "https://rpp.pe/peru/actualidad/sismo-en-lima-noticia-123456",
      "titulo": "Título de referencia (opcional)",
      "titulo_detalle": "Sismo de magnitud 4.5 se registró en Lima esta madrugada",
      "contenido_markdown": "# Sismo de magnitud 4.5 en Lima\n\nUn movimiento telúrico de magnitud 4.5 se sintió...",
      "caracteres": 1420,
      "error": null
    }
  ]
}
```

---

### 3. Pipeline Completo (`POST /api/v1/scrape/full-pipeline`)

Combina Nivel 1 y Nivel 2: escanea la portada y automáticamente extrae el contenido completo de los primeros $N$ artículos (indicados por `limit`, por defecto 5).

#### Petición (Payload)
```json
{
  "url": "https://rpp.pe/",
  "limit": 3
}
```

#### Respuesta Ejemplo
```json
{
  "url_origen": "https://rpp.pe/",
  "sitio_titulo": "RPP Noticias",
  "total_indexados": 15,
  "total_procesados_profundidad": 3,
  "articulos": [
    {
      "titulo": "Sismo en Lima",
      "url": "https://rpp.pe/peru/actualidad/sismo-en-lima-noticia-123456",
      "titulo_detalle": "Sismo de magnitud 4.5 se registró en Lima",
      "contenido_markdown": "# Contenido completo extraído...",
      "caracteres": 1420,
      "error": null
    }
  ]
}
```

---

## 💻 Ejemplos de Integración desde el Frontend (JavaScript / TypeScript)

### Ejemplo con Fetch API:
```javascript
const API_BASE = 'http://localhost:8000';

async function obtenerIndice(urlObjetivo) {
  try {
    const response = await fetch(`${API_BASE}/api/v1/scrape/index`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ url: urlObjetivo }),
    });

    if (!response.ok) {
      throw new Error(`Error HTTP: ${response.status}`);
    }

    const data = await response.json();
    console.log('Resultados del índice:', data);
    return data;
  } catch (error) {
    console.error('Error al conectar con la API:', error);
  }
}
```

---

## 🧠 Inteligencia con Ollama, Comparativa Histórica y Reportes

### 4. Análisis Inteligente con Reportes (`POST /api/v1/intelligence/analyze`)

Scrapea la página, busca en **PostgreSQL** la versión inmediatamente anterior de esa URL, calcula el **Delta diferencial** (nuevas vs. salientes), ejecuta el análisis semántico con el LLM local en **Ollama** (`llama3.1:latest`), genera gráficos con **Matplotlib** e informes descargables en **Excel** y **Word**.

#### Petición (Payload)
```json
{
  "url": "https://rpp.pe/",
  "guardar_snapshot": true,
  "generar_documentos": true
}
```

#### Respuesta Ejemplo
```json
{
  "url": "https://rpp.pe/",
  "sitio_titulo": "RPP Noticias",
  "snapshot_id": 14,
  "snapshot_anterior_id": 13,
  "es_linea_base": false,
  "total_items": 18,
  "analisis_ia": {
    "resumen_ejecutivo": "La jornada informativa está dominada por el debate presupuestal en el Congreso...",
    "analisis_evolucion": "Se observa un recambio del 35% en las noticias de portada respecto a la versión anterior...",
    "categorias": [
      {"nombre": "Política", "cantidad": 7, "porcentaje": 39},
      {"nombre": "Economía", "cantidad": 5, "porcentaje": 28},
      {"nombre": "Seguridad", "cantidad": 4, "porcentaje": 22},
      {"nombre": "Sociedad", "cantidad": 2, "porcentaje": 11}
    ],
    "sentimientos": {
      "positivo": 3,
      "neutro": 10,
      "negativo": 5
    },
    "entidades_clave": ["Congreso", "Ministerio de Economía", "Poder Judicial"],
    "conclusiones": [
      "Fuerte concentración en reformas legislativas.",
      "Disminución de noticias del sector minero respecto a la semana previa."
    ]
  },
  "delta": {
    "es_lista": true,
    "total_anteriores": 16,
    "total_actuales": 18,
    "total_nuevos": 6,
    "total_salientes": 4,
    "total_mantenidos": 12,
    "tasa_rotacion_pct": 33.3,
    "nuevos_articulos": [
      {"titulo": "Nueva ley de telecomunicaciones entra en vigencia", "url": "https://rpp.pe/..."}
    ],
    "articulos_salientes": [
      {"titulo": "Alerta por lluvias en la sierra central", "url": "https://rpp.pe/..."}
    ]
  },
  "descargas": {
    "excel": "/api/v1/reports/download/excel/5",
    "word": "/api/v1/reports/download/word/5"
  },
  "created_at": "2026-09-03T20:00:00.000000"
}
```

---

### 5. Descargas de Reportes

- **Descargar Excel (.xlsx)**:
  `GET http://localhost:8000/api/v1/reports/download/excel/{report_id}`
- **Descargar Word (.docx)**:
  `GET http://localhost:8000/api/v1/reports/download/word/{report_id}`
- **Listar Historial de Reportes**:
  `GET http://localhost:8000/api/v1/reports/list` (acepta opcionalmente `?solo_mis_reportes=true` si se envía el token JWT)
- **Consultar Snapshots de una URL**:
  `GET http://localhost:8000/api/v1/snapshots/history?url=https://rpp.pe/`

---

### 6. Autenticación y Gestión de Usuarios (JWT)

El sistema soporta modo **anónimo** (sin autenticación) para scraping y análisis puntual, y modo **autenticado** para guardar historial propio y configurar monitoreo temporal de páginas con alertas por correo.

#### A. Registro de Usuario (`POST /api/v1/auth/register`)
```json
{
  "email": "analista@empresa.com",
  "password": "miPasswordSeguro123",
  "nombre_completo": "Juan Pérez"
}
```
**Respuesta:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsIn...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "analista@empresa.com",
    "nombre_completo": "Juan Pérez",
    "is_active": true,
    "is_superuser": false,
    "created_at": "2026-09-03T22:15:00.000000Z"
  }
}
```

#### B. Inicio de Sesión (`POST /api/v1/auth/login`)
```json
{
  "email": "analista@empresa.com",
  "password": "miPasswordSeguro123"
}
```
**Respuesta:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsIn...",
  "token_type": "bearer",
  "user": { ... }
}
```

#### C. Perfil en Sesión (`GET /api/v1/auth/me`)
- **Headers**: `Authorization: Bearer <access_token>`

---

### 7. Monitoreo Continuo y Alertas por Correo (`/api/v1/tracking`)

Permite programar la vigilancia periódica de una web durante **1 a 3 días o hasta 1 mes** (30 días). Si el motor detecta cambios importantes, genera un análisis semántico con Ollama y despacha un correo electrónico al usuario con las novedades.

#### A. Iniciar Seguimiento (`POST /api/v1/tracking/start`)
- **Headers**: `Authorization: Bearer <access_token>`
- **Payload:**
```json
{
  "url": "https://rpp.pe/",
  "dias_duracion": 3,
  "frecuencia_horas": 12,
  "notificar_email": true
}
```
**Respuesta:**
```json
{
  "id": 1,
  "user_id": 1,
  "url": "https://rpp.pe/",
  "dias_duracion": 3,
  "frecuencia_horas": 12,
  "fecha_inicio": "2026-09-03T22:15:00.000000Z",
  "fecha_fin": "2026-09-06T22:15:00.000000Z",
  "activo": true,
  "notificar_email": true,
  "ultimo_chequeo": null,
  "created_at": "2026-09-03T22:15:00.000000Z"
}
```

#### B. Listar Mis Seguimientos (`GET /api/v1/tracking/my-targets`)
- **Headers**: `Authorization: Bearer <access_token>`
- Parámetros opcionales: `?activo=true`

#### C. Pausar o Reactivar Seguimiento (`PATCH /api/v1/tracking/{target_id}/toggle`)
- **Headers**: `Authorization: Bearer <access_token>`

#### D. Eliminar Seguimiento (`DELETE /api/v1/tracking/{target_id}`)
- **Headers**: `Authorization: Bearer <access_token>`


