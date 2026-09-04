# app/api/v1/tracking.py
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.entities import User, MonitoredTarget
from app.schemas.tracking import (
    TrackTargetCreate,
    TrackTargetUpdate,
    TrackTargetResponse
)

router = APIRouter(tags=["Monitoreo & Seguimiento de URLs"])


@router.post(
    "/start",
    response_model=TrackTargetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Iniciar seguimiento continuo de una URL (1 a 30 días)"
)
async def start_tracking(
    payload: TrackTargetCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Configura el monitoreo recurrente de una URL para un usuario autenticado.
    El sistema inspeccionará la página cada X horas y, si detecta cambios relevantes
    (nuevas noticias o eventos), enviará un correo de alerta con el análisis inteligente.
    """
    url_str = str(payload.url)

    # Verificar si ya existe un seguimiento activo para esta URL y este usuario
    stmt = select(MonitoredTarget).where(
        MonitoredTarget.user_id == current_user.id,
        MonitoredTarget.url == url_str,
        MonitoredTarget.activo == True
    )
    res = await db.execute(stmt)
    existente = res.scalars().first()
    if existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya tienes un monitoreo activo para esta URL (ID: {existente.id}). Puedes pausarlo o actualizarlo."
        )

    ahora = datetime.now(timezone.utc)
    fecha_fin = ahora + timedelta(days=payload.dias_duracion)

    nuevo_monitoreo = MonitoredTarget(
        user_id=current_user.id,
        url=url_str,
        dias_duracion=payload.dias_duracion,
        frecuencia_horas=payload.frecuencia_horas,
        fecha_inicio=ahora,
        fecha_fin=fecha_fin,
        activo=True,
        notificar_email=payload.notificar_email,
        ultimo_chequeo=None
    )

    db.add(nuevo_monitoreo)
    await db.commit()
    await db.refresh(nuevo_monitoreo)

    return TrackTargetResponse.model_validate(nuevo_monitoreo)


@router.get(
    "/my-targets",
    response_model=List[TrackTargetResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar URLs monitoreadas por el usuario"
)
async def list_user_targets(
    activo: Optional[bool] = Query(None, description="Filtrar por estado activo (true) o finalizado (false)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Obtiene la lista de todas las URLs que el usuario tiene o ha tenido en seguimiento.
    """
    stmt = select(MonitoredTarget).where(MonitoredTarget.user_id == current_user.id)
    if activo is not None:
        stmt = stmt.where(MonitoredTarget.activo == activo)
    stmt = stmt.order_by(MonitoredTarget.created_at.desc())

    res = await db.execute(stmt)
    targets = res.scalars().all()

    return [TrackTargetResponse.model_validate(t) for t in targets]


@router.patch(
    "/{target_id}/toggle",
    response_model=TrackTargetResponse,
    status_code=status.HTTP_200_OK,
    summary="Pausar o reanudar un monitoreo"
)
async def toggle_target(
    target_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Alterna el estado entre activo e inactivo de un seguimiento.
    """
    stmt = select(MonitoredTarget).where(
        MonitoredTarget.id == target_id,
        MonitoredTarget.user_id == current_user.id
    )
    res = await db.execute(stmt)
    target = res.scalars().first()

    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Monitoreo no encontrado o no pertenece a tu cuenta."
        )

    # Si se intenta reactivar un seguimiento cuya fecha_fin ya expiró, extenderlo por su duración original
    ahora = datetime.now(timezone.utc)
    target_fin = target.fecha_fin.replace(tzinfo=timezone.utc) if target.fecha_fin.tzinfo is None else target.fecha_fin
    if not target.activo and ahora >= target_fin:
        target.fecha_fin = ahora + timedelta(days=target.dias_duracion)

    target.activo = not target.activo
    await db.commit()
    await db.refresh(target)

    return TrackTargetResponse.model_validate(target)


@router.put(
    "/{target_id}",
    response_model=TrackTargetResponse,
    status_code=status.HTTP_200_OK,
    summary="Actualizar parámetros de un monitoreo"
)
async def update_target(
    target_id: int,
    payload: TrackTargetUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Actualiza la frecuencia de revisión, alerta de correo o estado activo de un monitoreo existente.
    """
    stmt = select(MonitoredTarget).where(
        MonitoredTarget.id == target_id,
        MonitoredTarget.user_id == current_user.id
    )
    res = await db.execute(stmt)
    target = res.scalars().first()

    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Monitoreo no encontrado."
        )

    if payload.activo is not None:
        target.activo = payload.activo
    if payload.notificar_email is not None:
        target.notificar_email = payload.notificar_email
    if payload.frecuencia_horas is not None:
        target.frecuencia_horas = payload.frecuencia_horas

    await db.commit()
    await db.refresh(target)

    return TrackTargetResponse.model_validate(target)


@router.delete(
    "/{target_id}",
    status_code=status.HTTP_200_OK,
    summary="Eliminar un monitoreo"
)
async def delete_target(
    target_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Elimina definitivamente el registro de monitoreo para la URL.
    """
    stmt = select(MonitoredTarget).where(
        MonitoredTarget.id == target_id,
        MonitoredTarget.user_id == current_user.id
    )
    res = await db.execute(stmt)
    target = res.scalars().first()

    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Monitoreo no encontrado."
        )

    await db.delete(target)
    await db.commit()

    return {"message": "Seguimiento eliminado exitosamente", "id": target_id}
