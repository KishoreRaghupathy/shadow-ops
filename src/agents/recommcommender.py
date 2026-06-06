# src/agents/recommcommender.py
"""Recommendation Agent for Phase 5.
Given a new incident ID, it retrieves the incident record, creates an embedding (placeholder),
searches Qdrant for similar past incidents, ranks them by similarity and outcome,
and returns a recommendation payload.
"""

import os
from typing import List, Dict, Any

from qdrant_client.http.models import Filter as QdrantFilter, Must, MatchValue

from src.memory.repo import get_incident_memory, list_incident_memory
from src.memory.models import IncidentMemory
from src.vector.qdrant_client import upsert_vectors, search_similar, ensure_collection

# Placeholder embedding function – replace with actual model later
def _embed_text(text: str) -> List[float]:
    # For now, return a deterministic dummy vector (e.g., hash‑based) of length 768.
    # In production you would call a sentence‑transformer or Ollama LLM.
    import hashlib
    import struct
    h = hashlib.sha256(text.encode("utf-8")).digest()
    # Convert first 768/4=192 32‑bit floats from hash (repeat if needed)
    vec = list(struct.unpack("%df" % (len(h) // 4), h))
    # Pad / truncate to 768 dimensions
    target_dim = 768
    if len(vec) < target_dim:
        vec = (vec * (target_dim // len(vec) + 1))[:target_dim]
    else:
        vec = vec[:target_dim]
    return vec

async def recommend_fix(db_session, incident_id: str, top_k: int = 5) -> Dict[str, Any]:
    """Generate a repair recommendation for ``incident_id``.
    Returns a dict compatible with the spec:
    {
        "recommended_fix": "adapter_v2_patch",
        "confidence": 0.94,
        "similar_incidents": 8,
    }
    """
    # Load the incident record
    incident: IncidentMemory = get_incident_memory(db_session, incident_id)
    if not incident:
        raise ValueError(f"Incident {incident_id} not found")

    # Build a textual representation for embedding (root cause + type)
    text = f"{incident.incident_type}: {incident.root_cause or ''}"
    query_vec = _embed_text(text)

    # Search Qdrant for similar incidents
    results = search_similar(query_vec, limit=top_k)
    similar_ids = [int(hit_id) for hit_id, _, _ in results]

    # Pull full incident records for ranking (here we just count successes)
    similar_records = (
        db_session.query(IncidentMemory)
        .filter(IncidentMemory.id.in_(similar_ids))
        .all()
    )

    # Simple heuristic: pick the most frequent successful recovery action
    action_counter = {}
    success_count = 0
    for rec in similar_records:
        if rec.outcome == "SUCCESS" and rec.recovery_action:
            success_count += 1
            action_counter[rec.recovery_action] = action_counter.get(rec.recovery_action, 0) + 1

    # Choose the most common successful action
    recommended_fix = None
    if action_counter:
        recommended_fix = max(action_counter.items(), key=lambda kv: kv[1])[0]

    # Confidence as proportion of successful similar incidents
    confidence = success_count / max(len(similar_records), 1)

    return {
        "recommended_fix": recommended_fix or "" ,
        "confidence": round(confidence, 2),
        "similar_incidents": len(similar_records),
    }

# Helper to index a new incident into Qdrant – called after incident persistence
def index_incident(db_session, incident_id: str) -> None:
    incident = get_incident_memory(db_session, incident_id)
    if not incident:
        return
    text = f"{incident.incident_type}: {incident.root_cause or ''}"
    vec = _embed_text(text)
    # Use the IncidentMemory.id (UUID) as integer hash for Qdrant ID
    # Convert UUID to int safely
    try:
        q_id = int(incident.id.int)  # sqlalchemy UUID stores .int attribute
    except Exception:
        q_id = int(hash(str(incident.id)))
    upsert_vectors([q_id], [vec], payload=[{"incident_id": incident.incident_id}])
