import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from openpyxl import load_workbook

from bot_extraccion import (
    ARCHIVO_POR_DEFECTO,
    URL_POR_DEFECTO,
    BotExtraccionHockey,
    verificar_muestra,
)

MAPA_COLUMNAS = {
    "N°": "numero",
    "Equipo": "equipo",
    "Año": "anio",
    "Victorias": "victorias",
    "Derrotas": "derrotas",
    "Derrotas OT": "derrotas_ot",
    "% Victorias": "porcentaje_victorias",
    "Goles a favor": "goles_favor",
    "Goles en contra": "goles_contra",
    "Diferencia": "diferencia",
    "Página fuente": "pagina",
    "Fuente (URL)": "fuente",
    "Fecha de extracción": "fecha_extraccion",
}


def leer_reporte(archivo: Path) -> Dict[str, Any]:
    wb = load_workbook(str(archivo), data_only=True)
    ws = wb["Datos Extraídos"]
    encabezados = [celda.value for celda in ws[1]]

    registros: List[Dict[str, Any]] = []
    for fila in ws.iter_rows(min_row=2, values_only=True):
        if not any(valor is not None for valor in fila):
            continue
        registro = {}
        for indice, encabezado in enumerate(encabezados):
            clave = MAPA_COLUMNAS.get(encabezado)
            if clave:
                registro[clave] = fila[indice] if indice < len(fila) else None
        if registro.get("equipo"):
            registros.append(registro)

    url_base = URL_POR_DEFECTO
    if "Fuente y Metadatos" in wb.sheetnames:
        for fila in wb["Fuente y Metadatos"].iter_rows(values_only=True):
            if fila and fila[0] == "Fuente de consulta" and fila[1]:
                url_base = str(fila[1])
                break

    return {"registros": registros, "url_base": url_base}


def parsear_argumentos(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verifica una muestra del Excel comparándola con la página pública."
    )
    parser.add_argument("--archivo", default=str(ARCHIVO_POR_DEFECTO), help="Ruta del .xlsx.")
    parser.add_argument("--muestra", type=int, default=5, help="Registros a verificar.")
    parser.add_argument("--url", default=None, help="URL base de consulta (opcional).")
    argumentos = parser.parse_args(argv)
    if argumentos.muestra < 1:
        parser.error("--muestra debe ser mayor o igual a 1.")
    return argumentos


def main(argv: Optional[List[str]] = None) -> int:
    argumentos = parsear_argumentos(argv)
    archivo = Path(argumentos.archivo)

    if not archivo.exists():
        print(f"[ERROR] No existe el archivo: {archivo}")
        print("Ejecuta primero: python bot_extraccion.py")
        return 2

    datos = leer_reporte(archivo)
    registros = datos["registros"]
    if not registros:
        print("[ERROR] El reporte no contiene registros para verificar.")
        return 2

    url_base = argumentos.url or datos["url_base"]
    max_paginas = max(int(registro.get("pagina") or 1) for registro in registros)
    bot = BotExtraccionHockey(url_base=url_base, limite=len(registros), max_paginas=max_paginas)

    print("=" * 78)
    print("Verificación independiente del reporte Excel contra la página pública")
    print("=" * 78)
    print(f"Archivo: {archivo}")
    print(f"Fuente: {url_base}")
    print(f"Registros en Excel: {len(registros)}")

    try:
        verificaciones, resumen = verificar_muestra(bot, registros, argumentos.muestra)
    except requests.RequestException as error:
        print(f"[ERROR] No se pudo consultar la página: {error}")
        return 2

    print(
        f"\nMuestra verificada: {resumen['registros_verificados']} registros | "
        f"{resumen['campos_comparados']} campos | "
        f"{resumen['coincidencias']} coincidencias | "
        f"{resumen['diferencias']} diferencias"
    )

    print(
        f"\n{'Equipo':<24} {'Año':>5} {'Campo':<18} "
        f"{'Excel':>12} {'Página':>12} {'Resultado':>12}"
    )
    for item in verificaciones:
        print(
            f"{item['Equipo']:<24} {item['Año']:>5} {item['Campo']:<18} "
            f"{str(item['Valor en Excel']):>12} "
            f"{str(item['Valor en la página']):>12} "
            f"{item['Resultado']:>12}"
        )

    if resumen["diferencias"]:
        print("\n[RESULTADO] Se encontraron diferencias en la muestra.")
        return 1

    print("\n[RESULTADO] La muestra coincide con los datos publicados en la página.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
