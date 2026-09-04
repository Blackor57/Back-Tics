# app/schemas/auth.py
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator
import re


class UserCreate(BaseModel):
    email: str = Field(..., description="Correo electrónico del usuario", json_schema_extra={"example": "usuario@ejemplo.com"})
    password: str = Field(..., min_length=6, description="Contraseña de al menos 6 caracteres", json_schema_extra={"example": "secreto123"})
    nombre_completo: Optional[str] = Field(None, description="Nombre o alias del usuario", json_schema_extra={"example": "Juan Pérez"})

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        patron = r"^[\w\.-]+@[\w\.-]+\.\w+$"
        if not re.match(patron, v):
            raise ValueError("Formato de correo electrónico inválido.")
        return v


class UserLogin(BaseModel):
    email: str = Field(..., description="Correo electrónico registrado", json_schema_extra={"example": "usuario@ejemplo.com"})
    password: str = Field(..., description="Contraseña", json_schema_extra={"example": "secreto123"})

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        return v.strip().lower()


class UserResponse(BaseModel):
    id: int
    email: str
    nombre_completo: Optional[str] = None
    is_active: bool
    is_superuser: bool
    is_verified: bool = False
    created_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True
    }


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class ResendVerificationRequest(BaseModel):
    email: str = Field(..., description="Correo electrónico registrado para reenviar confirmación", json_schema_extra={"example": "usuario@ejemplo.com"})

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        patron = r"^[\w\.-]+@[\w\.-]+\.\w+$"
        if not re.match(patron, v):
            raise ValueError("Formato de correo electrónico inválido.")
        return v


class MessageResponse(BaseModel):
    mensaje: str
    detalle: Optional[str] = None
