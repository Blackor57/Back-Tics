# app/api/v1/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user
)
from app.models.entities import User
from app.schemas.auth import UserCreate, UserLogin, UserResponse, TokenResponse

router = APIRouter(tags=["Autenticación & Usuarios"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un nuevo usuario y obtener JWT"
)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    Registra una cuenta de usuario en el sistema.
    Retorna el perfil del usuario creado junto a su token JWT para inicio de sesión inmediato.
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
        is_superuser=False
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    # Generar token JWT
    token = create_access_token({"sub": str(new_user.id), "email": new_user.email})

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
