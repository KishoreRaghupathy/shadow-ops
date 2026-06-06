import json
from typing import List, Dict, Any

from src.memory.repo import get_incident_memory_by_id
from src.vector.qdrant_client import QdrantClientWrapper
from src.memory.models import IncidentMemory

class RecommendationAgent:
    """Agent to recommend a recovery action based on historical incidents.

    Workflow:
        1. Retrieve the incident record to obtain any textual context (type, logs, etc.).
        2. Generate an embedding for the context (placeholder – you can plug in any embedding model).
        3. Use Qdrant to perform a similarity search for the *k* nearest incidents.
        4. Rank the retrieved incidents by a simple scoring function that favours
           successful outcomes and recent timestamps.
        5. Return the most promising fix, its confidence score, and the number of
           similar incidents that contributed to the recommendation.
    """

    def __init__(self, qdrant_host: str = "qdrant", qdrant_port: int = 6333):
        self.qdrant = QdrantClientWrapper(host=qdrant_host, port=qdrant_port)

    def _embed_text(self, text: str) -> List[float]:
        """Placeholder embedding function.

        In production you would replace this with a call to a sentence‑transformer
        model or the Ollama LLM's embedding endpoint.
        """
        # Simple deterministic dummy embedding – length‑based for illustration.
        # Replace with real embeddings for a production system.
        return [float(len(text))] * 128

    def recommend(self, incident_id: str, top_k: int = 5) -> Dict[str, Any]:
        """Return a recommendation for the given incident.

        Returns a dict with keys:
            - recommended_fix (str)
            - confidence (float 0‑1)
            - similar_incidents (int)
            - details (list of dicts with incident_id and outcome)
        """
        # Load incident meta (could include logs, error messages, etc.)
        incident: IncidentMemory = get_incident_memory_by_id(incident_id)
        if not incident:
            raise ValueError(f"Incident {incident_id} not found in memory")

        # Build a textual representation for embedding.
        text_payload = json.dumps({
            "type": incident.incident_type,
            "root_cause": incident.root_cause or "",
            "recovery_action": incident.recovery_action or "",
        })
        query_vector = self._embed_text(text_payload)

        # Perform similarity search in Qdrant.
        results = self.qdrant.search(collection_name="incident_vectors", query_vector=query_vector, top=top_k)
        if not results:
            # No similar incidents – fallback to a generic suggestion.
            return {
                "recommended_fix": "manual_review",
                "confidence": 0.0,
                "similar_incidents": 0,
                "details": [],
            }

        # Rank by a simple score: success outcome weighted higher + recency.
        scored = []
        for hit in results:
            payload = hit.payload
            outcome = payload.get("outcome", "FAILURE")
            success_score = 1.0 if outcome.upper() == "SUCCESS" else 0.0
            # Use stored similarity score (cosine distance) – Qdrant returns "score" (higher is better).
            similarity = hit.score
            total_score = 0.7 * success_score + 0.3 * similarity
            scored.append((total_score, payload))
        scored.sort(key=lambda x: x[0], reverse=True)
        best = scored[0][1]

        # Confidence is normalized between 0‑1 based on the total_score of the top hit.
        confidence = min(1.0, max(0.0, scored[0][0]))

        return {
            "recommended_fix": best.get("patch_path", "manual_review"),
            "confidence": confidence,
            "similar_incidents": len(results),
            "details": [
                {"incident_id": p.get("incident_id"), "outcome": p.get("outcome")} for _, p in scored
            ],
        }
