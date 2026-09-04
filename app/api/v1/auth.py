# app/api/v1/auth.py
import asyncio
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_email_verification_token,
    decode_email_verification_token,
    get_current_user
)
from app.services.email_service import EmailService
from app.models.entities import User
from app.schemas.auth import (
    UserCreate,
    UserLogin,
    UserResponse,
    TokenResponse,
    ResendVerificationRequest,
    MessageResponse
)

router = APIRouter(tags=["Autenticación & Usuarios"])


def _render_verification_html(titulo: str, mensaje: str, subtexto: str, es_exito: bool = True) -> str:
    """Genera una página HTML estilizada para la respuesta visual del navegador al hacer clic en el enlace."""
    icono = "✅" if es_exito else "⚠️"
    color_borde = "#10b981" if es_exito else "#f87171"
    
    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{titulo} - SIMAP</title>
        <style>
            body {{
                margin: 0;
                padding: 0;
                display: flex;
                align-items: center;
                justify-content: center;
                min-height: 100vh;
                background-color: #0f172a;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            }}
            .card {{
                max-width: 480px;
                width: 90%;
                background-color: #1e293b;
                border-radius: 16px;
                padding: 40px 32px;
                text-align: center;
                box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.5);
                border: 1px solid rgba(255, 255, 255, 0.08);
            }}
            .icon {{
                font-size: 54px;
                margin-bottom: 20px;
                display: inline-block;
            }}
            h1 {{
                color: #ffffff;
                font-size: 22px;
                margin: 0 0 12px 0;
                font-weight: 700;
            }}
            p.desc {{
                color: #94a3b8;
                font-size: 15px;
                line-height: 1.6;
                margin: 0 0 24px 0;
            }}
            .subtext {{
                background-color: rgba(255, 255, 255, 0.04);
                border-left: 3px solid {color_borde};
                border-radius: 6px;
                padding: 12px 16px;
                font-size: 13px;
                color: #cbd5e1;
                text-align: left;
                margin-bottom: 28px;
            }}
            .footer {{
                font-size: 12px;
                color: #64748b;
                margin-top: 24px;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="icon">{icono}</div>
            <h1>{titulo}</h1>
            <p class="desc">{mensaje}</p>
            <div class="subtext">{subtexto}</div>
            <div class="footer">Sistema Automatizado de Scraping &bull; 2026</div>
        </div>
    </body>
    </html>
    """


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un nuevo usuario y despachar correo de confirmación"
)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    Registra una cuenta de usuario en el sistema.
    Crea el usuario con `is_verified=False` y despacha un correo de confirmación asíncrono con botón interactivo.
    Retorna el perfil del usuario creado junto a su token JWT.
    """
    # Verificar si el correo ya existe
    stmt = select(User).where(User.email == payload.email)
    res = await db.execute(stmt)
    existing_user = res.scalars().first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un usuario registrado con este correo electrónico."
        )

    # Crear y almacenar el usuario
    hashed = hash_password(payload.password)
    new_user = User(
        email=payload.email,
        hashed_password=hashed,
        nombre_completo=payload.nombre_completo,
        is_active=True,
        is_superuser=False,
        is_verified=False
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    # Generar token JWT para la sesión
    token = create_access_token({"sub": str(new_user.id), "email": new_user.email})

    # Generar token de verificación de correo y despachar en segundo plano
    verification_token = create_email_verification_token(new_user.email)
    asyncio.create_task(
        EmailService.enviar_correo_verificacion(
            destinatario=new_user.email,
            nombre_usuario=new_user.nombre_completo or new_user.email.split("@")[0],
            token=verification_token
        )
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(new_user)
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Iniciar sesión y obtener token JWT"
)
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)):
    """
    Valida las credenciales (correo y contraseña).
    Retorna el token JWT con expiración configurada en el sistema.
    """
    stmt = select(User).where(User.email == payload.email)
    res = await db.execute(stmt)
    user = res.scalars().first()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo electrónico o contraseña incorrectos.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta cuenta de usuario se encuentra suspendida o inactiva."
        )

    token = create_access_token({"sub": str(user.id), "email": user.email})

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener perfil del usuario autenticado"
)
async def get_me(current_user: User = Depends(get_current_user)):
    """
    Devuelve los datos del usuario en sesión a partir de su token JWT.
    """
    return UserResponse.model_validate(current_user)


@router.get(
    "/verify",
    summary="Verificar cuenta de correo electrónico mediante token",
    response_class=HTMLResponse
)
async def verify_email(
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Endpoint invocado al hacer clic en el botón del correo electrónico.
    Decodifica el token, confirma la cuenta y devuelve una página visual atractiva.
    """
    email = decode_email_verification_token(token)
    if not email:
        html = _render_verification_html(
            titulo="Enlace Inválido o Expirado",
            mensaje="El enlace de confirmación es incorrecto o ha superado su límite de 24 horas de vigencia.",
            subtexto="Por favor solicita un nuevo correo de confirmación para activar tu cuenta.",
            es_exito=False
        )
        return HTMLResponse(content=html, status_code=status.HTTP_400_BAD_REQUEST)

    stmt = select(User).where(User.email == email)
    res = await db.execute(stmt)
    user = res.scalars().first()

    if not user:
        html = _render_verification_html(
            titulo="Usuario No Encontrado",
            mensaje="No pudimos encontrar una cuenta asociada a este correo electrónico.",
            subtexto="Verifica que te hayas registrado previamente en la plataforma.",
            es_exito=False
        )
        return HTMLResponse(content=html, status_code=status.HTTP_404_NOT_FOUND)

    if user.is_verified:
        html = _render_verification_html(
            titulo="¡Cuenta Previamente Verificada!",
            mensaje="Tu cuenta de correo ya fue confirmada con anterioridad.",
            subtexto="Ya tienes acceso completo al sistema y a los reportes automatizados.",
            es_exito=True
        )
        return HTMLResponse(content=html, status_code=status.HTTP_200_OK)

    user.is_verified = True
    await db.commit()

    html = _render_verification_html(
        titulo="¡Correo Confirmado Exitosamente!",
        mensaje=f"Tu cuenta ({email}) ha sido verificada correctamente.",
        subtexto="Tu perfil ahora cuenta con todas las funciones de monitoreo continuo y alertas activas.",
        es_exito=True
    )
    return HTMLResponse(content=html, status_code=status.HTTP_200_OK)


@router.post(
    "/resend-verification",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Reenviar enlace de confirmación de correo"
)
async def resend_verification(payload: ResendVerificationRequest, db: AsyncSession = Depends(get_db)):
    """
    Reenvía el correo de confirmación de cuenta en caso de haber expirado el enlace original.
    """
    stmt = select(User).where(User.email == payload.email)
    res = await db.execute(stmt)
    user = res.scalars().first()

    if not user:
        # Por seguridad y prevención de enumeración de usuarios
        return MessageResponse(
            mensaje="Si el correo se encuentra registrado y pendiente de confirmación, se ha enviado un nuevo enlace."
        )

    if user.is_verified:
        return MessageResponse(
            mensaje="La cuenta indicada ya se encuentra verificada.",
            detalle="is_verified: true"
        )

    token = create_email_verification_token(user.email)
    asyncio.create_task(
        EmailService.enviar_correo_verificacion(
            destinatario=user.email,
            nombre_usuario=user.nombre_completo or user.email.split("@")[0],
            token=token
        )
    )

    return MessageResponse(
        mensaje="Se ha enviado un nuevo enlace de confirmación a tu dirección de correo."
    )
