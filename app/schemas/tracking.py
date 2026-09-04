# app/schemas/tracking.py
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, HttpUrl


class TrackTargetCreate(BaseModel):
    url: HttpUrl = Field(..., json_schema_extra={"example": "https://rpp.pe/"}, description="URL a la que se le dará seguimiento continuo")
    dias_duracion: int = Field(default=3, ge=1, le=30, description="Días que durará el seguimiento continuo (1 a 30 días)", json_schema_extra={"example": 3})
    frecuencia_horas: int = Field(default=12, ge=1, le=48, description="Cada cuántas horas se revisará si hay cambios", json_schema_extra={"example": 12})
    notificar_email: bool = Field(default=True, description="Enviar alerta por correo si se detectan cambios relevantes", json_schema_extra={"example": True})


class TrackTargetUpdate(BaseModel):
    activo: Optional[bool] = Field(None, description="Activar o pausar el seguimiento")
    notificar_email: Optional[bool] = Field(None, description="Activar o desactivar notificaciones por correo")
    frecuencia_horas: Optional[int] = Field(None, ge=1, le=48, description="Modificar la frecuencia de chequeo en horas")


class TrackTargetResponse(BaseModel):
    id: int
    user_id: int
    url: str
    dias_duracion: int
    frecuencia_horas: int
    fecha_inicio: datetime
    fecha_fin: datetime
    activo: bool
    notificar_email: bool
    ultimo_chequeo: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True
    }
