# README4.md - Módulo RPA integrado: URL → Excel

Documentación completa del módulo de **Automatización RPA (Robotic Process Automation)** de SIMAP: consulta una URL pública, detecta datos estructurados, extrae registros, verifica una muestra contra la página en vivo y genera un archivo Excel descargable con trazabilidad de la fuente.

> **Alcance de este documento:** describe la implementación **integrada** (API FastAPI + panel React). El **bot autónomo** de consola (`Back-Tics/rpa_bot/`) se documenta en `README3.md`, sección 11, y se mantiene como alternativa independiente.

---

## 1. Resumen ejecutivo

| Aspecto | Detalle |
|---|---|
| Objetivo | Convertir una URL pública con datos tabulares o listas en un Excel listo para análisis. |
| Entrada | URL pública + límite de registros + máximo de páginas + verificación opcional. |
| Salida | Archivo `.xlsx` con 3 hojas (datos, metadatos y verificación) + descarga directa. |
| Backend | FastAPI + `httpx.AsyncClient` + `BeautifulSoup` + `openpyxl`. |
| Frontend | React + Vite + Tailwind, componente `RpaExportPanel`. |
| Requisito mínimo | Al menos **10 registros** extraídos; máximo **100**. |
| Páginas | Hasta **5 páginas** por ejecución (por defecto 2). |
| Estado | Funcional y probado contra fuentes reales (RPP, El Comercio, Scrape This Site). |

---

## 2. Dos implementaciones de RPA en el proyecto

| Implementación | Ubicación | Cómo se usa | Documentación |
|---|---|---|---|
| **RPA integrado** | `app/api/v1/rpa.py` + `app/services/rpa_service.py` + panel React | Desde la interfaz web o por API REST. Genera el Excel en `reports/rpa/` y lo sirve por HTTP. | Este documento. |
| **Bot autónomo** | `rpa_bot/bot_extraccion.py` | Script de consola sin backend ni navegador. Guarda en `rpa_bot/salidas/`. | `README3.md`, sección 11. |

Ambas comparten la misma idea (HTTP + BeautifulSoup + openpyxl), pero no comparten código. El módulo integrado está pensado para la plataforma; el bot autónomo para ejecuciones programadas aisladas.

---

## 3. Arquitectura

```mermaid
flowchart LR
    U[Usuario] -->|URL| UI[React RpaExportPanel]
    UI -->|POST /api/v1/rpa/extract| API[FastAPI rpa.py]
    API --> SVC[rpa_service.py]
    SVC -->|HTTP GET| WEB[Sitio público]
    SVC -->|BeautifulSoup| DET[Detección: tabla / lista / enlaces]
    DET --> PAG[Paginación y deduplicación]
    PAG --> VER[Verificación de muestra]
    VER --> XLS[openpyxl: 3 hojas]
    XLS --> FS[(reports/rpa/*.xlsx)]
    API -->|JSON con URL de descarga| UI
    UI -->|GET /api/v1/rpa/download/{archivo}| API
    API -->|FileResponse .xlsx| Usuario
```

### Archivos implicados

| Archivo | Rol |
|---|---|
| `Back-Tics/app/api/v1/rpa.py` | Endpoints REST, validación del request y descarga segura. |
| `Back-Tics/app/services/rpa_service.py` | Motor RPA: consulta, parsing, paginación, verificación y Excel. |
| `Back-Tics/app/main.py` | Registra el router RPA en `/api/v1`. |
| `Back-Tics/app/core/config.py` | Define `REPORTS_DIR` (carpeta de salida). |
| `Back-Tics/requirements.txt` | Dependencias: `httpx`, `beautifulsoup4`, `openpyxl`. |
| `Front-Tics/src/services/api.js` | Cliente `rpaAPI.extract` y `rpaAPI.getDownloadUrl`. |
| `Front-Tics/src/components/analyzer/RpaExportPanel.jsx` | Panel de UI: estados, vista previa y botones. |
| `Front-Tics/src/App.jsx` | Estado y handlers `handleRpaExtract` / `handleRpaDemo`. |
| `Front-Tics/src/components/analyzer/UrlInputSection.jsx` | Presets de URL, incluido el demo de hockey. |

---

## 4. Flujo de funcionamiento

### 4.1. Frontend

1. El usuario pega una URL en el panel del analizador.
2. Pulsa **«Generar Excel RPA»** (o **«Regenerar Excel»** si ya existe un resultado).
3. `handleRpaExtract` valida que la URL no esté vacía y llama a `rpaAPI.extract`.
4. Mientras espera, el panel muestra el estado de carga y deshabilita el botón.
5. Al terminar:
   - Muestra KPIs: registros, páginas, tipo de contenido y coincidencias.
   - Muestra un mensaje de verificación (verde si no hay diferencias, ámbar si hay avisos).
   - Muestra una vista previa de la muestra (primeros 5 registros).
   - Habilita **«Descargar Excel»** y **«Regenerar Excel»**.
6. Si la URL cambia después de generar, aparece un aviso ámbar indicando que el Excel corresponde a la URL anterior.
7. El botón **«Probar con sitio demo de hockey»** fija `https://www.scrapethissite.com/pages/forms/` y ejecuta la extracción.

### 4.2. Backend

1. Valida el cuerpo con Pydantic (`HttpUrl`, `limite` 10-100, `max_paginas` 1-5, `verificar` booleano).
2. Realiza `GET` con cabeceras de navegador, redirecciones, timeout de 25 s y **reintentos con retroceso exponencial** para 429/5xx y errores de red.
3. Verifica que el `Content-Type` sea HTML/XML (si viene informado).
4. Parsea el HTML con `BeautifulSoup` y aplica tres estrategias en orden de preferencia:
   - **Tabla:** busca la tabla con mayor puntuación (`filas × columnas`).
   - **Lista:** busca contenedores tipo `article`, `card`, `item`, `result`, `noticia`, `news` o `li`.
   - **Enlaces:** último recurso; recoge enlaces con texto significativo.
5. Exige un mínimo de 10 registros; si no se alcanza, responde con un error explicativo.
6. Recorre páginas adicionales cuando hace falta:
   - Primero intenta el enlace de «siguiente».
   - Si no hay avance, prueba a incrementar un parámetro de paginación (`page`, `pagina`, `p`, `page_num`, etc.).
   - Aplica una pausa de 0.35 s entre páginas y deduplica registros.
7. Verifica una muestra de hasta 5 registros reconsultando las páginas de origen y comparando campo por campo.
8. Genera el Excel con `openpyxl` en `reports/rpa/rpa_<10 hex>.xlsx`.
9. Devuelve un JSON con metadatos, muestra, resumen de verificación y la ruta de descarga.

### 4.3. Detección de contenido

| Tipo | Criterio | Columnas generadas |
|---|---|---|
| `tabla` | Tabla con al menos 3 filas y 2 columnas. Usa encabezados de `thead` o de la primera fila con `th`. | Encabezados reales de la tabla. |
| `lista` | Al menos 3 contenedores repetidos con título de 12+ caracteres. | `Título`, `Enlace`, y opcionalmente `Fecha` y `Resumen`. |
| `enlaces` | Al menos 3 enlaces con texto de 15+ caracteres. | `Título`, `Enlace`. |

Si ningún candidato alcanza 10 registros, se elige el de mayor cantidad y luego se aplica la validación mínima (que puede rechazar la extracción).

### 4.4. Deduplicación

- **Tabla:** clave compuesta por todos los campos del registro.
- **Lista:** `título + enlace`.
- **Enlaces:** la URL.

La deduplicación se aplica al fusionar páginas para evitar filas repetidas.

### 4.5. Verificación de muestra

1. Selecciona hasta 5 registros distribuidos a lo largo del resultado.
2. Reconsulta las páginas de origen.
3. Compara los campos relevantes:
   - Tabla: todas las columnas.
   - Lista/Enlaces: `Título`, `Enlace` y `Fecha`.
4. Clasifica cada comparación como:
   - **Coincide:** el valor del Excel es igual al de la página.
   - **No coincide:** el valor cambió o el registro ya no está.
   - **No verificable:** no se pudo recargar la página de origen.
5. Resume: registros verificados, campos comparados, coincidencias, diferencias y no verificables.

### 4.6. Excel y descarga

El archivo se guarda en `Back-Tics/reports/rpa/`. El endpoint de descarga valida el nombre con la expresión regular `^rpa_[a-f0-9]{10}\.xlsx$`, evita rutas arbitrarias y responde como `FileResponse` con `Cache-Control: no-store`.

---

## 5. API REST

Prefijo efectivo: `/api/v1/rpa` (router con prefijo `/rpa` incluido bajo `/api/v1`).

### 5.1. `POST /api/v1/rpa/extract`

Ejecuta la extracción y genera el Excel.

**Cuerpo de la petición**

| Campo | Tipo | Obligatorio | Por defecto | Restricciones |
|---|---|---|---|---|
| `url` | string (URL HTTP/HTTPS) | Sí | — | Debe ser una URL válida y pública. |
| `limite` | integer | No | `40` | `10 <= limite <= 100` |
| `max_paginas` | integer | No | `2` | `1 <= max_paginas <= 5` |
| `verificar` | boolean | No | `true` | Activa/desactiva la verificación de muestra. |

**Ejemplo de petición**

```json
{
  "url": "https://www.scrapethissite.com/pages/forms/",
  "limite": 40,
  "max_paginas": 2,
  "verificar": true
}
```

**Ejemplo de respuesta (200 OK)**

```json
{
  "archivo": "rpa_8c5fe3b462.xlsx",
  "descargas": {
    "excel": "/api/v1/rpa/download/rpa_8c5fe3b462.xlsx"
  },
  "url": "https://www.scrapethissite.com/pages/forms/",
  "sitio_titulo": "Hockey Teams: Forms, Searching and Pagination | Scrape This Site",
  "tipo_contenido": "tabla",
  "total_registros": 40,
  "total_paginas": 2,
  "paginas": [
    "https://www.scrapethissite.com/pages/forms/",
    "https://www.scrapethissite.com/pages/forms/?page_num=2"
  ],
  "columnas": [
    "Team Name",
    "Year",
    "Wins",
    "Losses",
    "OT Losses",
    "Win %",
    "Goals For (GF)",
    "Goals Against (GA)",
    "+ / -"
  ],
  "muestra": [
    {
      "Team Name": "Boston Bruins",
      "Year": "1990",
      "Wins": "44",
      "Losses": "24",
      "OT Losses": "",
      "Win %": "0.55",
      "Goals For (GF)": "299",
      "Goals Against (GA)": "264",
      "+ / -": "35"
    }
  ],
  "verificacion": {
    "registros_verificados": 5,
    "campos_comparados": 45,
    "coincidencias": 45,
    "diferencias": 0,
    "no_verificables": 0
  },
  "mensaje": "Excel generado con 40 registros de 2 página(s)."
}
```

**Campos de la respuesta**

| Campo | Descripción |
|---|---|
| `archivo` | Nombre del Excel generado. |
| `descargas.excel` | Ruta relativa para descargar el archivo. |
| `url` | URL consultada. |
| `sitio_titulo` | Título de la página. |
| `tipo_contenido` | `tabla`, `lista` o `enlaces`. |
| `total_registros` | Registros incluidos en el Excel. |
| `total_paginas` | Páginas efectivamente consultadas. |
| `paginas` | Lista de URLs consultadas. |
| `columnas` | Nombres de columnas detectadas. |
| `muestra` | Primeros 5 registros en formato de objeto. |
| `verificacion` | Resumen de la comparación contra la página en vivo. |
| `mensaje` | Mensaje legible para el usuario. |

### 5.2. `GET /api/v1/rpa/download/{filename}`

Descarga el Excel generado. Solo acepta nombres con el patrón `rpa_<10 hex>.xlsx`.

- `200 OK`: devuelve el archivo con tipo MIME
  `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`.
- `400 Bad Request`: nombre de archivo inválido.
- `404 Not Found`: el archivo no existe o expiró.

### 5.3. Códigos de estado y errores

| Código | Situación | Mensaje típico |
|---|---|---|
| `200` | Extracción correcta. | — |
| `400` | Nombre de archivo de descarga inválido. | `Nombre de archivo RPA inválido.` |
| `404` | Archivo inexistente en la descarga. | `El archivo RPA no existe o expiró.` |
| `422` | URL inexistente (404 del sitio). | `La URL respondió 404 (página no encontrada)...` |
| `422` | Sitio que bloquea bots (401/403). | `El sitio bloqueó la consulta automatizada (HTTP 403)...` |
| `422` | Contenido no HTML. | `La URL no devolvió una página HTML compatible...` |
| `422` | Sin datos detectados. | `No se detectaron tablas ni listas de datos...` |
| `422` | Menos de 10 registros. | `Solo se encontraron X registros...` |
| `422` | Timeout o error de red. | `La página tardó demasiado en responder...` |
| `500` | Error inesperado del servidor. | `No se pudo completar la extracción RPA...` |

---

## 6. Estructura del archivo Excel

El libro generado contiene tres hojas.

### 6.1. Hoja `Datos Extraídos`

- Fila 1: encabezados con fondo azul, texto blanco y bordes.
- Primera columna `N°` con numeración correlativa.
- Columnas dinámicas según el tipo detectado.
- Columnas finales:
  - `Fuente (URL)`: hipervínculo a la página de origen de cada fila.
  - `Fecha de extracción`: fecha y hora exactas de la ejecución.
- Panel congelado en `A2`, autofiltro, filas alternadas y bordes.

Ejemplo para una tabla:

| N° | Team Name | Year | Wins | Losses | OT Losses | Win % | GF | GA | + / - | Fuente (URL) | Fecha de extracción |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Boston Bruins | 1990 | 44 | 24 | | 0.55 | 299 | 264 | 35 | https://... | 2026-11-05 00:58:13 |

Ejemplo para una lista:

| N° | Título | Enlace | Fuente (URL) | Fecha de extracción |
|---|---|---|---|---|
| 1 | Título de la noticia | https://... | https://... | 2026-11-05 00:58:13 |

### 6.2. Hoja `Fuente y Metadatos`

Registra la trazabilidad del proceso:

| Campo | Contenido |
|---|---|
| Reporte | Extracción automática de datos públicos a Excel |
| Sitio consultado | Título de la página |
| Fuente de consulta | URL analizada |
| Páginas consultadas | URLs de todas las páginas recorridas |
| Tipo de contenido detectado | `tabla`, `lista` o `enlaces` |
| Total de registros | Cantidad incluida en el Excel |
| Límite solicitado | Valor de `limite` |
| Fecha de generación | Fecha y hora |
| Motor RPA | `Back-Tics/app/services/rpa_service.py v1.0.0` |
| Verificación de muestra | Registros, campos, coincidencias, diferencias y no verificables |
| Nota | Solo datos públicos, pausas entre páginas y URL de origen por fila |

### 6.3. Hoja `Verificación de Muestra`

Comparación campo por campo:

| Clave | Campo | Valor en Excel | Valor en la página | Resultado |
|---|---|---|---|---|
| Boston Bruins 1990... | Team Name | Boston Bruins | Boston Bruins | Coincide |

Colores de la columna `Resultado`:

- Verde: `Coincide`.
- Rojo: `No coincide`.
- Ámbar: `No verificable`.

---

## 7. Frontend

### 7.1. Componente `RpaExportPanel`

Props:

| Prop | Tipo | Descripción |
|---|---|---|
| `url` | string | URL actual del analizador. |
| `result` | object/null | Respuesta de la última extracción. |
| `isLoading` | boolean | Extracción en curso. |
| `error` | string | Mensaje de error legible. |
| `onExtract` | function | Ejecuta la extracción con la URL actual. |
| `onUseDemo` | function | Carga y ejecuta el demo de hockey. |

Estados de la interfaz:

| Estado | Elementos visibles |
|---|---|
| Sin resultado | Botón **«Generar Excel RPA»** + ayudas + botón de demo. |
| Cargando | Botón deshabilitado con spinner + mensaje de progreso. |
| Error | Banda roja con el detalle del backend + botón para reintentar. |
| Resultado | KPIs, verificación, vista previa de muestra, **«Descargar Excel»** y **«Regenerar Excel»**. |
| URL cambiada | Aviso ámbar que recuerda regenerar el Excel para la URL actual. |

### 7.2. Cliente API

```js
// Front-Tics/src/services/api.js
export const rpaAPI = {
  extract: async ({ url, limite = 40, max_paginas = 2, verificar = true }) => {
    const response = await api.post(
      '/api/v1/rpa/extract',
      { url, limite, max_paginas, verificar },
      { timeout: 180000 }
    );
    return response.data;
  },
  getDownloadUrl: (pathOrUrl) => {
    if (!pathOrUrl) return null;
    if (/^https?:\/\//i.test(pathOrUrl)) return pathOrUrl;
    return `${API_BASE_URL}${pathOrUrl.startsWith('/') ? '' : '/'}${pathOrUrl}`;
  },
};
```

---

## 8. Requisitos e instalación

### Backend

- Python 3.10 o superior (probado con 3.14).
- Dependencias del proyecto:

```powershell
cd Back-Tics
pip install -r requirements.txt
```

Dependencias específicas del RPA (ya incluidas):

```text
httpx>=0.27.0
beautifulsoup4>=4.12.0
openpyxl>=3.1.2
```

### Frontend

```powershell
cd Front-Tics
npm install
```

### Nota sobre PostgreSQL

El módulo RPA **no usa base de datos**. Si PostgreSQL no está disponible, el arranque del backend muestra una advertencia pero el endpoint RPA sigue funcionando. El RPA no requiere JWT ni sesión de usuario.

---

## 9. Cómo probarlo

### 9.1. Arrancar el backend

```powershell
cd D:\Escritorio\SIMAP\SIMAP\Back-Tics
python run_local.py
```

Alternativa directa:

```powershell
cd D:\Escritorio\SIMAP\SIMAP\Back-Tics
python -m uvicorn app.main:app --reload --port 8000
```

Verificar que está arriba:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

Documentación interactiva: `http://localhost:8000/docs`.

### 9.2. Arrancar el frontend

```powershell
cd D:\Escritorio\SIMAP\SIMAP\Front-Tics
npm run dev
```

Abrir `http://localhost:5173`.

### 9.3. Prueba desde la interfaz

1. Ir a la pestaña del analizador (inicio).
2. Verificar que la URL sea `https://rpp.pe/actualidad` o pulsar el preset **«Demo RPA · Hockey»**.
3. En el panel **«Automatización RPA · URL a Excel»**, pulsar **«Generar Excel RPA»**.
4. Esperar el estado de carga.
5. Revisar los KPIs, la verificación y la vista previa.
6. Pulsar **«Descargar Excel»** y abrir el archivo.
7. Verificar las tres hojas: `Datos Extraídos`, `Fuente y Metadatos`, `Verificación de Muestra`.
8. Cambiar la URL y comprobar el aviso ámbar; pulsar **«Regenerar Excel»** para extraer la nueva URL.

### 9.4. Prueba por API con PowerShell

```powershell
$body = @{
  url         = "https://www.scrapethissite.com/pages/forms/"
  limite      = 40
  max_paginas = 2
  verificar   = $true
} | ConvertTo-Json

$res = Invoke-RestMethod `
  -Uri "http://localhost:8000/api/v1/rpa/extract" `
  -Method Post `
  -Body $body `
  -ContentType "application/json"

$res | ConvertTo-Json -Depth 6
Start-Process "http://localhost:8000$($res.descargas.excel)"
```

### 9.5. Prueba por API con curl

```bash
curl -X POST "http://localhost:8000/api/v1/rpa/extract" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.scrapethissite.com/pages/forms/","limite":40,"max_paginas":2,"verificar":true}'
```

En Windows usar `curl.exe` si `curl` apunta a un alias de PowerShell.

### 9.6. Prueba directa del motor (sin servidor)

```powershell
cd D:\Escritorio\SIMAP\SIMAP\Back-Tics
@'
import asyncio
from app.services.rpa_service import extraer_y_exportar

async def main():
    r = await extraer_y_exportar(
        "https://www.scrapethissite.com/pages/forms/",
        limite=40,
        max_paginas=2,
        verificar=True,
    )
    print("Archivo:", r["archivo"])
    print("Registros:", r["total_registros"])
    print("Verificación:", r["verificacion"])

asyncio.run(main())
'@ | python -
```

### 9.7. Prueba del bot autónomo (alternativa)

```powershell
cd D:\Escritorio\SIMAP\SIMAP\Back-Tics
pip install -r rpa_bot\requirements.txt
python rpa_bot\bot_extraccion.py
python rpa_bot\verificar_reporte.py
```

Genera/valida `rpa_bot/salidas/datos_extraidos.xlsx`. Ver `README3.md`, sección 11.

### 9.8. Casos de prueba recomendados

| Caso | Entrada | Resultado esperado |
|---|---|---|
| Tabla con paginación | `https://www.scrapethissite.com/pages/forms/` | 40 registros, 2 páginas, verificación sin diferencias. |
| Lista de noticias | `https://rpp.pe/actualidad` | Detección tipo `lista`, 40 registros, verificación correcta. |
| Portal de economía | `https://elcomercio.pe/economia` | Detección tipo `lista`, 40 registros. |
| URL inexistente | `https://rpp.pe/politica-y-economia` | HTTP 422 con mensaje de 404 amigable. |
| Límite inválido | `limite = 5` | HTTP 422 por validación de Pydantic. |
| Regeneración | Generar, cambiar URL, regenerar | Nuevo Excel y aviso de URL actualizado. |
| Descarga inválida | `/api/v1/rpa/download/otro.xlsx` | HTTP 400 por nombre inválido. |

---

## 10. Correcciones y mejoras aplicadas (noviembre 2026)

| Problema detectado | Causa | Corrección |
|---|---|---|
| El panel no ejecutaba nada | `RpaExportPanel` estaba importado pero no renderizado y sin handlers. | Se renderizó en la pestaña del analizador y se añadieron `handleRpaExtract` y `handleRpaDemo`. |
| El botón de RPA fallaba con la URL por defecto | `https://rpp.pe/politica-y-economia` devuelve 404. | Se cambió el valor por defecto y los presets a `https://rpp.pe/actualidad`. |
| No se podía extraer dos veces | Al haber resultado, el botón se convertía solo en descarga. | Se añadió **«Regenerar Excel»** junto a **«Descargar Excel»**. |
| Resultado obsoleto al cambiar de URL | El panel no avisaba. | Aviso ámbar cuando `result.url` no coincide con la URL actual. |
| Errores HTTP poco claros | Todo se reportaba como «No se pudo consultar». | Mensajes específicos para 404, 401/403, timeout, contenido no HTML y errores de red. |
| Sin reintentos ante fallos transitorios | `_consultar` hacía una sola petición. | Reintentos con retroceso exponencial para 429/5xx y errores de red. |
| Verificación con falsos negativos | Se mezclaban tipos de detección y se penalizaba una recarga fallida. | Se usa el tipo original, se marcan campos «No verificable» y se excluyen de las diferencias. |
| Encabezados de tabla mal detectados | Filas de `thead` podían tratarse como datos. | Se excluyen las filas del `thead` al recolectar el cuerpo. |
| Celdas de verificación en rojo para casos no concluyentes | Solo existían verde/rojo. | Se añadió ámbar para «No verificable». |

---

## 11. Solución de problemas

| Síntoma | Causa probable | Solución |
|---|---|---|
| `No se pudo completar la extracción RPA` | Backend caído o CORS. | Verificar `http://localhost:8000/health` y que el frontend apunte a esa URL. |
| `La URL respondió 404` | Dirección inexistente o cambió. | Usar una URL válida (p. ej. el demo de hockey). |
| `El sitio bloqueó la consulta automatizada` | Protección anti-bot, login o captcha. | Probar otra fuente pública; este modo no resuelve captchas ni sesiones. |
| `No se detectaron tablas ni listas` | Contenido generado por JavaScript. | Usar una página con datos en el HTML o el flujo de análisis con Playwright. |
| `Solo se encontraron X registros` | Menos de 10 resultados o paginación no detectada. | Aumentar `max_paginas`, usar otra URL o un listado con más elementos. |
| `La página tardó demasiado` | Timeout de 25 s. | Reintentar o usar una fuente más rápida. |
| El Excel no descarga | Bloqueo de ventanas emergentes. | Permitir ventanas emergentes o abrir la URL de descarga directamente. |
| Acento o carácter extraño en consola | Codificación de la terminal Windows. | El Excel conserva los caracteres correctos; usar `chcp 65001` si se desea. |
| PostgreSQL no conecta | Servicio no iniciado. | Es opcional para RPA; se puede ignorar esa advertencia. |

---

## 12. Seguridad, ética y límites

- **Solo datos públicos:** no se usan credenciales, cookies ni sesiones autenticadas.
- **Sin persistencia de datos sensibles:** solo se guarda el Excel en `reports/rpa/`; no se almacenan HTML ni imágenes.
- **Descarga segura:** el nombre se valida con `^rpa_[a-f0-9]{10}\.xlsx$` para evitar rutas arbitrarias.
- **Límites de cortesía:** pausas entre páginas, límite de páginas/registros y `User-Agent` identificable.
- **Reintentos controlados:** máximo 3 intentos por petición con retroceso exponencial.
- **CORS explícito:** configurado en el backend para el frontend.
- **Sin base de datos:** el módulo no requiere PostgreSQL ni autenticación.

---

## 13. Limitaciones conocidas

- No ejecuta JavaScript: los sitios SPA que cargan datos por API o JS no son compatibles con este modo HTTP+HTML.
- No resuelve captchas, logins, 401/403 ni protecciones anti-bot.
- La detección de listas es heurística: en portales de noticias puede elegir enlaces de navegación si no hay contenedores de artículo claros.
- Requiere un mínimo de 10 registros para considerar la extracción válida.
- La paginación se apoya en enlaces «siguiente» o parámetros de página; estructuras atípicas pueden no recorrerse completas.
- Los archivos generados permanecen en `reports/rpa/`; conviene limpiarlos periódicamente.

Limpieza manual sugerida (PowerShell):

```powershell
Get-ChildItem D:\Escritorio\SIMAP\SIMAP\Back-Tics\reports\rpa\*.xlsx |
  Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-7) } |
  Remove-Item
```

---

## 14. Roadmap

| Mejora | Descripción |
|---|---|
| Detección con Playwright | Fallback para sitios con contenido dinámico. |
| Selectores configurables | Permitir indicar tabla/columnas manualmente desde la UI. |
| Exportación CSV/JSON | Añadir formatos además de Excel. |
| Historial de extracciones | Persistir metadatos y permitir re-descargas. |
| Programación periódica | Reutilizar el scheduler de monitoreo para extracciones RPA. |
| Limpieza automática | Purgar archivos antiguos de `reports/rpa/`. |
| Pruebas automatizadas | Tests unitarios de parsing, paginación y verificación. |

---

## 15. Evidencias y archivos generados

| Evidencia | Ubicación |
|---|---|
| Endpoints RPA | `Back-Tics/app/api/v1/rpa.py` |
| Motor RPA | `Back-Tics/app/services/rpa_service.py` |
| Cliente API frontend | `Front-Tics/src/services/api.js` |
| Panel frontend | `Front-Tics/src/components/analyzer/RpaExportPanel.jsx` |
| Integración en la app | `Front-Tics/src/App.jsx` |
| Excels integrados | `Back-Tics/reports/rpa/rpa_*.xlsx` |
| Bot autónomo | `Back-Tics/rpa_bot/bot_extraccion.py` |
| Excel del bot autónomo | `Back-Tics/rpa_bot/salidas/datos_extraidos.xlsx` |
| Documentación del bot autónomo | `Back-Tics/README3.md`, sección 11 |

---

## 16. Checklist de validación

- [x] El backend arranca y expone `POST /api/v1/rpa/extract`.
- [x] La extracción de tabla paginada devuelve 40 registros de 2 páginas.
- [x] La extracción de listas devuelve 40 registros.
- [x] La verificación compara campos y reporta coincidencias.
- [x] El Excel contiene las 3 hojas y enlaces de fuente.
- [x] La descarga devuelve el archivo con el MIME correcto.
- [x] Una URL 404 devuelve un mensaje claro (HTTP 422).
- [x] Un límite inválido es rechazado por validación (HTTP 422).
- [x] El panel permite generar, regenerar y descargar.
- [x] El aviso de URL cambiada aparece al editar la URL.
- [x] El build del frontend compila sin errores.

---

## 17. Changelog

### v1.1.0 - Noviembre 2026

- Integración completa del panel RPA en el frontend (render, handlers, estados).
- Corrección de la URL por defecto y presets (404 de RPP).
- Botón de regeneración y aviso de URL desactualizada.
- Reintentos con retroceso exponencial y mensajes de error específicos.
- Verificación robusta con estado «No verificable» y colores en Excel.
- Mejora en la detección de encabezados de tablas.
- Documentación completa en `README4.md`.

### v1.0.0 - Noviembre 2026

- Endpoints `/api/v1/rpa/extract` y `/api/v1/rpa/download/{filename}`.
- Motor de detección de tablas, listas y enlaces.
- Paginación, deduplicación, verificación y generación de Excel.
- Panel React `RpaExportPanel` y cliente `rpaAPI`.

---

**Proyecto:** SIMAP - Universal Web Scraper & Intelligence Platform  
**Módulo:** RPA integrado (URL → Excel)  
**Versión:** 1.1.0  
**Fecha:** Noviembre 2026
