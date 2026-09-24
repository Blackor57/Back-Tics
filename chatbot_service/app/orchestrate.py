# chatbot_service/app/orchestrate.py
"""
Orquestador del pipeline de chat (intención -> datos -> redacción).

Flujo por petición /chat:
1. Recupera historial de Redis (últimos N turnos).
2. Clasifica intención con Ollama (valor por defecto: factual).
3. Recupera contexto según intención:
   - factual / estado / comparacion: text-to-SQL (SELECT seguro + READ ONLY).
   - busqueda: búsqueda vectorial pgvector.
   - resumen: text-to-SQL de cambios recientes + resumidor.
   - accion: guía estática.
4. Redacción final (streaming desde Ollama) con el contexto recuperado.
5. Guarda el turno en Redis.
"""
import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Dict, List

from app import prompts
from app.intent import IntentRouter
from app.memory import RedisMemory
from app.ollama import OllamaClient
from app.sql_agent import SqlSafeResult, SqlValidationError, generate_sql, run_readonly_sql, validate_sql
from app.summarize import summarize_changes
from app.vector_search import VectorSearch

logger = logging.getLogger("uvicorn.error")


class ChatPipeline:
    """Construye las respuestas del chatbot y las transmite como eventos SSE."""

    def __init__(
        self,
        client: OllamaClient,
        memory: RedisMemory,
        router: IntentRouter,
        vector_search: VectorSearch,
    ) -> None:
        self.client = client
        self.memory = memory
        self.router = router
        self.vector_search = vector_search

    # ------------------------------------------------------------------
    # Utilidades de eventos
    # ------------------------------------------------------------------
    @staticmethod
    def _sse(event: str, data: Dict[str, Any]) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    # ------------------------------------------------------------------
    # Recuperación de contexto según intención
    # ------------------------------------------------------------------
    async def _obtener_contexto_sql(
        self, question: str, historial: str, intent: str
    ) -> List[Dict[str, Any]] | None:
        """Genera y ejecuta SQL para intenciones estructuradas."""
        try:
            plan = await generate_sql(self.client, question, historial)
            query = validate_sql(plan["sql"])
            result: SqlSafeResult = await run_readonly_sql(query)
        except SqlValidationError as e:
            logger.info("SQL rechazado (%s): %s", intent, e)
            return None

        # Algunas intenciones necesitan contexto adicional: embeddings siempre
        # que el conjunto devuelto sea pequeño, para enriquecer la redacción.
        rows = result.rows
        context_text = result.to_text(max_rows=25)
        preparado = {"explicacion": plan.get("explicacion", ""), "rows": rows, "text": context_text}
        return [preparado]

    async def _obtener_contexto_vectorial(self, question: str) -> List[Dict[str, Any]]:
        resultados = await self.vector_search.search(question)
        if not resultados:
            return []
        return [{"rows": [], "text": self.vector_search.format_context(resultados), "explicacion": "búsqueda vectorial"}]

    # ------------------------------------------------------------------
    # Generación de la respuesta final en streaming
    # ------------------------------------------------------------------
    async def _stream_final(
        self, question: str, historial: str, contexto_text: str
    ) -> AsyncGenerator[str, None]:
        messages = [
            {"role": "system", "content": prompts.FINAL_RESPONSE_SYSTEM},
        ]
        if historial.strip():
            messages.append({"role": "system", "content": f"Historial de la conversación:\n{historial}"})
        messages.append(
            {
                "role": "user",
                "content": prompts.TEMPLATE_FINAL_RESPONSE.format(
                    historial=historial or "(sin historial previo)",
                    contexto=contexto_text or "(Sin contexto recuperado.)",
                    consulta=question,
                ),
            }
        )
        try:
            async for token in self.client.generate_stream(messages, temperature=0.3, num_predict=700):
                yield token
        except Exception as e:  # noqa: BLE001
            logger.warning("Streaming final falló: %s", e)
            yield "Ollama no está disponible. Aquí está el contexto recuperado:\n\n" + (contexto_text or "")

    # ------------------------------------------------------------------
    # Pipeline principal (generador de eventos SSE)
    # ------------------------------------------------------------------
    async def chat(self, session_id: str, message: str) -> AsyncGenerator[str, None]:
        # 1) Memoria
        historial_raw = await self.memory.get_history(session_id)
        historial_text = "\n".join(
            f"{'Usuario' if t.get('role') == 'user' else 'Asistente'}: {t.get('content', '')}"
            for t in historial_raw[-8:]
        )[:3000]

        try:
            # 2) Intención
            clasificacion = await self.router.classify(message, historial_raw)
            intent = clasificacion["intent"]
            yield self._sse("intent", {"intent": intent, "confidence": clasificacion.get("confidence", 0.0)})

            contexto_text = ""
            resp_tokens: List[str] = []

            # 3) Contexto por intención
            if intent == "accion":
                texto = prompts.ACTION_GUIDANCE
                yield self._sse("source", {"kind": "accion", "rows": 0})
                full = ""
                async for token in self._ghost_stream(texto):
                    full += token
                    yield self._sse("token", {"content": token})
                yield self._sse("done", {"intent": intent, "tokens": len(full)})
                return

            if intent == "busqueda":
                vectorial = await self._obtener_contexto_vectorial(message)
                yield self._sse("source", {"kind": "vector", "fragmentos": len(vectorial)})
                if vectorial:
                    contexto_text = vectorial[0]["text"]

            elif intent == "resumen":
                sql_result = await self._obtener_contexto_sql(message, historial_text, intent)
                if sql_result:
                    preparado = sql_result[0]
                    yield self._sse("source", {"kind": "sql", "filas": len(preparado["rows"])})
                    full = ""
                    async for token in summarize_changes(
                        self.client, SqlSafeResult(preparado["rows"], len(preparado["rows"])), message
                    ):
                        full += token
                        yield self._sse("token", {"content": token})
                    yield self._sse("done", {"intent": intent, "tokens": len(full)})
                    return
                yield self._sse("source", {"kind": "sql", "filas": 0, "error": "sin resultados"})
                contexto_text = ""

            else:  # factual / estado / comparacion
                preparado = await self._obtener_contexto_sql(message, historial_text, intent)
                if preparado:
                    p = preparado[0]
                    yield self._sse("source", {"kind": "sql", "filas": len(p["rows"]), "explicacion": p["explicacion"]})
                    if not p["rows"]:
                        # Sin filas: complementar con búsqueda semántica
                        extra = await self._obtener_contexto_vectorial(message)
                        if extra:
                            yield self._sse("source", {"kind": "vector", "fragmentos": len(extra), "complemento": True})
                            p["text"] = (p["text"] + "\n\nContexto semántico adicional:\n" + extra[0]["text"])[:6000]
                    contexto_text = p["text"]
                else:
                    yield self._sse("source", {"kind": "sql", "filas": 0, "error": "intento no ejecutable"})
                    contexto_text = ""

            # 4) Redacción final en streaming
            full = ""
            async for token in self._stream_final(message, historial_text, contexto_text):
                full += token
                resp_tokens.append(token)
                yield self._sse("token", {"content": token})

            yield self._sse("done", {"intent": intent, "tokens": len(resp_tokens)})

        except Exception as e:  # noqa: BLE001
            logger.exception("Error en el pipeline de chat")
            yield self._sse(
                "error",
                {"message": "Ocurrió un error interno procesando tu consulta.", "detalle": str(e)},
            )

    @staticmethod
    async def _ghost_stream(texto: str) -> AsyncGenerator[str, None]:
        """Transmite un texto estático en pseudo-streaming (respuestas 'accion')."""
        chunk_size = 64
        for i in range(0, len(texto), chunk_size):
            yield texto[i:i + chunk_size]
            await asyncio.sleep(0.005)