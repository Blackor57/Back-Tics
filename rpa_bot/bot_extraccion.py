import argparse
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

URL_POR_DEFECTO = "https://www.scrapethissite.com/pages/forms/"
DIR_SALIDA = Path(__file__).resolve().parent / "salidas"
ARCHIVO_POR_DEFECTO = DIR_SALIDA / "datos_extraidos.xlsx"
VERSION_BOT = "1.0.0"

COLUMNAS_EXCEL = [
    ("N°", "numero"),
    ("Equipo", "equipo"),
    ("Año", "anio"),
    ("Victorias", "victorias"),
    ("Derrotas", "derrotas"),
    ("Derrotas OT", "derrotas_ot"),
    ("% Victorias", "porcentaje_victorias"),
    ("Goles a favor", "goles_favor"),
    ("Goles en contra", "goles_contra"),
    ("Diferencia", "diferencia"),
    ("Página fuente", "pagina"),
    ("Fuente (URL)", "fuente"),
    ("Fecha de extracción", "fecha_extraccion"),
]

CAMPOS_VERIFICACION = [
    ("equipo", "Equipo"),
    ("anio", "Año"),
    ("victorias", "Victorias"),
    ("derrotas", "Derrotas"),
    ("porcentaje_victorias", "% Victorias"),
    ("goles_favor", "Goles a favor"),
    ("goles_contra", "Goles en contra"),
    ("diferencia", "Diferencia"),
]


def _texto_celda(fila, clase: str) -> str:
    celda = fila.find("td", class_=clase)
    return celda.get_text(" ", strip=True) if celda else ""


def _entero(valor: str) -> Optional[int]:
    try:
        limpio = valor.replace(",", "").strip()
        return int(limpio) if limpio else None
    except (TypeError, ValueError):
        return None


def _decimal(valor: str) -> Optional[float]:
    try:
        limpio = valor.replace("%", "").replace(",", ".").strip()
        return float(limpio) if limpio else None
    except (TypeError, ValueError):
        return None


def _normalizar(valor: Any) -> Any:
    if isinstance(valor, float):
        return round(valor, 6)
    return valor


def _mostrar(valor: Any) -> str:
    return "-" if valor in (None, "") else str(valor)


class BotExtraccionHockey:
    def __init__(
        self,
        url_base: str,
        limite: int = 40,
        max_paginas: int = 2,
        timeout: int = 20,
        pausa: float = 0.5,
    ):
        self.url_base = url_base
        self.limite = limite
        self.max_paginas = max_paginas
        self.timeout = timeout
        self.pausa = pausa
        self.session = self._crear_sesion()

    def _crear_sesion(self) -> requests.Session:
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36 SIMAP-RPA-Bot/1.0"
                ),
                "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )
        reintentos = Retry(
            total=3,
            backoff_factor=0.6,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adaptador = HTTPAdapter(max_retries=reintentos)
        session.mount("https://", adaptador)
        session.mount("http://", adaptador)
        return session

    def consultar(self, url: str) -> str:
        respuesta = self.session.get(url, timeout=self.timeout)
        respuesta.raise_for_status()
        if not respuesta.encoding or respuesta.encoding.lower() == "iso-8859-1":
            respuesta.encoding = respuesta.apparent_encoding or "utf-8"
        return respuesta.text

    def url_pagina(self, numero_pagina: int) -> str:
        if numero_pagina <= 1:
            return self.url_base
        separador = "&" if "?" in self.url_base else "?"
        return f"{self.url_base}{separador}page_num={numero_pagina}"

    def extraer_pagina(
        self, html: str, url_pagina: str, numero_pagina: int
    ) -> Tuple[str, List[Dict[str, Any]]]:
        soup = BeautifulSoup(html, "html.parser")
        titulo = soup.title.get_text(" ", strip=True) if soup.title else ""
        filas = soup.select("tr.team")
        fecha_extraccion = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        registros: List[Dict[str, Any]] = []

        for fila in filas:
            equipo = _texto_celda(fila, "name")
            if not equipo:
                continue
            registros.append(
                {
                    "equipo": equipo,
                    "anio": _entero(_texto_celda(fila, "year")),
                    "victorias": _entero(_texto_celda(fila, "wins")),
                    "derrotas": _entero(_texto_celda(fila, "losses")),
                    "derrotas_ot": _entero(_texto_celda(fila, "ot-losses")),
                    "porcentaje_victorias": _decimal(_texto_celda(fila, "pct")),
                    "goles_favor": _entero(_texto_celda(fila, "gf")),
                    "goles_contra": _entero(_texto_celda(fila, "ga")),
                    "diferencia": _entero(_texto_celda(fila, "diff")),
                    "pagina": numero_pagina,
                    "fuente": url_pagina,
                    "fecha_extraccion": fecha_extraccion,
                }
            )

        return titulo, registros

    def ejecutar(self) -> Dict[str, Any]:
        registros: List[Dict[str, Any]] = []
        vistos = set()
        titulos: List[str] = []
        paginas_consultadas: List[str] = []

        for numero_pagina in range(1, self.max_paginas + 1):
            if len(registros) >= self.limite:
                break

            url = self.url_pagina(numero_pagina)
            html = self.consultar(url)
            titulo, registros_pagina = self.extraer_pagina(html, url, numero_pagina)
            if titulo:
                titulos.append(titulo)
            paginas_consultadas.append(url)

            if not registros_pagina:
                break

            for registro in registros_pagina:
                clave = (registro["equipo"], registro["anio"])
                if clave in vistos:
                    continue
                vistos.add(clave)
                registro["numero"] = len(registros) + 1
                registros.append(registro)
                if len(registros) >= self.limite:
                    break

            if numero_pagina < self.max_paginas:
                time.sleep(self.pausa)

        return {
            "titulo_sitio": titulos[0] if titulos else "",
            "paginas_consultadas": paginas_consultadas,
            "registros": registros,
            "fecha_ejecucion": datetime.now(),
            "limite_solicitado": self.limite,
        }


def verificar_muestra(
    bot: BotExtraccionHockey, registros: List[Dict[str, Any]], cantidad: int = 5
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    if not registros:
        return [], {
            "registros_verificados": 0,
            "campos_comparados": 0,
            "coincidencias": 0,
            "diferencias": 0,
        }

    cantidad = max(1, min(cantidad, len(registros)))
    if cantidad == 1:
        indices = [0]
    else:
        paso = (len(registros) - 1) / (cantidad - 1)
        indices = sorted({round(i * paso) for i in range(cantidad)})

    muestra = [registros[i] for i in indices]
    paginas_necesarias = sorted({registro["pagina"] for registro in muestra})
    cache: Dict[int, Dict[Tuple[str, Optional[int]], Dict[str, Any]]] = {}

    for numero_pagina in paginas_necesarias:
        url = bot.url_pagina(numero_pagina)
        html = bot.consultar(url)
        _, registros_frescos = bot.extraer_pagina(html, url, numero_pagina)
        cache[numero_pagina] = {
            (registro["equipo"], registro["anio"]): registro
            for registro in registros_frescos
        }

    resultados: List[Dict[str, Any]] = []
    for registro in muestra:
        fresco = cache.get(registro["pagina"], {}).get(
            (registro["equipo"], registro["anio"])
        )
        for campo, etiqueta in CAMPOS_VERIFICACION:
            valor_excel = registro.get(campo)
            valor_web = fresco.get(campo) if fresco else None
            coincide = _normalizar(valor_excel) == _normalizar(valor_web)
            resultados.append(
                {
                    "Equipo": registro["equipo"],
                    "Año": registro["anio"],
                    "Campo": etiqueta,
                    "Valor en Excel": valor_excel,
                    "Valor en la página": valor_web,
                    "Resultado": "Coincide" if coincide else "No coincide",
                }
            )

    total = len(resultados)
    coincidencias = sum(1 for item in resultados if item["Resultado"] == "Coincide")
    return resultados, {
        "registros_verificados": len(muestra),
        "campos_comparados": total,
        "coincidencias": coincidencias,
        "diferencias": total - coincidencias,
    }


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
        celda.alignment = Alignment(horizontal="center", vertical="center")
        celda.border = borde
    ws.row_dimensions[1].height = 24


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


def guardar_excel(
    resultado: Dict[str, Any],
    verificaciones: List[Dict[str, Any]],
    resumen_verificacion: Dict[str, int],
    archivo: Path,
) -> Path:
    archivo.parent.mkdir(parents=True, exist_ok=True)
    registros = resultado["registros"]

    wb = Workbook()
    ws = wb.active
    ws.title = "Datos Extraídos"
    ws.views.sheetView[0].showGridLines = True

    for columna, (titulo, _) in enumerate(COLUMNAS_EXCEL, start=1):
        ws.cell(row=1, column=columna, value=titulo)

    _aplicar_estilo_encabezado(ws, len(COLUMNAS_EXCEL))

    fuente_datos = Font(name="Segoe UI", size=9, color="334155")
    fuente_url = Font(name="Segoe UI", size=9, color="2563EB", underline="single")
    relleno_zebra = PatternFill("solid", fgColor="F8FAFC")

    for indice, registro in enumerate(registros, start=2):
        for columna, (_, clave) in enumerate(COLUMNAS_EXCEL, start=1):
            valor = registro.get(clave)
            celda = ws.cell(row=indice, column=columna, value=valor)
            celda.font = fuente_datos
            celda.alignment = Alignment(
                horizontal="center" if columna in (1, 3, 4, 5, 6, 7, 8, 9, 10, 11) else "left",
                vertical="center",
            )
            if indice % 2 == 0:
                celda.fill = relleno_zebra

        celda_url = ws.cell(row=indice, column=12)
        if isinstance(registro.get("fuente"), str) and registro["fuente"].startswith("http"):
            celda_url.hyperlink = registro["fuente"]
            celda_url.font = fuente_url

    _aplicar_bordes(ws, 2, max(2, len(registros) + 1), len(COLUMNAS_EXCEL))
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(COLUMNAS_EXCEL))}{max(1, len(registros) + 1)}"

    anchos = [6, 24, 8, 10, 10, 11, 13, 14, 15, 11, 12, 52, 20]
    for columna, ancho in enumerate(anchos, start=1):
        ws.column_dimensions[get_column_letter(columna)].width = ancho

    ws2 = wb.create_sheet("Fuente y Metadatos")
    ws2.views.sheetView[0].showGridLines = False
    ws2["A1"] = "FUENTE DE CONSULTA Y METADATOS DEL REPORTE"
    ws2["A1"].font = Font(name="Segoe UI", size=14, bold=True, color="0F172A")
    ws2.merge_cells("A1:B1")

    metadatos = [
        ("Reporte", "Estadísticas NHL por temporada (registros y años)"),
        ("Sitio consultado", resultado.get("titulo_sitio", "")),
        ("Fuente de consulta", resultado.get("paginas_consultadas", [""])[0]),
        ("Páginas consultadas", ", ".join(resultado.get("paginas_consultadas", []))),
        ("Total de registros", len(registros)),
        ("Límite solicitado", resultado.get("limite_solicitado", len(registros))),
        ("Fecha de ejecución", resultado["fecha_ejecucion"].strftime("%Y-%m-%d %H:%M:%S")),
        ("Método de extracción", "RPA básica: HTTP GET + BeautifulSoup + paginación"),
        ("Bot", f"Back-Tics/rpa_bot/bot_extraccion.py v{VERSION_BOT}"),
        (
            "Verificación de muestra",
            f"{resumen_verificacion.get('registros_verificados', 0)} registros, "
            f"{resumen_verificacion.get('campos_comparados', 0)} campos comparados, "
            f"{resumen_verificacion.get('coincidencias', 0)} coincidencias, "
            f"{resumen_verificacion.get('diferencias', 0)} diferencias",
        ),
        (
            "Nota",
            "Sitio público de práctica para aprendizaje de scraping. "
            "Los datos se consultan con pausas y sin autenticación.",
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

    ws2.column_dimensions["A"].width = 24
    ws2.column_dimensions["B"].width = 90

    ws3 = wb.create_sheet("Verificación de Muestra")
    ws3.views.sheetView[0].showGridLines = True
    encabezados_verificacion = [
        "Equipo",
        "Año",
        "Campo",
        "Valor en Excel",
        "Valor en la página",
        "Resultado",
    ]
    for columna, titulo in enumerate(encabezados_verificacion, start=1):
        ws3.cell(row=1, column=columna, value=titulo)
    _aplicar_estilo_encabezado(ws3, len(encabezados_verificacion))

    if verificaciones:
        relleno_ok = PatternFill("solid", fgColor="ECFDF5")
        relleno_fallo = PatternFill("solid", fgColor="FEF2F2")
        for indice, item in enumerate(verificaciones, start=2):
            for columna, titulo in enumerate(encabezados_verificacion, start=1):
                celda = ws3.cell(row=indice, column=columna, value=item.get(titulo))
                celda.font = fuente_datos
                celda.alignment = Alignment(horizontal="center", vertical="center")
                if titulo == "Resultado":
                    celda.fill = relleno_ok if item[titulo] == "Coincide" else relleno_fallo
        _aplicar_bordes(ws3, 2, len(verificaciones) + 1, len(encabezados_verificacion))
        ws3.auto_filter.ref = (
            f"A1:{get_column_letter(len(encabezados_verificacion))}{len(verificaciones) + 1}"
        )
    else:
        ws3.cell(row=2, column=1, value="No se ejecutó la verificación de muestra.")

    for columna, ancho in enumerate([24, 8, 18, 18, 20, 14], start=1):
        ws3.column_dimensions[get_column_letter(columna)].width = ancho
    ws3.freeze_panes = "A2"

    wb.save(str(archivo))
    return archivo


def parsear_argumentos(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bot RPA: extrae registros de una página pública y genera un Excel."
    )
    parser.add_argument("--url", default=URL_POR_DEFECTO, help="URL pública a consultar.")
    parser.add_argument("--limite", type=int, default=40, help="Mínimo 10 registros.")
    parser.add_argument("--paginas", type=int, default=2, help="Máximo de páginas a recorrer.")
    parser.add_argument("--muestra", type=int, default=5, help="Registros a verificar.")
    parser.add_argument("--salida", default=str(ARCHIVO_POR_DEFECTO), help="Ruta del .xlsx.")
    parser.add_argument(
        "--sin-verificacion",
        action="store_true",
        help="Omite la comparación de la muestra contra la página.",
    )
    argumentos = parser.parse_args(argv)
    if argumentos.limite < 10:
        parser.error("--limite debe ser mayor o igual a 10.")
    if argumentos.paginas < 1:
        parser.error("--paginas debe ser mayor o igual a 1.")
    if argumentos.muestra < 1:
        parser.error("--muestra debe ser mayor o igual a 1.")
    return argumentos


def main(argv: Optional[List[str]] = None) -> int:
    argumentos = parsear_argumentos(argv)
    bot = BotExtraccionHockey(
        url_base=argumentos.url,
        limite=argumentos.limite,
        max_paginas=argumentos.paginas,
    )

    print("=" * 78)
    print("SIMAP RPA - Bot de extracción de datos a Excel")
    print("=" * 78)
    print(f"Fuente: {argumentos.url}")
    print(f"Límite de registros: {argumentos.limite} | Páginas máximas: {argumentos.paginas}")

    try:
        resultado = bot.ejecutar()
    except requests.RequestException as error:
        print(f"[ERROR] No se pudo consultar la página: {error}")
        return 2

    registros = resultado["registros"]
    print(f"Registros extraídos: {len(registros)}")
    print(f"Páginas consultadas: {len(resultado['paginas_consultadas'])}")

    if len(registros) < 10:
        print("[ADVERTENCIA] Se obtuvieron menos de 10 registros.")

    verificaciones: List[Dict[str, Any]] = []
    resumen_verificacion = {
        "registros_verificados": 0,
        "campos_comparados": 0,
        "coincidencias": 0,
        "diferencias": 0,
    }

    if not argumentos.sin_verificacion and registros:
        print("\nVerificando muestra contra la página...")
        try:
            verificaciones, resumen_verificacion = verificar_muestra(
                bot, registros, argumentos.muestra
            )
        except requests.RequestException as error:
            print(f"[ADVERTENCIA] No se pudo verificar la muestra: {error}")
        else:
            print(
                "Verificación: "
                f"{resumen_verificacion['registros_verificados']} registros | "
                f"{resumen_verificacion['campos_comparados']} campos | "
                f"{resumen_verificacion['coincidencias']} coincidencias | "
                f"{resumen_verificacion['diferencias']} diferencias"
            )
            for item in verificaciones:
                if item["Resultado"] != "Coincide":
                    print(
                        f"  [FALLO] {item['Equipo']} {item['Año']} - {item['Campo']}: "
                        f"Excel={item['Valor en Excel']} | Web={item['Valor en la página']}"
                    )

    archivo = guardar_excel(
        resultado,
        verificaciones,
        resumen_verificacion,
        Path(argumentos.salida),
    )

    print("\nMuestra de registros extraídos:")
    print(
        f"{'N°':>3}  {'Equipo':<24} {'Año':>5} {'V':>4} {'D':>4} "
        f"{'%':>7} {'GF':>5} {'GC':>5} {'Dif':>5}"
    )
    for registro in registros[:10]:
        print(
            f"{registro['numero']:>3}  {registro['equipo']:<24} "
            f"{_mostrar(registro['anio']):>5} "
            f"{_mostrar(registro['victorias']):>4} "
            f"{_mostrar(registro['derrotas']):>4} "
            f"{_mostrar(registro['porcentaje_victorias']):>7} "
            f"{_mostrar(registro['goles_favor']):>5} "
            f"{_mostrar(registro['goles_contra']):>5} "
            f"{_mostrar(registro['diferencia']):>5}"
        )

    print(f"\nArchivo Excel generado: {archivo}")
    print("Hojas: Datos Extraídos | Fuente y Metadatos | Verificación de Muestra")
    return 0 if resumen_verificacion.get("diferencias", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
