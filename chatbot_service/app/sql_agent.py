# chatbot_service/app/sql_agent.py
"""
Agente Text-to-SQL.

1. Ollama genera la consulta SQL (JSON estricto) a partir de la pregunta.
2. Validación de seguridad: sólo SELECT/WITH, sin palabras peligrosas,
   una sola sentencia, límite de filas siempre presente.
3. Ejecución dentro de una transacción READ ONLY con timeout (pool asyncpg).
"""
import asyncio
import json
import logging
import re
from typing import Any, Dict, List

import asyncpg

from app import prompts
from app.config import SQL_MAX_ROWS, SQL_TIMEOUT_SECONDS
from app.database import get_readonly_pool
from app.ollama import OllamaClient

logger = logging.getLogger("uvicorn.error")


class SqlValidationError(ValueError):
    """SQL rechazado por las reglas de seguridad."""


# Palabras que invalidan el SQL generado (bloqueadas en toda la sentencia).
_FORBIDDEN_WORDS = [
    "insert", "update", "delete", "drop", "alter", "truncate", "create", "replace",
    "grant", "revoke", "copy", "call", "do", "vacuum", "analyze", "comment",
    "\\gexec", "\\copy", "pg_", "dblink", "lo_import", "lo_export",
]


def validate_sql(sql: str) -> str:
    """
    Valida y normaliza el SQL generado. Devuelve la consulta segura o lanza
    SqlValidationError.
    """
    sql = re.sub(r"--[^\n]*", "", sql)          # comentarios de línea
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)  # comentarios de bloque
    sql = sql.strip().rstrip(";").strip()

    if not sql:
        raise SqlValidationError("SQL vacío tras la limpieza.")

    if ";" in sql:
        raise SqlValidationError("Solo se permite UNA sentencia (sin ';' interno).")

    if not re.match(r"^\s*(SELECT\b|WITH\b)", sql, re.IGNORECASE):
        raise SqlValidationError("El SQL debe comenzar por SELECT o WITH.")

    lowered = sql.lower()
    for word in _FORBIDDEN_WORDS:
        if re.search(rf"\b{re.escape(word)}\b", lowered):
            raise SqlValidationError(f"Palabra prohibida en SQL generado: {word}")

    # Forzar límite de filas para que el contexto no se dispare.
    if not re.search(r"\blimit\s+\d+\b", lowered):
        sql = f"{sql} LIMIT {SQL_MAX_ROWS}"
    else:
        # Si ya trae LIMIT, lo mantenemos pero acotado a SQL_MAX_ROWS.
        sql = re.sub(
            r"\blimit\s+\d+\b",
            f"LIMIT {SQL_MAX_ROWS}",
            sql,
            flags=re.IGNORECASE,
        )
    return sql


class SqlSafeResult:
    """Resultado seguro de la consulta ejecutada."""

    def __init__(self, rows: List[Dict[str, Any]], rowcount: int) -> None:
        self.rows = rows
        self.rowcount = rowcount

    def to_text(self, max_rows: int = 20) -> str:
        """Serializa las filas para inyectarlas como contexto al redactor."""
        if not self.rows:
            return "(La consulta no devolvió filas.)"
        preview = self.rows[:max_rows]
        return json.dumps(preview, ensure_ascii=False, default=str)[:6000]


async def generate_sql(client: OllamaClient, question: str, historial: str = "") -> Dict[str, str]:
    """Pide a Ollama la consulta SQL para la pregunta dada."""
    contexto = ""
    if historial:
        contexto = f"\nCONTEXTO PREVIO DE LA CONVERSACIÓN:\n{historial}\n"
    raw = await client.generate(
        prompt=f"PREGUNTA DEL USUARIO:\n{question}{contexto}",
        system=prompts.SQL_GENERATOR_SYSTEM,
        format="json",
        temperature=0.0,
        num_predict=400,
    )
    try:
        json_block = re.search(r"(\{.*\})", raw, re.DOTALL)
        data = json.loads(json_block.group(1)) if json_block else json.loads(raw)
        sql = str(data.get("sql", "")).strip()
        if not sql:
            raise ValueError("Ollama no devolvió campo 'sql'.")
        return {"sql": sql, "explicacion": str(data.get("explicacion", ""))}
    except (json.JSONDecodeError, ValueError) as e:
        # Último recurso: usar el texto crudo como SQL.
        candidate = raw.strip().strip("`")
        if candidate.lower().startswith(("select", "with")):
            return {"sql": candidate, "explicacion": "SQL extraído de la respuesta cruda."}
        raise SqlValidationError(f"No fue posible generar SQL válido: {e}") from e


async def run_readonly_sql(sql: str) -> SqlSafeResult:
    """
    Ejecuta la consulta (ya validada) en una transacción READ ONLY.
    Devuelve filas como lista de dicts (valores serializables por asyncpg).
    """
    pool = await get_readonly_pool()
    try:
        async with pool.acquire() as conn:
            async with conn.transaction(readonly=True, isolation="read_committed"):
                records = await asyncio.wait_for(conn.fetch(sql), timeout=SQL_TIMEOUT_SECONDS)
        rows = _normalize_records(records)
        return SqlSafeResult(rows=rows, rowcount=len(rows))
    except asyncio.TimeoutError as exc:
        raise SqlValidationError("La consulta excedió el tiempo máximo permitido.") from exc
    except asyncpg.PostgresError as exc:
        raise SqlValidationError(f"La consulta fue rechazada por PostgreSQL: {exc}") from exc


def _normalize_records(records: List[asyncpg.Record]) -> List[Dict[str, Any]]:
    """Convierte asyncpg.Record en dicts serializables JSON."""
    rows: List[Dict[str, Any]] = []
    for rec in records:
        rows.append({k: _jsonable(v) for k, v in rec.items()})
    return rows


def _jsonable(value: Any) -> Any:
    if isinstance(value, (int, float, str, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    return str(value)