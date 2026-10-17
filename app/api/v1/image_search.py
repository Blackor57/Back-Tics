# app/api/v1/image_search.py
"""
Router para la búsqueda visual por imagen mediante Gemini Vision.

Endpoint:
    POST /api/v1/image-search/search
    Content-Type: multipart/form-data
    Body: { image: <archivo .jpg / .png> }
    Response: { "url": "https://..." }
"""

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.services.image_search_service import ImageSearchService

router = APIRouter(tags=["Búsqueda por Imagen"])

_image_search_service = ImageSearchService()

# Tipos MIME permitidos para la carga de imágenes
_ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/gif",
}

# Tamaño máximo de imagen: 10 MB
_MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024


@router.post(
    "/search",
    status_code=status.HTTP_200_OK,
    summary="Búsqueda visual por imagen con Gemini Vision",
    description=(
        "Recibe una imagen (.jpg / .png) y utiliza Google Gemini Vision para identificar "
        "el producto o contenido en la foto. Retorna la URL más relevante y cercana "
        "al producto encontrado (tienda oficial, marketplace, fabricante, etc.).\n\n"
        "**Campos de respuesta aceptados:** `url`, `result_url`, `similar_url`, `link`."
    ),
    response_description="URL más relevante para el producto identificado en la imagen.",
)
async def search_by_image(
    image: UploadFile = File(
        ...,
        description="Archivo de imagen (.jpg, .png, .webp). Máximo 10 MB.",
    )
) -> dict:
    """
    Pipeline de búsqueda visual:

    1. Valida el tipo de archivo y el tamaño.
    2. Lee los bytes de la imagen.
    3. Envía la imagen a Gemini Vision con un prompt especializado.
    4. Extrae y retorna la URL más relevante del resultado de Gemini.
    """

    # --- Validación del MIME type ---
    content_type = (image.content_type or "").lower()
    # Normalizar 'image/jpg' -> 'image/jpeg'
    if content_type == "image/jpg":
        content_type = "image/jpeg"

    if content_type not in _ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Tipo de archivo no soportado: '{image.content_type}'. "
                "Solo se aceptan imágenes JPEG, PNG, WebP o GIF."
            ),
        )

    # --- Lectura de bytes ---
    image_bytes = await image.read()

    # --- Validación del tamaño ---
    if len(image_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo de imagen está vacío.",
        )

    if len(image_bytes) > _MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"El archivo supera el límite de 10 MB "
                f"({len(image_bytes) / 1024 / 1024:.1f} MB recibidos)."
            ),
        )

    # --- Procesamiento con Gemini ---
    try:
        result = await _image_search_service.search_by_image(
            image_bytes=image_bytes,
            mime_type=content_type,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inesperado durante la búsqueda por imagen: {str(exc)}",
        ) from exc

    if isinstance(result, dict):
        return result

    return {"url": result}
