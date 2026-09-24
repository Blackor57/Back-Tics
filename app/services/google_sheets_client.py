# app/services/google_sheets_client.py
"""
Cliente de Google Sheets (gspread) para el registro automatizado de eventos.

El Agente de Monitoreo Autónomo invoca `registrar_evento()` cuando detecta
un cambio crítico (por ejemplo, una nueva licitación pública). Si no hay
credenciales configuradas, el servicio entra en modo simulación y registra
el evento en el log sin fallar.
"""
import json
import logging
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

from app.core.config import (
    GOOGLE_SHEETS_CREDENTIALS_PATH,
    GOOGLE_SHEETS_CREDENTIALS_JSON,
    GOOGLE_SHEETS_SPREADSHEET_NAME,
    GOOGLE_SHEETS_WORKSHEET_NAME,
)

logger = logging.getLogger("sheet_client")

ENCABEZADOS = [
    "timestamp",
    "tipo_evento",
    "titulo",
    "descripcion",
    "url_fuente",
    "nivel_prioridad",
    "origen_ia",
]


def _credenciales() -> Optional[Dict[str, Any]]:
    """Devuelve la credencial de service account desde JSON explícito o archivo."""
    if GOOGLE_SHEETS_CREDENTIALS_JSON.strip():
        try:
            return json.loads(GOOGLE_SHEETS_CREDENTIALS_JSON)
        except Exception as e:
            logger.warning(f"GOOGLE_SHEETS_CREDENTIALS_JSON no es JSON válido: {str(e)}")
    if GOOGLE_SHEETS_CREDENTIALS_PATH.strip():
        ruta = Path(GOOGLE_SHEETS_CREDENTIALS_PATH)
        if ruta.exists():
            try:
                return json.loads(ruta.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning(f"No se pudo leer el JSON de credenciales: {str(e)}")
    return None


class GoogleSheetsClient:
    """
    Encapsula el acceso a Google Sheets mediante gspread.
    Métodos de escritura ejecutados en threadpool para no bloquear asyncio.
    """

    @staticmethod
    def disponible() -> bool:
        return _credenciales() is not None

    @staticmethod
    def _crear_sheet():
        """Abre (o crea) la hoja de cálculo y devuelve la worksheet de eventos."""
        import gspread
        from gspread.utils import rowcol_to_a1

        creds = _credenciales()
        if not creds:
            raise RuntimeError("Sin credenciales de Google Sheets configuradas.")

        gc = gspread.service_account_from_dict(creds)
        try:
            sh = gc.open(GOOGLE_SHEETS_SPREADSHEET_NAME)
        except gspread.SpreadsheetNotFound:
            # Crear el libro y compartirlo con el correo de la service account
            sh = gc.create(GOOGLE_SHEETS_SPREADSHEET_NAME)
            if creds.get("client_email"):
                try:
                    sh.share(creds["client_email"], perm_type="user", role="writer")
                except Exception:
                    pass

        try:
            ws = sh.worksheet(GOOGLE_SHEETS_WORKSHEET_NAME)
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title=GOOGLE_SHEETS_WORKSHEET_NAME, rows=1000, cols=len(ENCABEZADOS))

        # Asegurar encabezados la primera vez
        if ws.row_values(1) != ENCABEZADOS:
            ws.update("A1:" + rowcol_to_a1(1, len(ENCABEZADOS)), [ENCABEZADOS])

        return ws

    @classmethod
    def _registrar_sincrono(cls, datos: Dict[str, Any]) -> Dict[str, Any]:
        """Registra un evento agregando una fila a la hoja (ejecución sincrona en thread)."""
        fila = [
            datetime.now(timezone.utc).isoformat(),
            str(datos.get("tipo_evento", "evento_generico")),
            str(datos.get("titulo", ""))[:300],
            str(datos.get("descripcion", ""))[:1000],
            str(datos.get("url_fuente", "")),
            str(datos.get("nivel_prioridad", "BAJO")),
            str(datos.get("origen_ia", "agente_simap")),
        ]
        try:
            ws = cls._crear_sheet()
            ws.append_row(fila, value_input_option="USER_ENTERED")
            return {"ok": True, "sheet": GOOGLE_SHEETS_SPREADSHEET_NAME, "fila": fila}
        except Exception as e:
            logger.error(f"Error al registrar evento en Google Sheets: {str(e)}")
            return {"ok": False, "error": str(e), "fila": fila}

    @classmethod
    async def registrar_evento(cls, datos: Dict[str, Any]) -> Dict[str, Any]:
        """
        Registra un evento en la hoja de cálculo. Devuelve un dict con resultado.
        Si no hay credenciales, simula el registro en consola para desarrollo local.
        """
        if not cls.disponible():
            aviso = (
                f"\n{'='*70}\n"
                f"  ⚠️ [MODO SIMULACIÓN GOOGLE SHEETS - NO SE REGISTRÓ EN LA NUBE]\n"
                f"  Motivo: sin GOOGLE_SHEETS_CREDENTIALS_PATH/JSON en .env\n"
                f"  Tipo evento: {datos.get('tipo_evento')}\n"
                f"  Título: {datos.get('titulo')}\n"
                f"  URL: {datos.get('url_fuente')}\n"
                f"{'='*70}"
            )
            logger.warning(aviso)
            return {
                "ok": True,
                "modo": "simulacion",
                "sheet": GOOGLE_SHEETS_SPREADSHEET_NAME,
                "mensaje": "Evento simulado en consola (sin credenciales de Google Sheets).",
            }

        return await asyncio.to_thread(cls._registrar_sincrono, datos)