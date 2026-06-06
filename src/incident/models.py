# src/incident/models.py
"""SQLAlchemy models for the Incident Memory Store.
Defines tables:
- incidents
- incident_actions
- incident_fixes
- incident_memory
"""

from sqlalchemy import Column, Integer, String, DateTime, JSON, Boolean, ForeignKey, func
from sqlalchemy.orm import relationship

from src.engine.models import Base

class Incident(Base):
    __tablename__ = "incidents"
    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(String, unique=True, nullable=False, index=True)  # e.g., "INC-001"
    severity = Column(String, nullable=False)
    status = Column(String, nullable=False, default="OPEN")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    description = Column(String, nullable=True)

    actions = relationship("IncidentAction", back_populates="incident", cascade="all, delete-orphan")
    fixes = relationship("IncidentFix", back_populates="incident", cascade="all, delete-orphan")

class IncidentAction(Base):
    __tablename__ = "incident_actions"
    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=False)
    action_type = Column(String, nullable=False)  # e.g., "CREATE", "INVESTIGATE"
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    incident = relationship("Incident", back_populates="actions")

class IncidentFix(Base):
    __tablename__ = "incident_fixes"
    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=False)
    patch_path = Column(String, nullable=False)  # filesystem path to generated patch
    validation_status = Column(String, nullable=False, default="PENDING")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    incident = relationship("Incident", back_populates="fixes")

class IncidentMemory(Base):
    __tablename__ = "incident_memory"
    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=False)
    root_cause = Column(String, nullable=True)
    recovery_time_seconds = Column(Integer, nullable=True)
    success = Column(Boolean, default=False)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    incident = relationship("Incident", backref="memory", uselist=False)
