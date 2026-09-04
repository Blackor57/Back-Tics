# snapshot_service.py
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.entities import Snapshot


class SnapshotService:
    @staticmethod
    async def guardar_snapshot(
        session: AsyncSession,
        url: str,
        site_title: str,
        tipo_contenido: str,
        data: Any
    ) -> Snapshot:
        """
        Almacena una captura completa (snapshot) de una URL en PostgreSQL.
        """
        total_items = len(data) if isinstance(data, list) else 1
        snapshot = Snapshot(
            url=url,
            site_title=site_title,
            tipo_contenido=tipo_contenido,
            total_items=total_items,
            data=data
        )
        session.add(snapshot)
        await session.flush()
        await session.refresh(snapshot)
        return snapshot

    @staticmethod
    async def obtener_ultimo_snapshot(
        session: AsyncSession,
        url: str,
        exclude_id: Optional[int] = None
    ) -> Optional[Snapshot]:
        """
        Obtiene el snapshot más reciente previamente guardado para una URL dada.
        """
        stmt = (
            select(Snapshot)
            .where(Snapshot.url == url)
            .order_by(Snapshot.created_at.desc())
        )
        if exclude_id is not None:
            stmt = stmt.where(Snapshot.id != exclude_id)
        
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    def calcular_delta(
        data_anterior: Any,
        data_actual: Any
    ) -> Dict[str, Any]:
        """
        Calcula las diferencias entre los datos de dos snapshots de la misma URL.
        Detecta qué artículos entraron como novedades y cuáles ya no figuran en portada.
        """
        if not isinstance(data_actual, list) or not isinstance(data_anterior, list):
            # En caso de páginas públicas de texto continuo (normas, pronunciamientos, términos, blogs, landing pages)
            str_ant = str(data_anterior)
            str_act = str(data_actual)
            len_ant = len(str_ant)
            len_act = len(str_act)
            diff_chars = len_act - len_ant

            # Detección de párrafos o líneas modificadas/añadidas
            lineas_ant = set(filter(None, [l.strip() for l in str_ant.splitlines() if len(l.strip()) > 15]))
            lineas_act = set(filter(None, [l.strip() for l in str_act.splitlines() if len(l.strip()) > 15]))
            nuevas_lineas = list(lineas_act - lineas_ant)
            lineas_salientes = list(lineas_ant - lineas_act)

            nuevos_items = [{"titulo": l[:150], "url": ""} for l in nuevas_lineas[:20]]
            salientes_items = [{"titulo": l[:150], "url": ""} for l in lineas_salientes[:20]]

            return {
                "es_lista": False,
                "variacion_caracteres": diff_chars,
                "cambio_porcentual": round((diff_chars / max(len_ant, 1)) * 100, 2),
                "total_nuevos": len(nuevas_lineas),
                "total_salientes": len(lineas_salientes),
                "total_anteriores": len(lineas_ant),
                "total_actuales": len(lineas_act),
                "nuevos_articulos": nuevos_items,
                "articulos_salientes": salientes_items,
                "articulos_mantenidos": []
            }


        map_ant = {item.get("url"): item for item in data_anterior if isinstance(item, dict) and "url" in item}
        map_act = {item.get("url"): item for item in data_actual if isinstance(item, dict) and "url" in item}

        urls_ant = set(map_ant.keys())
        urls_act = set(map_act.keys())

        urls_nuevas = urls_act - urls_ant
        urls_salientes = urls_ant - urls_act
        urls_mantenidas = urls_act & urls_ant

        nuevos_items = [map_act[u] for u in urls_nuevas]
        salientes_items = [map_ant[u] for u in urls_salientes]
        mantenidos_items = [map_act[u] for u in urls_mantenidas]

        total_actual = len(urls_act)
        rotacion_pct = round((len(urls_nuevas) / max(total_actual, 1)) * 100, 1)

        return {
            "es_lista": True,
            "total_anteriores": len(urls_ant),
            "total_actuales": len(urls_act),
            "total_nuevos": len(urls_nuevas),
            "total_salientes": len(urls_salientes),
            "total_mantenidos": len(urls_mantenidas),
            "tasa_rotacion_pct": rotacion_pct,
            "nuevos_articulos": nuevos_items,
            "articulos_salientes": salientes_items,
            "articulos_mantenidos": mantenidos_items
        }
