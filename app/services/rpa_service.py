import asyncio
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.core.config import REPORTS_DIR

RPA_DIR = REPORTS_DIR / "rpa"
RPA_DIR.mkdir(parents=True, exist_ok=True)

VERSION_RPA = "1.0.0"
MINIMO_REGISTROS = 10

SELECTORES_LISTA = [
    "article",
    "div[class*='article']",
    "div[class*='card']",
    "div[class*='item']",
    "div[class*='result']",
    "div[class*='noticia']",
    "div[class*='news']",
    "li",
]

TEXTOS_SIGUIENTE = {
    "next",
    "siguiente",
    "próximo",
    "proximo",
    "siguiente página",
    "siguiente pagina",
    "›",
    "»",
    ">",
    "→",
}


class RpaExtractionError(Exception):
    pass


def _limpiar(texto: Optional[str]) -> str:
    return re.sub(r"\s+", " ", texto or "").strip()


def _normalizar(valor: Any) -> str:
    return _limpiar(str(valor)) if valor is not None else ""


def _pagina_titulo(soup: BeautifulSoup) -> str:
    if soup.title and soup.title.get_text(strip=True):
        return _limpiar(soup.title.get_text(" ", strip=True))
    heading = soup.find(["h1", "h2"])
    return _limpiar(heading.get_text(" ", strip=True)) if heading else "Página Web"


def _siguiente_url(soup: BeautifulSoup, url_actual: str) -> Optional[str]:
    for enlace in soup.find_all("a", href=True):
        rel = " ".join(enlace.get("rel", [])).lower()
        clases = " ".join(enlace.get("class", [])).lower()
        texto = _limpiar(enlace.get_text(" ", strip=True)).lower()
        aria = _limpiar(enlace.get("aria-label", "")).lower()
        if (
            "next" in rel
            or "next" in clases
            or texto in TEXTOS_SIGUIENTE
            or "siguiente" in aria
            or "next" in aria
        ):
            href = enlace["href"].strip()
            if href and not href.startswith(("javascript:", "#", "mailto:")):
                siguiente = urljoin(url_actual, href)
                if siguiente != url_actual:
                    return siguiente
    return None


def _extraer_tabla(soup: BeautifulSoup, url_fuente: str) -> Optional[Dict[str, Any]]:
    mejor: Optional[Tuple[int, List[str], List[List[str]]]] = None

    for tabla in soup.find_all("table"):
        filas = tabla.find_all("tr")
        if len(filas) < 3:
            continue

        encabezados: List[str] = []
        thead = tabla.find("thead")
        if thead:
            celdas_thead = thead.find_all(["th", "td"])
            encabezados = [_limpiar(celda.get_text(" ", strip=True)) for celda in celdas_thead]

        filas_cuerpo = [fila for fila in filas if not fila.find_parent("thead")]

        primera_fila = filas[0]
        celdas_primera = primera_fila.find_all(["th", "td"], recursive=False)
        if not encabezados and celdas_primera and any(c.name == "th" for c in celdas_primera):
            encabezados = [_limpiar(celda.get_text(" ", strip=True)) for celda in celdas_primera]
            filas_datos = filas_cuerpo[1:] if filas_cuerpo else filas[1:]
        elif encabezados:
            filas_datos = filas_cuerpo or filas[1:]
        else:
            columnas_detectadas = max(
                (len(fila.find_all(["td", "th"])) for fila in filas_cuerpo or filas),
                default=0,
            )
            if columnas_detectadas < 2:
                continue
            encabezados = [f"Columna {i + 1}" for i in range(columnas_detectadas)]
            filas_datos = filas_cuerpo or filas

        datos: List[List[str]] = []
        for fila in filas_datos:
            celdas = fila.find_all(["td", "th"])
            if len(celdas) < 2:
                continue
            valores = [_limpiar(celda.get_text(" ", strip=True)) for celda in celdas]
            if any(valores):
                datos.append(valores)

        if len(datos) < 3:
            continue

        total_columnas = max([len(encabezados)] + [len(fila) for fila in datos])
        while len(encabezados) < total_columnas:
            encabezados.append(f"Columna {len(encabezados) + 1}")
        encabezados = encabezados[:total_columnas]

        puntaje = len(datos) * total_columnas
        if mejor is None or puntaje > mejor[0]:
            mejor = (puntaje, encabezados, datos)

    if not mejor:
        return None

    _, encabezados, datos = mejor
    columnas: List[Dict[str, str]] = []
    vistos: Dict[str, int] = {}
    for indice, titulo in enumerate(encabezados, start=1):
        titulo_limpio = _limpiar(titulo) or f"Columna {indice}"
        if titulo_limpio in vistos:
            vistos[titulo_limpio] += 1
            titulo_limpio = f"{titulo_limpio} ({vistos[titulo_limpio]})"
        else:
            vistos[titulo_limpio] = 1
        columnas.append({"clave": f"col_{indice}", "titulo": titulo_limpio[:90]})

    registros = []
    for valores in datos:
        registro: Dict[str, Any] = {"_fuente": url_fuente}
        for indice, columna in enumerate(columnas):
            registro[columna["clave"]] = valores[indice] if indice < len(valores) else ""
        registros.append(registro)

    return {"tipo": "tabla", "columnas": columnas, "registros": registros}


def _extraer_lista(soup: BeautifulSoup, url_fuente: str) -> Optional[Dict[str, Any]]:
    candidatos: List[Tuple[int, int, str, List[Dict[str, str]]]] = []

    for prioridad, selector in enumerate(SELECTORES_LISTA):
        elementos = soup.select(selector)
        if len(elementos) < 3:
            continue

        items: List[Dict[str, str]] = []
        vistos = set()
        for elemento in elementos:
            if elemento.find_parent(["nav", "header", "footer", "aside"]):
                continue
            enlace = elemento.find("a", href=True)
            titulo_tag = elemento.find(["h1", "h2", "h3", "h4", "h5", "strong"])
            titulo = (
                _limpiar(titulo_tag.get_text(" ", strip=True))
                if titulo_tag
                else (_limpiar(enlace.get_text(" ", strip=True)) if enlace else "")
            )
            if len(titulo) < 12:
                continue

            href = ""
            if enlace:
                href_crudo = enlace["href"].strip()
                if href_crudo and not href_crudo.startswith(("javascript:", "#", "mailto:")):
                    href = urljoin(url_fuente, href_crudo)

            clave = (titulo, href)
            if clave in vistos:
                continue
            vistos.add(clave)

            fecha = ""
            time_tag = elemento.find("time")
            if time_tag:
                fecha = _limpiar(time_tag.get("datetime") or time_tag.get_text(" ", strip=True))

            resumen_tag = elemento.find("p")
            resumen = _limpiar(resumen_tag.get_text(" ", strip=True))[:400] if resumen_tag else ""

            items.append({"titulo": titulo, "enlace": href, "fecha": fecha, "resumen": resumen})

        if items:
            candidatos.append((len(items) * 10 - prioridad, prioridad, selector, items))

    if not candidatos:
        return None

    candidatos.sort(reverse=True)
    _, _, _, items = candidatos[0]
    if len(items) < 3:
        return None

    tiene_fecha = any(item["fecha"] for item in items)
    tiene_resumen = any(item["resumen"] for item in items)
    columnas = [
        {"clave": "titulo", "titulo": "Título"},
        {"clave": "enlace", "titulo": "Enlace"},
    ]
    if tiene_fecha:
        columnas.append({"clave": "fecha", "titulo": "Fecha"})
    if tiene_resumen:
        columnas.append({"clave": "resumen", "titulo": "Resumen"})

    for item in items:
        item["_fuente"] = url_fuente

    return {"tipo": "lista", "columnas": columnas, "registros": items}


def _extraer_enlaces(soup: BeautifulSoup, url_fuente: str) -> Optional[Dict[str, Any]]:
    items: List[Dict[str, str]] = []
    vistos = set()
    base_netloc = urlparse(url_fuente).netloc

    for enlace in soup.find_all("a", href=True):
        texto = _limpiar(enlace.get_text(" ", strip=True))
        if len(texto) < 15:
            continue
        href_crudo = enlace["href"].strip()
        if not href_crudo or href_crudo.startswith(("javascript:", "#", "mailto:")):
            continue
        href = urljoin(url_fuente, href_crudo)
        if not href.startswith(("http://", "https://")):
            continue
        if urlparse(href).netloc == base_netloc and href.rstrip("/") == url_fuente.rstrip("/"):
            continue
        if href in vistos:
            continue
        vistos.add(href)
        items.append({"titulo": texto, "enlace": href, "fecha": "", "resumen": "", "_fuente": url_fuente})
        if len(items) >= 200:
            break

    if len(items) < 3:
        return None

    return {
        "tipo": "enlaces",
        "columnas": [
            {"clave": "titulo", "titulo": "Título"},
            {"clave": "enlace", "titulo": "Enlace"},
        ],
        "registros": items,
    }


def _parsear(html: str, url_fuente: str) -> Dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    titulo = _pagina_titulo(soup)

    tabla = _extraer_tabla(soup, url_fuente)
    lista = _extraer_lista(soup, url_fuente)
    enlaces = _extraer_enlaces(soup, url_fuente)

    if tabla and len(tabla["registros"]) >= MINIMO_REGISTROS:
        elegido = tabla
    elif lista and len(lista["registros"]) >= MINIMO_REGISTROS:
        elegido = lista
    elif enlaces and len(enlaces["registros"]) >= MINIMO_REGISTROS:
        elegido = enlaces
    else:
        candidatos = [c for c in (tabla, lista, enlaces) if c]
        if not candidatos:
            return {
                "url": url_fuente,
                "titulo": titulo,
                "tipo": "vacio",
                "columnas": [],
                "registros": [],
            }
        elegido = max(candidatos, key=lambda c: len(c["registros"]))

    elegido["url"] = url_fuente
    elegido["titulo"] = titulo
    return elegido


def _clave_registro(registro: Dict[str, Any], tipo: str) -> str:
    if tipo == "tabla":
        return "|".join(
            f"{clave}={_normalizar(valor)}"
            for clave, valor in sorted(registro.items())
            if clave != "_fuente"
        )
    if tipo == "enlaces":
        return _normalizar(registro.get("enlace")) or _normalizar(registro.get("titulo"))
    return f"{_normalizar(registro.get('titulo'))}|{_normalizar(registro.get('enlace'))}"


def _fusionar_registros(
    registros: List[Dict[str, Any]],
    pagina: Dict[str, Any],
    tipo: str,
    limite: int,
) -> int:
    if pagina.get("tipo") != tipo:
        return 0

    vistos = {_clave_registro(registro, tipo) for registro in registros}
    agregados = 0

    for registro in pagina["registros"]:
        clave = _clave_registro(registro, tipo)
        if clave in vistos:
            continue
        vistos.add(clave)
        registros.append(registro)
        agregados += 1
        if len(registros) >= limite:
            break

    return agregados


def _url_pagina_incrementada(url: str, paso: int = 1) -> Optional[str]:
    partes = urlparse(url)
    if not partes.query:
        return None

    claves_pagina = {
        "page",
        "pagina",
        "p",
        "pg",
        "pageno",
        "page_no",
        "pagenum",
        "page_num",
        "page-number",
        "pageindex",
    }
    parametros = parse_qsl(partes.query, keep_blank_values=True)
    nuevos = []
    incrementado = False

    for clave, valor in parametros:
        clave_normalizada = clave.lower()
        es_pagina = clave_normalizada in claves_pagina or (
            "page" in clave_normalizada or "pagina" in clave_normalizada
        )
        if es_pagina and re.fullmatch(r"\d+", valor or ""):
            nuevos.append((clave, str(int(valor) + paso)))
            incrementado = True
        else:
            nuevos.append((clave, valor))

    if not incrementado:
        return None

    return urlunparse(partes._replace(query=urlencode(nuevos, doseq=True)))


def _campos_verificacion(columnas: List[Dict[str, str]], tipo: str) -> List[Dict[str, str]]:
    if tipo == "tabla":
        return columnas
    permitidos = {"titulo", "enlace", "fecha"}
    return [columna for columna in columnas if columna["clave"] in permitidos]


async def _consultar(
    url: str, client: httpx.AsyncClient, intentos: int = 3
) -> str:
    ultimo_error: Optional[Exception] = None

    for intento in range(intentos):
        try:
            respuesta = await client.get(url)
            if respuesta.status_code in (429, 500, 502, 503, 504) and intento < intentos - 1:
                await asyncio.sleep(0.6 * (2 ** intento))
                continue
            respuesta.raise_for_status()

            tipo_contenido = respuesta.headers.get("content-type", "").lower()
            if (
                tipo_contenido
                and "html" not in tipo_contenido
                and "xml" not in tipo_contenido
            ):
                raise RpaExtractionError(
                    "La URL no devolvió una página HTML compatible "
                    f"(tipo de contenido: {tipo_contenido})."
                )
            return respuesta.text
        except httpx.HTTPStatusError as error:
            ultimo_error = error
            if error.response.status_code in (429, 500, 502, 503, 504) and intento < intentos - 1:
                await asyncio.sleep(0.6 * (2 ** intento))
                continue
            raise
        except RpaExtractionError:
            raise
        except (httpx.TimeoutException, httpx.TransportError) as error:
            ultimo_error = error
            if intento < intentos - 1:
                await asyncio.sleep(0.6 * (2 ** intento))
                continue
            raise

    if ultimo_error is not None:
        raise ultimo_error
    raise httpx.RequestError("No se pudo consultar la URL.")


async def _verificar_muestra(
    columnas: List[Dict[str, str]],
    registros: List[Dict[str, Any]],
    tipo: str,
    client: httpx.AsyncClient,
    cantidad: int = 5,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    resumen = {
        "registros_verificados": 0,
        "campos_comparados": 0,
        "coincidencias": 0,
        "diferencias": 0,
        "no_verificables": 0,
    }
    if not registros:
        return [], resumen

    cantidad = max(1, min(cantidad, len(registros)))
    if cantidad == 1:
        indices = [0]
    else:
        paso = (len(registros) - 1) / (cantidad - 1)
        indices = sorted({round(i * paso) for i in range(cantidad)})
    muestra = [registros[indice] for indice in indices]

    paginas = sorted({registro.get("_fuente") for registro in muestra if registro.get("_fuente")})
    cache: Dict[str, Dict[str, Dict[str, Any]]] = {}
    paginas_fallidas = set()

    for pagina in paginas:
        try:
            html = await _consultar(pagina, client)
            fresca = _parsear(html, pagina)
        except Exception:
            paginas_fallidas.add(pagina)
            continue
        cache[pagina] = {
            _clave_registro(registro, tipo): registro
            for registro in fresca["registros"]
        }

    campos = _campos_verificacion(columnas, tipo)
    resultados: List[Dict[str, Any]] = []

    for registro in muestra:
        fuente = registro.get("_fuente")
        indice_fresco = cache.get(fuente, {})
        fresco = indice_fresco.get(_clave_registro(registro, tipo))
        verificable = fuente not in paginas_fallidas
        for campo in campos:
            valor_excel = registro.get(campo["clave"])
            valor_web = fresco.get(campo["clave"]) if fresco else None
            if not verificable:
                resultado_campo = "No verificable"
            else:
                coincide = _normalizar(valor_excel) == _normalizar(valor_web)
                resultado_campo = "Coincide" if coincide else "No coincide"
            resultados.append(
                {
                    "clave": _clave_registro(registro, tipo),
                    "campo": campo["titulo"],
                    "valor_excel": valor_excel,
                    "valor_web": valor_web,
                    "resultado": resultado_campo,
                }
            )

    total = len(resultados)
    coincidencias = sum(1 for item in resultados if item["resultado"] == "Coincide")
    diferencias = sum(1 for item in resultados if item["resultado"] == "No coincide")
    no_verificables = sum(1 for item in resultados if item["resultado"] == "No verificable")
    resumen.update(
        {
            "registros_verificados": len(muestra),
            "campos_comparados": total,
            "coincidencias": coincidencias,
            "diferencias": diferencias,
            "no_verificables": no_verificables,
        }
    )
    return resultados, resumen


def _aplicar_estilo_encabezado(ws, total_columnas: int) -> None:
    relleno = PatternFill("solid", fgColor="1E3A8A")
    fuente = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
    borde = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1"),
    )
    for columna in range(1, total_columnas + 1):
        celda = ws.cell(row=1, column=columna)
        celda.fill = relleno
        celda.font = fuente
        celda.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        celda.border = borde
    ws.row_dimensions[1].height = 30


def _aplicar_bordes(ws, primera_fila: int, ultima_fila: int, total_columnas: int) -> None:
    borde = Border(
        left=Side(style="thin", color="E2E8F0"),
        right=Side(style="thin", color="E2E8F0"),
        top=Side(style="thin", color="E2E8F0"),
        bottom=Side(style="thin", color="E2E8F0"),
    )
    for fila in range(primera_fila, ultima_fila + 1):
        for columna in range(1, total_columnas + 1):
            ws.cell(row=fila, column=columna).border = borde


def indice_celda_es_enlace(columna: Dict[str, str], valor: Any) -> bool:
    if not isinstance(valor, str) or not valor.startswith(("http://", "https://")):
        return False
    clave = columna["clave"].lower()
    titulo = columna["titulo"].lower()
    return clave == "enlace" or "enlace" in titulo or "url" in titulo


def _guardar_excel(
    resultado: Dict[str, Any],
    verificaciones: List[Dict[str, Any]],
    resumen_verificacion: Dict[str, int],
    paginas: List[str],
    limite: int,
    archivo: Path,
) -> Path:
    archivo.parent.mkdir(parents=True, exist_ok=True)
    columnas = resultado["columnas"]
    registros = resultado["registros"]
    fecha_extraccion = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    wb = Workbook()
    ws = wb.active
    ws.title = "Datos Extraídos"
    ws.views.sheetView[0].showGridLines = True

    encabezados = ["N°"] + [columna["titulo"] for columna in columnas] + [
        "Fuente (URL)",
        "Fecha de extracción",
    ]
    for indice, titulo in enumerate(encabezados, start=1):
        ws.cell(row=1, column=indice, value=titulo)
    _aplicar_estilo_encabezado(ws, len(encabezados))

    fuente_datos = Font(name="Segoe UI", size=9, color="334155")
    fuente_url = Font(name="Segoe UI", size=9, color="2563EB", underline="single")
    relleno_zebra = PatternFill("solid", fgColor="F8FAFC")

    for fila_numero, registro in enumerate(registros, start=2):
        ws.cell(row=fila_numero, column=1, value=fila_numero - 1).alignment = Alignment(
            horizontal="center", vertical="center"
        )
        for columna_indice, columna in enumerate(columnas, start=2):
            valor = registro.get(columna["clave"], "")
            celda = ws.cell(row=fila_numero, column=columna_indice, value=valor)
            celda.font = fuente_datos
            celda.alignment = Alignment(vertical="center", wrap_text=False)
            if indice_celda_es_enlace(columna, valor):
                celda.hyperlink = str(valor)
                celda.font = fuente_url
        celda_fuente = ws.cell(
            row=fila_numero,
            column=len(columnas) + 2,
            value=registro.get("_fuente", resultado["url"]),
        )
        celda_fuente.font = fuente_url
        celda_fuente.hyperlink = str(registro.get("_fuente", resultado["url"]))
        ws.cell(
            row=fila_numero,
            column=len(columnas) + 3,
            value=fecha_extraccion,
        ).font = fuente_datos

        for columna_indice in range(1, len(encabezados) + 1):
            if fila_numero % 2 == 0:
                ws.cell(row=fila_numero, column=columna_indice).fill = relleno_zebra

    _aplicar_bordes(ws, 2, max(2, len(registros) + 1), len(encabezados))
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = (
        f"A1:{get_column_letter(len(encabezados))}{max(1, len(registros) + 1)}"
    )

    ws.column_dimensions["A"].width = 6
    for indice in range(2, len(columnas) + 2):
        ws.column_dimensions[get_column_letter(indice)].width = 28
    ws.column_dimensions[get_column_letter(len(columnas) + 2)].width = 52
    ws.column_dimensions[get_column_letter(len(columnas) + 3)].width = 20

    ws2 = wb.create_sheet("Fuente y Metadatos")
    ws2["A1"] = "FUENTE DE CONSULTA Y METADATOS DEL REPORTE RPA"
    ws2["A1"].font = Font(name="Segoe UI", size=14, bold=True, color="0F172A")
    ws2.merge_cells("A1:B1")

    metadatos = [
        ("Reporte", "Extracción automática de datos públicos a Excel"),
        ("Sitio consultado", resultado.get("titulo", "")),
        ("Fuente de consulta", resultado["url"]),
        ("Páginas consultadas", ", ".join(paginas)),
        ("Tipo de contenido detectado", resultado["tipo"]),
        ("Total de registros", len(registros)),
        ("Límite solicitado", limite),
        ("Fecha de generación", fecha_extraccion),
        ("Motor RPA", f"Back-Tics/app/services/rpa_service.py v{VERSION_RPA}"),
        (
            "Verificación de muestra",
            f"{resumen_verificacion.get('registros_verificados', 0)} registros, "
            f"{resumen_verificacion.get('campos_comparados', 0)} campos, "
            f"{resumen_verificacion.get('coincidencias', 0)} coincidencias, "
            f"{resumen_verificacion.get('diferencias', 0)} diferencias, "
            f"{resumen_verificacion.get('no_verificables', 0)} no verificables",
        ),
        (
            "Nota",
            "El bot consulta únicamente información pública, aplica pausas entre páginas "
            "y registra la URL de origen en cada fila.",
        ),
    ]

    for fila, (etiqueta, valor) in enumerate(metadatos, start=3):
        celda_etiqueta = ws2.cell(row=fila, column=1, value=etiqueta)
        celda_etiqueta.font = Font(name="Segoe UI", size=9, bold=True, color="1E3A8A")
        celda_etiqueta.fill = PatternFill("solid", fgColor="F1F5F9")
        celda_etiqueta.alignment = Alignment(vertical="top")
        celda_valor = ws2.cell(row=fila, column=2, value=valor)
        celda_valor.font = Font(name="Segoe UI", size=9, color="334155")
        celda_valor.alignment = Alignment(wrap_text=True, vertical="top")

    ws2.column_dimensions["A"].width = 28
    ws2.column_dimensions["B"].width = 95

    ws3 = wb.create_sheet("Verificación de Muestra")
    ws3.views.sheetView[0].showGridLines = True
    encabezados_verificacion = [
        "Clave",
        "Campo",
        "Valor en Excel",
        "Valor en la página",
        "Resultado",
    ]
    for indice, titulo in enumerate(encabezados_verificacion, start=1):
        ws3.cell(row=1, column=indice, value=titulo)
    _aplicar_estilo_encabezado(ws3, len(encabezados_verificacion))

    if verificaciones:
        relleno_ok = PatternFill("solid", fgColor="ECFDF5")
        relleno_fallo = PatternFill("solid", fgColor="FEF2F2")
        relleno_aviso = PatternFill("solid", fgColor="FEF3C7")
        for fila, item in enumerate(verificaciones, start=2):
            valores = [
                item.get("clave"),
                item.get("campo"),
                item.get("valor_excel"),
                item.get("valor_web"),
                item.get("resultado"),
            ]
            for indice, valor in enumerate(valores, start=1):
                celda = ws3.cell(row=fila, column=indice, value=valor)
                celda.font = fuente_datos
                celda.alignment = Alignment(vertical="center", wrap_text=True)
                if indice == 5:
                    if valor == "Coincide":
                        celda.fill = relleno_ok
                    elif valor == "No verificable":
                        celda.fill = relleno_aviso
                    else:
                        celda.fill = relleno_fallo
        _aplicar_bordes(ws3, 2, len(verificaciones) + 1, len(encabezados_verificacion))
        ws3.auto_filter.ref = (
            f"A1:{get_column_letter(len(encabezados_verificacion))}{len(verificaciones) + 1}"
        )
    else:
        ws3.cell(row=2, column=1, value="No se ejecutó la verificación de muestra.")

    for indice, ancho in enumerate([26, 24, 32, 32, 14], start=1):
        ws3.column_dimensions[get_column_letter(indice)].width = ancho
    ws3.freeze_panes = "A2"

    wb.save(str(archivo))
    return archivo


def _muestra_para_respuesta(
    registros: List[Dict[str, Any]], columnas: List[Dict[str, str]], cantidad: int = 5
) -> List[Dict[str, Any]]:
    muestra = []
    for registro in registros[:cantidad]:
        muestra.append({columna["titulo"]: registro.get(columna["clave"], "") for columna in columnas})
    return muestra


async def extraer_y_exportar(
    url: str,
    limite: int = 40,
    max_paginas: int = 2,
    verificar: bool = True,
) -> Dict[str, Any]:
    limite = max(MINIMO_REGISTROS, min(limite, 100))
    max_paginas = max(1, min(max_paginas, 5))

    cabeceras = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36 SIMAP-RPA-Bot/1.0"
        ),
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    try:
        async with httpx.AsyncClient(
            headers=cabeceras,
            follow_redirects=True,
            timeout=httpx.Timeout(25.0),
        ) as client:
            html = await _consultar(url, client)
            pagina = _parsear(html, url)
            if pagina["tipo"] == "vacio" or not pagina["registros"]:
                raise RpaExtractionError(
                    "No se detectaron tablas ni listas de datos en la URL indicada. "
                    "Si el sitio carga el contenido con JavaScript, este modo HTTP+HTML "
                    "no podrá leerlo: prueba con una URL que renderice los datos en el HTML."
                )

            tipo = pagina["tipo"]
            columnas = pagina["columnas"]
            registros = pagina["registros"][:limite]
            paginas = [url]
            url_actual = url
            soup_actual = BeautifulSoup(html, "html.parser")

            async def cargar(destino: str) -> Tuple[str, Dict[str, Any]]:
                await asyncio.sleep(0.35)
                contenido = await _consultar(destino, client)
                return contenido, _parsear(contenido, destino)

            for _ in range(1, max_paginas):
                if len(registros) >= limite:
                    break

                siguiente = _siguiente_url(soup_actual, url_actual)
                if not siguiente:
                    break

                html_siguiente, pagina_siguiente = await cargar(siguiente)
                agregados = _fusionar_registros(registros, pagina_siguiente, tipo, limite)
                if agregados > 0:
                    paginas.append(siguiente)
                    url_actual = siguiente
                    soup_actual = BeautifulSoup(html_siguiente, "html.parser")
                    continue

                alternativa = _url_pagina_incrementada(
                    siguiente
                ) or _url_pagina_incrementada(url_actual)
                if not alternativa or alternativa == siguiente or alternativa in paginas:
                    break

                html_alternativa, pagina_alternativa = await cargar(alternativa)
                agregados = _fusionar_registros(
                    registros, pagina_alternativa, tipo, limite
                )
                if agregados == 0:
                    break

                paginas.append(alternativa)
                url_actual = alternativa
                soup_actual = BeautifulSoup(html_alternativa, "html.parser")

            registros = registros[:limite]
            if len(registros) < MINIMO_REGISTROS:
                raise RpaExtractionError(
                    f"Solo se encontraron {len(registros)} registros. "
                    f"Se requieren al menos {MINIMO_REGISTROS}. "
                    "Prueba con otra URL o aumenta el número de páginas."
                )

            verificaciones: List[Dict[str, Any]] = []
            resumen_verificacion = {
                "registros_verificados": 0,
                "campos_comparados": 0,
                "coincidencias": 0,
                "diferencias": 0,
                "no_verificables": 0,
            }
            if verificar:
                verificaciones, resumen_verificacion = await _verificar_muestra(
                    columnas, registros, tipo, client
                )

            nombre_archivo = f"rpa_{uuid.uuid4().hex[:10]}.xlsx"
            archivo = RPA_DIR / nombre_archivo
            resultado_excel = {
                "url": url,
                "titulo": pagina["titulo"],
                "tipo": tipo,
                "columnas": columnas,
                "registros": registros,
            }
            _guardar_excel(
                resultado_excel,
                verificaciones,
                resumen_verificacion,
                paginas,
                limite,
                archivo,
            )

            return {
                "archivo": nombre_archivo,
                "descargas": {"excel": f"/api/v1/rpa/download/{nombre_archivo}"},
                "url": url,
                "sitio_titulo": pagina["titulo"],
                "tipo_contenido": tipo,
                "total_registros": len(registros),
                "total_paginas": len(paginas),
                "paginas": paginas,
                "columnas": [columna["titulo"] for columna in columnas],
                "muestra": _muestra_para_respuesta(registros, columnas),
                "verificacion": resumen_verificacion,
                "mensaje": f"Excel generado con {len(registros)} registros de {len(paginas)} página(s).",
            }
    except RpaExtractionError:
        raise
    except httpx.HTTPStatusError as error:
        codigo = error.response.status_code
        if codigo == 404:
            raise RpaExtractionError(
                "La URL respondió 404 (página no encontrada). "
                "Verifica que la dirección exista o usa otra fuente."
            )
        if codigo in (401, 403):
            raise RpaExtractionError(
                f"El sitio bloqueó la consulta automatizada (HTTP {codigo}). "
                "Prueba con otra URL pública."
            )
        raise RpaExtractionError(
            f"La página respondió con un error HTTP {codigo}. Inténtalo más tarde."
        )
    except httpx.TimeoutException:
        raise RpaExtractionError(
            "La página tardó demasiado en responder. Inténtalo nuevamente o usa otra URL."
        )
    except httpx.HTTPError as error:
        raise RpaExtractionError(f"No se pudo consultar la URL: {str(error)}")
