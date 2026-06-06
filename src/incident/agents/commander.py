import uuid
from datetime import datetime
from typing import Dict, Any

from ..repo import create_incident
from ..models import IncidentStatus

def run(state: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new incident record and enrich the workflow state.

    Expected ``state`` keys:
        - ``event``: dict with ``type`` (str) and ``severity`` (str) fields.
        - optional ``metadata``: additional dict.
    Returns updated state containing ``incident_id``, ``status`` and ``created_at``.
    """
    event = state.get("event", {})
    incident_type = event.get("type", "UNKNOWN")
    severity = event.get("severity", "MEDIUM")
    metadata = state.get("metadata", {})

    incident_id = f"INC-{uuid.uuid4().hex[:8].upper()}"
    created_at = datetime.utcnow()

    # Persist incident using repo helper (requires a DB session later in the workflow)
    # Here we just store the identifiers in state; DB insertion will be done by a later step.
    state.update({
        "incident_id": incident_id,
        "incident_type": incident_type,
        "severity": severity,
        "metadata": metadata,
        "status": IncidentStatus.INVESTIGATING,
        "created_at": created_at.isoformat(),
    })
    return state
