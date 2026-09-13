import re
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.entities import Snapshot

# Parámetros de tracking y marcas temporales volátiles en URLs
TRACKING_QUERY_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "t", "ts", "timestamp", "time", "_", "_cb", "v",
    "ref", "session_id", "rnd", "cache_buster", "nc"
}

# Patrones de publicidad o anuncios en títulos o encabezados
PATRON_AD_TITULO = re.compile(
    r'^(publicidad|patrocinado|anuncio|advertisement|sponsored|anuncie aquí|aviso publicitario|suscríbete al boletín|banner)\b',
    re.IGNORECASE
)

# Patrones de líneas de texto dinámicas (fechas de carga, horas relativas, contadores de visualizaciones)
PATRONES_LINEAS_DINAMICAS = [
    # Tiempos relativos: "hace 5 minutos", "hace 2 horas", "hace 1 día", "3 mins ago"
    re.compile(r'\bhace\s+\d+\s+(segundo|minuto|hora|día|semana|mes|año)s?\b', re.IGNORECASE),
    re.compile(r'\b\d+\s+(sec|min|mins|hr|hrs|hour|hours|day|days)\s+ago\b', re.IGNORECASE),
    re.compile(r'\b(justo ahora|hace un momento|recién publicado|actualizado recientemente)\b', re.IGNORECASE),
    # Fechas de carga o actualización dinámicas: "Actualizado: 12:30", "Fecha de carga: 06/09/2026"
    re.compile(r'\b(última\s+actualización|actualizado(\s+el|\s+hace)?|fecha\s+de\s+carga|hora\s+de\s+carga|generado\s+en|tiempo\s+de\s+carga|last\s+updated|loaded\s+at)\b', re.IGNORECASE),
    # Contadores dinámicos de visualizaciones / lecturas: "1,250 lecturas", "200 personas están leyendo esto"
    re.compile(r'\b\d+[\d,.]*\s*(vistas|visitas|lecturas|lectores|veces\s+le[ií]do|personas(\s+est[aá]n)?\s+leyendo|compartidos|comentarios)\b', re.IGNORECASE),
    re.compile(r'\b\d+[\d,.]*\s*(personas|usuarios)\s+(en\s+l[ií]nea|leyendo|conectados)\b', re.IGNORECASE),
    re.compile(r'\b(leyendo|vistas?|visitas?|lectores?):\s*\d+', re.IGNORECASE),
    # Avisos de cookies / copyright dinámico
    re.compile(r'\b(este\s+sitio\s+(web\s+)?utiliza\s+cookies|política\s+de\s+cookies|aceptar\s+cookies|todos\s+los\s+derechos\s+reservados)\b', re.IGNORECASE),
]


def normalizar_url(url: str) -> str:
    """
    Normaliza una URL eliminando fragmentos y parámetros volátiles de tracking o timestamps
    (utm_*, fbclid, t, timestamp, etc.) para evitar falsos positivos al comparar deltas.
    """
    if not url:
        return ""
    try:
        parsed = urlparse(url.strip())
        if not parsed.netloc and not parsed.path:
            return url.strip()

        query_items = parse_qsl(parsed.query, keep_blank_values=False)
        clean_query = [
            (k, v) for k, v in query_items
            if k.lower() not in TRACKING_QUERY_PARAMS and not k.lower().startswith("utm_")
        ]
        new_query = urlencode(clean_query)

        path = parsed.path
        if len(path) > 1 and path.endswith("/"):
            path = path[:-1]

        clean_url = urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            parsed.params,
            new_query,
            ""
        ))
        return clean_url
    except Exception:
        return url.strip()


def es_linea_dinamica(linea: str) -> bool:
    """
    Determina si una línea de texto contiene elementos dinámicos volátiles
    (banners publicitarios, fechas de carga cambiantes, horas relativas o contadores)
    que no representan una modificación real en el contenido de la noticia.
    """
    linea_limpia = linea.strip()
    if not linea_limpia or len(linea_limpia) < 5:
        return True

    if PATRON_AD_TITULO.search(linea_limpia):
        return True

    for patron in PATRONES_LINEAS_DINAMICAS:
        if patron.search(linea_limpia):
            return True

    return False


def es_item_ruido_o_publicidad(item: Dict[str, Any]) -> bool:
    """Verifica si un ítem extraído es un banner de publicidad o widget no informativo."""
    titulo = str(item.get("titulo", "")).strip()
    url = str(item.get("url", "")).strip()
    if PATRON_AD_TITULO.search(titulo):
        return True
    if any(ad_domain in url.lower() for ad_domain in ["doubleclick.net", "googleads", "adnuntius", "outbrain", "taboola"]):
        return True
    return False


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
        Ignora elementos dinámicos (banners de publicidad, fechas de carga, tracking params)
        para evitar falsos positivos al detectar si una noticia cambió.
        """
        if not isinstance(data_actual, list) or not isinstance(data_anterior, list):
            # Páginas públicas de texto continuo (normas, pronunciamientos, términos, blogs)
            str_ant = str(data_anterior)
            str_act = str(data_actual)

            lineas_ant_todas = [l.strip() for l in str_ant.splitlines() if len(l.strip()) > 15]
            lineas_act_todas = [l.strip() for l in str_act.splitlines() if len(l.strip()) > 15]

            # Filtrar líneas dinámicas volátiles (banners, timestamps de carga, horas relativas)
            lineas_ant_estables = [l for l in lineas_ant_todas if not es_linea_dinamica(l)]
            lineas_act_estables = [l for l in lineas_act_todas if not es_linea_dinamica(l)]

            set_ant = set(lineas_ant_estables)
            set_act = set(lineas_act_estables)

            nuevas_lineas = list(set_act - set_ant)
            lineas_salientes = list(set_ant - set_act)

            len_ant_estable = sum(len(l) for l in lineas_ant_estables)
            len_act_estable = sum(len(l) for l in lineas_act_estables)
            diff_chars = len_act_estable - len_ant_estable

            nuevos_items = [{"titulo": l[:150], "url": ""} for l in nuevas_lineas[:20]]
            salientes_items = [{"titulo": l[:150], "url": ""} for l in lineas_salientes[:20]]

            return {
                "es_lista": False,
                "variacion_caracteres": diff_chars,
                "cambio_porcentual": round((diff_chars / max(len_ant_estable, 1)) * 100, 2),
                "total_nuevos": len(nuevas_lineas),
                "total_salientes": len(lineas_salientes),
                "total_anteriores": len(set_ant),
                "total_actuales": len(set_act),
                "nuevos_articulos": nuevos_items,
                "articulos_salientes": salientes_items,
                "articulos_mantenidos": []
            }

        # Páginas tipo lista de entidades
        items_ant_filtrados = [
            item for item in data_anterior
            if isinstance(item, dict) and "url" in item and not es_item_ruido_o_publicidad(item)
        ]
        items_act_filtrados = [
            item for item in data_actual
            if isinstance(item, dict) and "url" in item and not es_item_ruido_o_publicidad(item)
        ]

        # Mapeo usando URLs normalizadas (limpias de tracking y parámetros volátiles)
        map_ant = {normalizar_url(item["url"]): item for item in items_ant_filtrados}
        map_act = {normalizar_url(item["url"]): item for item in items_act_filtrados}

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
