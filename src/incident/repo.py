# src/incident/repo.py
"""Repository layer for Incident Memory Store.
Provides CRUD helpers used by FastAPI endpoints and LangGraph agents.
"""

from typing import List, Optional

from sqlalchemy.orm import Session

from src.incident.models import Incident, IncidentAction, IncidentFix, IncidentMemory


def create_incident(
    db: Session,
    incident_id: str,
    severity: str,
    description: Optional[str] = None,
) -> Incident:
    """Create a new incident record.
    Returns the persisted Incident instance.
    """
    incident = Incident(
        incident_id=incident_id,
        severity=severity,
        status="OPEN",
        description=description,
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return incident


def get_incident_by_id(db: Session, incident_id: str) -> Optional[Incident]:
    """Fetch an incident by its business ID (e.g., INC-001)."""
    return db.query(Incident).filter(Incident.incident_id == incident_id).first()


def list_incidents(db: Session, skip: int = 0, limit: int = 100) -> List[Incident]:
    """Return a paginated list of incidents ordered by creation time descending."""
    return (
        db.query(Incident)
        .order_by(Incident.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def update_incident_status(
    db: Session, incident_id: str, status: str, severity: Optional[str] = None
) -> Incident:
    """Update status (and optionally severity) of an incident.
    Raises ValueError if incident not found.
    """
    inc = get_incident_by_id(db, incident_id)
    if not inc:
        raise ValueError(f"Incident {incident_id} not found")
    inc.status = status
    if severity:
        inc.severity = severity
    db.commit()
    db.refresh(inc)
    return inc


def add_incident_action(
    db: Session,
    incident_id: str,
    action_type: str,
    payload: Optional[dict] = None,
) -> IncidentAction:
    """Record an action taken for an incident (e.g., investigation step)."""
    inc = get_incident_by_id(db, incident_id)
    if not inc:
        raise ValueError(f"Incident {incident_id} not found")
    action = IncidentAction(
        incident_id=inc.id,
        action_type=action_type,
        payload=payload,
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    return action


def add_incident_fix(
    db: Session,
    incident_id: str,
    patch_path: str,
    validation_status: str = "PENDING",
) -> IncidentFix:
    """Persist generated patch information for an incident."""
    inc = get_incident_by_id(db, incident_id)
    if not inc:
        raise ValueError(f"Incident {incident_id} not found")
    fix = IncidentFix(
        incident_id=inc.id,
        patch_path=patch_path,
        validation_status=validation_status,
    )
    db.add(fix)
    db.commit()
    db.refresh(fix)
    return fix


def add_incident_memory(
    db: Session,
    incident_id: str,
    root_cause: Optional[str] = None,
    recovery_time_seconds: Optional[int] = None,
    success: bool = False,
    metadata: Optional[dict] = None,
) -> IncidentMemory:
    """Store high‑level memory for an incident after resolution."""
    inc = get_incident_by_id(db, incident_id)
    if not inc:
        raise ValueError(f"Incident {incident_id} not found")
    memory = IncidentMemory(
        incident_id=inc.id,
        root_cause=root_cause,
        recovery_time_seconds=recovery_time_seconds,
        success=success,
        metadata=metadata,
    )
    db.add(memory)
    db.commit()
    db.refresh(memory)
    return memory
