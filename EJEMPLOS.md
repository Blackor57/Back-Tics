<!-- Ejemplos de uso del Frontend -->

# 📌 Ejemplos de Uso - Web Scraper Frontend

## 🌐 Sitios Recomendados para Probar

Aquí hay algunos sitios que funcionan bien con el scraper:

### Noticias
- **RPP Noticias**: https://rpp.pe/
- **BBC**: https://www.bbc.com/
- **CNN**: https://www.cnn.com/
- **The Guardian**: https://www.theguardian.com/

### Blogs
- **Medium**: https://medium.com/
- **Dev.to**: https://dev.to/
- **Hacker News**: https://news.ycombinator.com/

### Tiendas
- **Amazon**: https://www.amazon.com/
- **eBay**: https://www.ebay.com/

---

## 📝 Ejemplos Paso a Paso

### Ejemplo 1: Extraer Índice de RPP Noticias

**Objetivo:** Obtener la lista de noticias principales de la portada

1. Abre el frontend en `http://localhost:8080`
2. La pestaña "Extraer Índice" debería estar activa
3. En el campo "URL", ingresa:
   ```
   https://rpp.pe/
   ```
4. Haz clic en "Extraer"

**Resultado esperado:**
- Verás el título del sitio: "RPP Noticias"
- Tipo de contenido: "lista_entidades"
- Un JSON con la lista de artículos encontrados

---

### Ejemplo 2: Deep Scraping de un Artículo

**Objetivo:** Extraer el contenido completo de un artículo

1. Selecciona la pestaña "Deep Scraping"
2. En el primer campo URL, ingresa un artículo, ej:
   ```
   https://rpp.pe/peru/actualidad/sismo-en-peru-igp-reporto-temblor-noticia-1500000
   ```
3. (Opcional) Agrega más URLs con "+ Agregar URL"
4. Haz clic en "Procesar"

**Resultado esperado:**
- El contenido del artículo en formato Markdown
- Cantidad de caracteres extraídos
- URL y título del artículo

---

### Ejemplo 3: Pipeline Completo

**Objetivo:** Extraer automáticamente la portada y hacer deep scraping de los 3 artículos principales

1. Selecciona la pestaña "Pipeline Completo"
2. Ingresa:
   - URL: `https://rpp.pe/`
   - Límite: `3`
3. Haz clic en "Ejecutar"

**Resultado esperado:**
- Mensaje de progreso
- Lista de 3 artículos con contenido completo
- Estadísticas de procesamiento

---

## 🔍 Testing Avanzado

### Probar con URLs Fallidas

Para verificar el manejo de errores:

```
https://esta-url-no-existe-12345.com/
```

**Resultado esperado:** 
- Error amigable indicando que la URL no es válida o no es alcanzable

### URLs Mal Formateadas

Intenta sin protocolo:
```
rpp.pe/
```

**Resultado esperado:**
- Validación rechaza la URL
- Mensaje: "Por favor ingresa una URL válida"

---

## 📊 Ejemplos de Respuestas

### Response: Extraer Índice

```json
{
  "url": "https://rpp.pe/",
  "site_title": "RPP Noticias",
  "tipo_contenido": "lista_entidades",
  "total_items": 25,
  "data": [
    {
      "titulo": "Sismo en Perú",
      "url": "https://rpp.pe/peru/...",
      "fecha": "2024-01-15"
    }
  ]
}
```

### Response: Deep Scraping

```json
{
  "total_procesados": 1,
  "articulos": [
    {
      "url": "https://rpp.pe/peru/...",
      "titulo_detalle": "Sismo de magnitud 5.2 en Perú",
      "contenido_markdown": "# Sismo de magnitud 5.2\n\nLa ciudad de Lima fue afectada...",
      "caracteres": 5432
    }
  ]
}
```

### Response: Pipeline Completo

```json
{
  "url_origen": "https://rpp.pe/",
  "sitio_titulo": "RPP Noticias",
  "total_indexados": 25,
  "total_procesados_profundidad": 5,
  "articulos": [
    {
      "url": "https://...",
      "titulo_detalle": "Título del artículo",
      "contenido_markdown": "# Contenido...",
      "caracteres": 5432
    }
  ]
}
```

---

## ⚙️ Configuración para Testing

### Cambiar timeouts

En `frontend/app.js`, modifica:
```javascript
const TIMEOUT = 60000; // 60 segundos
```

### Cambiar la URL base de la API

En `frontend/app.js`:
```javascript
const API_BASE_URL = 'http://tu-servidor.com:8000';
```

### Habilitar logs detallados

En la consola del navegador (F12), ejecuta:
```javascript
localStorage.debug = 'app:*'
```

---

## 🐛 Debugging

### Abrir herramientas de desarrollo

- **Windows/Linux**: Presiona `F12`
- **macOS**: Presiona `Cmd + Option + I`

### Ver logs de la API

En la terminal donde ejecutas `uvicorn`:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     POST /api/v1/scrape/index HTTP/1.1" 200 OK
```

### Ver network requests

1. Abre DevTools (F12)
2. Vete a la pestaña "Network"
3. Realiza una operación
4. Verás las peticiones POST a `/api/v1/...`

---

## 📌 Tips Importantes

✅ **Usa sitios confiables y legales** para probar
✅ **Respeta robots.txt** de los sitios
✅ **No hagas scraping masivo** sin autorización
✅ **Prueba primero con "Extraer Índice"** antes de deep scraping
✅ **Ajusta los timeouts** si trabajas con sitios lentos

---

## 🚀 Performance

### Tiempos esperados

| Operación | Tiempo | Factores |
|-----------|--------|----------|
| Extraer Índice | 5-15s | Tamaño de página, velocidad de red |
| Deep Scraping | 10-30s | Número de artículos, conexión |
| Pipeline Completo | 30-60s | Límite de artículos, servidor |

### Optimizaciones

1. **Reduce el límite** del pipeline (ej: 3 en lugar de 10)
2. **Usa URLs más simples** (sin parámetros largos)
3. **Ejecuta en horarios de menor carga**
4. **Verifica tu conexión a internet**

---

## ❌ Errores Comunes

### "Desconectado"
**Causa:** API no está ejecutándose
**Solución:** Ejecuta `python -m uvicorn api:app --reload`

### "Error de CORS"
**Causa:** API sin CORS habilitado
**Solución:** Verifica que `api.py` tiene `CORSMiddleware`

### "Timeout"
**Causa:** La página tarda mucho en cargar
**Solución:** Aumenta `PAGE_TIMEOUT_MS` en `config.py`

### "Sin resultados"
**Causa:** La estructura de la página cambió
**Solución:** Prueba con otro sitio, o revisa los logs

---

## 📚 Recursos Adicionales

- Documentación API: http://localhost:8000/docs
- Frontend README: [frontend/README.md](../frontend/README.md)
- Documentación FastAPI: https://fastapi.tiangolo.com/
- Documentación Beautiful Soup: https://www.crummy.com/software/BeautifulSoup/

---

**¡Listo para experimentar! 🎯**
