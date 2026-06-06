# src/agents/pattern_detector.py
"""Failure Pattern Detector Agent.
Scans the incident memory for recurring root‑cause signatures and updates the
`RecoveryPattern` table. Intended to run periodically (e.g., via a LangGraph
node or a scheduled background task).
"""

from datetime import datetime, timedelta
from typing import List

from sqlalchemy.orm import Session

from src.memory.models import IncidentMemory, RecoveryPattern
from src.memory.repo import get_incident_memory, list_incident_memory

# Simple heuristic: any root cause that appears more than `MIN_OCCURRENCES`
# within the last `WINDOW_DAYS` is considered a pattern.
MIN_OCCURRENCES = int(os.getenv("PATTERN_MIN_OCCURRENCES", "3"))
WINDOW_DAYS = int(os.getenv("PATTERN_WINDOW_DAYS", "30"))

def _detect_patterns(db: Session) -> List[RecoveryPattern]:
    """Detect recurring failure patterns and upsert them.
    Returns a list of `RecoveryPattern` objects that were created or updated.
    """
    cutoff = datetime.utcnow() - timedelta(days=WINDOW_DAYS)
    # Retrieve recent incidents with a root cause.
    recent = (
        db.query(IncidentMemory)
        .filter(IncidentMemory.created_at >= cutoff)
        .filter(IncidentMemory.root_cause.isnot(None))
        .all()
    )
    # Count occurrences of each root cause string.
    counter = {}
    for inc in recent:
        rc = inc.root_cause.strip().lower()
        counter[rc] = counter.get(rc, 0) + 1
    patterns = []
    for rc, count in counter.items():
        if count >= MIN_OCCURRENCES:
            # Upsert a RecoveryPattern entry.
            pattern = (
                db.query(RecoveryPattern)
                .filter(RecoveryPattern.pattern_name == rc)
                .first()
            )
            if pattern:
                pattern.occurrences = count
                pattern.risk_level = "HIGH" if count > 10 else "MEDIUM"
            else:
                pattern = RecoveryPattern(
                    pattern_name=rc,
                    description=f"Detected {count} occurrences of '{rc}' in the last {WINDOW_DAYS} days.",
                    occurrences=count,
                    risk_level="MEDIUM",
                )
                db.add(pattern)
            db.commit()
            db.refresh(pattern)
            patterns.append(pattern)
    return patterns

# Public entry point used by the workflow.
def run_pattern_detection(db: Session) -> List[RecoveryPattern]:
    return _detect_patterns(db)
