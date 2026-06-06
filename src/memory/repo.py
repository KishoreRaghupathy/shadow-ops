# src/memory/repo.py
"""Repository layer for the Adaptive Learning Memory.
Provides CRUD helpers for IncidentMemory, RecoveryPattern, FailureSignature,
and PerformanceMetric.
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from .models import IncidentMemory, RecoveryPattern, FailureSignature, PerformanceMetric

# ------------------------------- IncidentMemory -------------------------------

def create_incident_memory(db: Session, *, incident_id: str, incident_type: str,
                          root_cause: Optional[str] = None,
                          recovery_action: Optional[str] = None,
                          patch_path: Optional[str] = None,
                          validation_passed: Optional[bool] = None,
                          outcome: Optional[str] = None,
                          mttr_seconds: Optional[int] = None,
                          extra: Optional[dict] = None) -> IncidentMemory:
    """Insert a new IncidentMemory record.
    """
    obj = IncidentMemory(
        incident_id=incident_id,
        incident_type=incident_type,
        root_cause=root_cause,
        recovery_action=recovery_action,
        patch_path=patch_path,
        validation_passed=validation_passed,
        outcome=outcome,
        mttr_seconds=mttr_seconds,
        extra=extra,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def get_incident_memory(db: Session, incident_id: str) -> Optional[IncidentMemory]:
    return db.query(IncidentMemory).filter(IncidentMemory.incident_id == incident_id).first()


def list_incident_memory(db: Session, skip: int = 0, limit: int = 100) -> List[IncidentMemory]:
    return db.query(IncidentMemory).offset(skip).limit(limit).all()

# ------------------------------- RecoveryPattern ------------------------------

def upsert_recovery_pattern(db: Session, *, pattern_name: str, description: Optional[str] = None,
                             risk_level: str = "LOW") -> RecoveryPattern:
    obj = db.query(RecoveryPattern).filter(RecoveryPattern.pattern_name == pattern_name).first()
    if obj:
        obj.occurrences += 1
        if description:
            obj.description = description
        obj.risk_level = risk_level
    else:
        obj = RecoveryPattern(
            pattern_name=pattern_name,
            description=description,
            occurrences=1,
            risk_level=risk_level,
        )
        db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

def get_recovery_patterns(db: Session, limit: int = 100) -> List[RecoveryPattern]:
    return db.query(RecoveryPattern).order_by(RecoveryPattern.occurrences.desc()).limit(limit).all()

# ------------------------------- FailureSignature ------------------------------

def upsert_failure_signature(db: Session, *, signature: str, description: Optional[str] = None) -> FailureSignature:
    obj = db.query(FailureSignature).filter(FailureSignature.signature == signature).first()
    if obj:
        obj.count += 1
        obj.last_seen = func.now()
        if description:
            obj.description = description
    else:
        obj = FailureSignature(
            signature=signature,
            description=description,
            count=1,
        )
        db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

def list_failure_signatures(db: Session, limit: int = 100) -> List[FailureSignature]:
    return db.query(FailureSignature).order_by(FailureSignature.count.desc()).limit(limit).all()

# ------------------------------- PerformanceMetric ------------------------------

def record_performance_metric(db: Session, *, metric_name: str, value: float) -> PerformanceMetric:
    metric = PerformanceMetric(metric_name=metric_name, value=value)
    db.add(metric)
    db.commit()
    db.refresh(metric)
    return metric

def get_recent_metrics(db: Session, metric_name: str, limit: int = 10) -> List[PerformanceMetric]:
    return (
        db.query(PerformanceMetric)
        .filter(PerformanceMetric.metric_name == metric_name)
        .order_by(PerformanceMetric.recorded_at.desc())
        .limit(limit)
        .all()
    )
