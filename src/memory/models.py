# src/memory/models.py
"""SQLAlchemy models for the Adaptive Learning Memory layer.
These tables store incident metadata, root‑cause analysis, generated patches,
validation results and outcomes. They are separate from the core incident
tables (src/incident/models.py) to keep the learning layer modular.
"""

from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
import uuid

from src.engine.models import Base

class IncidentMemory(Base):
    __tablename__ = "incident_memory"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id = Column(String, nullable=False, index=True)  # reference to core incident.id
    incident_type = Column(String, nullable=False)
    root_cause = Column(Text, nullable=True)
    recovery_action = Column(Text, nullable=True)
    patch_path = Column(String, nullable=True)
    validation_passed = Column(Boolean, nullable=True)
    outcome = Column(String, nullable=True)  # SUCCESS / FAILURE
    mttr_seconds = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    extra = Column(JSON, nullable=True)  # arbitrary payload for future extensions

class RecoveryPattern(Base):
    __tablename__ = "recovery_patterns"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pattern_name = Column(String, unique=True, nullable=False)
    description = Column(Text, nullable=True)
    occurrences = Column(Integer, default=0)
    risk_level = Column(String, default="LOW")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class FailureSignature(Base):
    __tablename__ = "failure_signatures"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    signature = Column(String, unique=True, nullable=False)
    description = Column(Text, nullable=True)
    count = Column(Integer, default=0)
    last_seen = Column(DateTime, default=datetime.utcnow)

class PerformanceMetric(Base):
    __tablename__ = "performance_metrics"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    metric_name = Column(String, nullable=False)
    value = Column(Float, nullable=False)
    recorded_at = Column(DateTime, default=datetime.utcnow)

