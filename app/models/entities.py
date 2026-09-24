from datetime import datetime
from typing import Optional, Any
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()


class User(Base):
    """
    Entidad de usuario para autenticación JWT y asociación de reportes generados.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    nombre_completo = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relaciones
    reportes = relationship(
        "AnalysisReport",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    monitoreos = relationship(
        "MonitoredTarget",
        back_populates="user",
        cascade="all, delete-orphan"
    )


class Snapshot(Base):
    """
    Registro histórico de una captura de scraping de una URL.
    Permite comparar versiones pasadas con la actual.
    """
    __tablename__ = "snapshots"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, nullable=False, index=True)
    site_title = Column(String, nullable=True)
    tipo_contenido = Column(String(50), nullable=False)
    total_items = Column(Integer, default=0)
    data = Column(JSON, nullable=False)  # Lista de noticias o texto continuo
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relaciones
    reportes_actuales = relationship(
        "AnalysisReport",
        foreign_keys="AnalysisReport.current_snapshot_id",
        back_populates="current_snapshot",
        cascade="all, delete-orphan"
    )
    reportes_previos = relationship(
        "AnalysisReport",
        foreign_keys="AnalysisReport.previous_snapshot_id",
        back_populates="previous_snapshot"
    )


class AnalysisReport(Base):
    """
    Registro de análisis semántico generado por IA (Ollama)
    y referencias a los reportes generados en Excel y Word.
    """
    __tablename__ = "analysis_reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    url = Column(String, nullable=False, index=True)
    current_snapshot_id = Column(Integer, ForeignKey("snapshots.id", ondelete="CASCADE"), nullable=True)
    previous_snapshot_id = Column(Integer, ForeignKey("snapshots.id", ondelete="SET NULL"), nullable=True)
    resumen_ejecutivo = Column(Text, nullable=True)
    metricas = Column(JSON, nullable=True)            # Categorías, sentimiento, distribución
    diferencias_delta = Column(JSON, nullable=True)   # Novedades vs noticias salientes
    excel_path = Column(String, nullable=True)
    word_path = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relaciones
    user = relationship("User", back_populates="reportes")
    current_snapshot = relationship("Snapshot", foreign_keys=[current_snapshot_id], back_populates="reportes_actuales")
    previous_snapshot = relationship("Snapshot", foreign_keys=[previous_snapshot_id], back_populates="reportes_previos")


class MonitoredTarget(Base):
    """
    Sitio web configurado para seguimiento recurrente temporal (1 a 30 días)
    con detección automática de cambios y alertas por correo.
    """
    __tablename__ = "monitored_targets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    url = Column(String, nullable=False, index=True)
    dias_duracion = Column(Integer, default=3)
    frecuencia_horas = Column(Integer, default=12)
    fecha_inicio = Column(DateTime(timezone=True), server_default=func.now())
    fecha_fin = Column(DateTime(timezone=True), nullable=False)
    activo = Column(Boolean, default=True, index=True)
    notificar_email = Column(Boolean, default=True)
    ultimo_chequeo = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relaciones
    user = relationship("User", back_populates="monitoreos")


class AgentEvent(Base):
    """
    Registro de eventos generados por el Agente de Monitoreo Autónomo
    (function calling con Ollama): cambios críticos, correos enviados,
    eventos registrados en Google Sheets y transcripciones de sesiones.
    """
    __tablename__ = "agent_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    tipo_evento = Column(String(80), nullable=False, default="evento_generico")
    titulo = Column(String(300), nullable=True)
    descripcion = Column(Text, nullable=True)
    url_fuente = Column(String, nullable=True)
    nivel_prioridad = Column(String(20), nullable=True, default="BAJO")
    canal = Column(String(40), nullable=True, default="sistema")  # email | sheets | ambos | sistema
    razon_ia = Column(Text, nullable=True)
    metadatos = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

