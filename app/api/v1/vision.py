# app/api/v1/vision.py
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

from app.services.gemini_vision import GeminiVisionService

router = APIRouter()


@router.post("/vision/analyze-image", status_code=status.HTTP_200_OK)
async def analyze_image_from_camera(
    image: UploadFile = File(...),
    prompt: Optional[str] = Form(None),
):
    """
    Analiza una imagen capturada desde cámara (web) con Gemini Vision.
    
    Flujo IoT/Cámara:
    - Usuario toma foto desde navegador (getUserMedia + canvas)
    - Imagen se envía como multipart/form-data a este endpoint
    - Gemini identifica el objeto y sugiere sitios web públicos para monitoreo
    """
    try:
        allowed_types = [
            "image/jpeg",
            "image/jpg",
            "image/png",
            "image/webp",
            "image/heic",
            "image/heif",
        ]
        content_type = image.content_type or "image/jpeg"
        if content_type.lower() not in [t.lower() for t in allowed_types]:
            raise HTTPException(
                status_code=400,
                detail=f"Tipo de archivo no permitido: {content_type}. Use JPEG, PNG, WEBP, HEIC/HEIF",
            )

        image_bytes = await image.read()
        if len(image_bytes) == 0:
            raise HTTPException(status_code=400, detail="Imagen vacía o inválida")

        # Limitar tamaño (máx 20MB)
        max_size = 20 * 1024 * 1024
        if len(image_bytes) > max_size:
            raise HTTPException(status_code=400, detail="Imagen demasiado grande (máximo 20MB)")

        service = GeminiVisionService()
        result = await service.analyze_image(
            image_bytes=image_bytes,
            mime_type=content_type,
            prompt=prompt,
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al procesar imagen: {str(e)}",
        )


@router.post("/vision/analyze-base64", status_code=status.HTTP_200_OK)
async def analyze_image_from_base64(payload: dict):
    """Endpoint alternativo para enviar imagen como base64 desde frontend."""
    try:
        image_data = payload.get("image")
        mime_type = payload.get("mimeType", "image/jpeg")
        prompt = payload.get("prompt")

        if not image_data:
            raise HTTPException(status_code=400, detail="Falta campo 'image' (base64)")

        if image_data.startswith("data:"):
            # Formato data:image/jpeg;base64,...
            try:
                image_data = image_data.split(",", 1)[1]
            except Exception:
                pass

        try:
            image_bytes = base64.b64decode(image_data)
        except Exception:
            raise HTTPException(status_code=400, detail="Formato base64 inválido")

        service = GeminiVisionService()
        result = await service.analyze_image(
            image_bytes=image_bytes,
            mime_type=mime_type,
            prompt=prompt,
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al procesar imagen: {str(e)}",
        )
