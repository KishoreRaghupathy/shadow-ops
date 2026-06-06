# src/agents/scoring_engine.py
"""Learning Scoring Engine for Phase 5.
Computes performance metrics from the incident memory and persists them in the
`PerformanceMetric` table. Intended to be invoked after each incident
recovery attempt.
"""

from typing import Dict, Any

from src.memory.repo import record_performance_metric
from src.memory.models import PerformanceMetric

def compute_metrics(db_session, incident_id: str) -> Dict[str, Any]:
    """Calculate a set of performance metrics for a given incident.

    Returns a dictionary of metric_name -> value. The caller can then persist
    them via ``record_performance_metric``.
    """
    # Placeholder logic – replace with real calculations based on your data.
    # For demonstration we compute:
    #   - success_rate (1 if outcome == SUCCESS else 0)
    #   - patch_effectiveness (1 if validation_passed else 0)
    #   - mttr_seconds (as stored)
    from src.memory.repo import get_incident_memory
    inc = get_incident_memory(db_session, incident_id)
    if not inc:
        raise ValueError(f"Incident {incident_id} not found for scoring")

    success_rate = 1.0 if inc.outcome == "SUCCESS" else 0.0
    patch_effectiveness = 1.0 if inc.validation_passed else 0.0
    mttr = float(inc.mttr_seconds or 0)

    metrics = {
        "success_rate": success_rate,
        "patch_effectiveness": patch_effectiveness,
        "mttr_seconds": mttr,
    }

    # Persist each metric.
    for name, value in metrics.items():
        record_performance_metric(db_session, metric_name=name, value=value)

    return metrics
