import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, HttpUrl

from app.core.security import get_optional_current_user
from app.models.entities import User
from app.services.email_service import EmailService
from app.services.rpa_service import (
    RPA_DIR,
    RpaExtractionError,
    extraer_y_exportar,
)

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/rpa", tags=["RPA"])

NOMBRE_ARCHIVO_VALIDO = re.compile(r"^rpa_[a-f0-9]{10}\.xlsx$")
MEDIA_TYPE_XLSX = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


class RpaExtractRequest(BaseModel):
    url: HttpUrl = Field(..., description="URL pública de la página a consultar")
    limite: int = Field(
        40,
        ge=10,
        le=100,
        description="Número máximo de registros a extraer (mínimo 10)",
    )
    max_paginas: int = Field(
        2,
        ge=1,
        le=5,
        description="Número máximo de páginas a recorrer",
    )
    verificar: bool = Field(
        True,
        description="Verifica una muestra de registros contra la página en vivo",
    )


@router.post("/extract")
async def extraer(
    payload: RpaExtractRequest,
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Consulta una URL pública, detecta tablas o listas de datos, extrae al menos
    10 registros, verifica una muestra y genera un Excel descargable con
    encabezados, fuente y metadatos.

    Si el usuario está autenticado, el Excel se envía automáticamente al correo
    con el que se registró.
    """
    try:
        resultado = await extraer_y_exportar(
            url=str(payload.url),
            limite=payload.limite,
            max_paginas=payload.max_paginas,
            verificar=payload.verificar,
        )
    except RpaExtractionError as error:
        raise HTTPException(status_code=422, detail=str(error))
    except Exception as error:
        logger.exception("Error inesperado en la extracción RPA: %s", error)
        raise HTTPException(
            status_code=500,
            detail="No se pudo completar la extracción RPA. Revisa la URL e inténtalo nuevamente.",
        )

    resultado["correo_enviado"] = False
    resultado["correo_destino"] = None

    if current_user and current_user.email:
        archivo = RPA_DIR / resultado["archivo"]
        try:
            enviado = await EmailService.enviar_reporte_excel(
                destinatario=current_user.email,
                nombre_usuario=current_user.nombre_completo or current_user.email.split("@")[0],
                url_fuente=str(payload.url),
                archivo_excel=archivo,
                total_registros=resultado.get("total_registros", 0),
                resumen_ejecutivo=(
                    f"Extracción automática con {resultado.get('total_registros', 0)} "
                    f"registros provenientes de {resultado.get('total_paginas', 1)} página(s)."
                ),
                titulo_reporte="Reporte RPA · URL a Excel",
            )
            resultado["correo_enviado"] = bool(enviado)
            resultado["correo_destino"] = current_user.email
        except Exception as error:
            logger.error("No se pudo enviar el Excel RPA por correo: %s", error)

    return resultado


@router.get("/download/{filename}")
async def descargar(filename: str):
    """Descarga un archivo Excel generado por el motor RPA."""
    if not NOMBRE_ARCHIVO_VALIDO.match(filename):
        raise HTTPException(status_code=400, detail="Nombre de archivo RPA inválido.")

    archivo = RPA_DIR / filename
    if not archivo.exists() or not archivo.is_file():
        raise HTTPException(status_code=404, detail="El archivo RPA no existe o expiró.")

    return FileResponse(
        path=archivo,
        media_type=MEDIA_TYPE_XLSX,
        filename=filename,
        headers={"Cache-Control": "no-store"},
    )
