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
