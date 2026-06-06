import uuid
from typing import Dict
from src.incident.repo import IncidentRepo

class LogAnalysisAgent:
    """Parse raw logs and extract a root error signature with confidence.

    Expected input (state) keys:
        - incident_id: str
        - raw_logs: str | list[str]
    Output (state) updates:
        - root_error: str
        - confidence: float (0.0-1.0)
    """
    def __init__(self):
        self.repo = IncidentRepo()

    async def run(self, state: Dict) -> Dict:
        logs = state.get("raw_logs")
        if not logs:
            return {"root_error": None, "confidence": 0.0}
        if isinstance(logs, list):
            logs = "\n".join(logs)
        # Simple heuristic: look for lines containing the word "error" or "exception"
        error_lines = [ln for ln in logs.splitlines() if "error" in ln.lower() or "exception" in ln.lower()]
        if not error_lines:
            return {"root_error": None, "confidence": 0.0}
        # Pick the most frequent phrase (naïve)
        from collections import Counter
        phrases = [ln.strip() for ln in error_lines]
        most_common, count = Counter(phrases).most_common(1)[0]
        confidence = min(1.0, count / max(len(error_lines), 1))
        # Update incident record with extracted info
        self.repo.update_incident(state["incident_id"], {"root_error": most_common, "confidence": confidence})
        return {"root_error": most_common, "confidence": confidence}
