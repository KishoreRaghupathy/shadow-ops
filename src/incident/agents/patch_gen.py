# src/incident/agents/patch_gen.py
"""Patch Generation Agent.
Generates remediation code using Ollama Llama 3.1.
Returns the file path of the generated patch and a flag.
"""

import os
import uuid
from typing import Dict, Any
import httpx

from ..constants import IncidentStatus

PATCH_DIR = "tmp/patches"

async def _generate_patch(prompt: str) -> str:
    """Call Ollama to generate Python code.
    Returns the generated source as a string.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "http://localhost:11434/api/generate",
            json={"model": "llama3.1", "prompt": prompt},
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        # Ollama returns a stream of tokens; concatenate "response" fields.
        return "".join(chunk.get("response", "") for chunk in data.get("done", []))

async def run(state: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a remediation patch based on the root cause.
    Expects ``state`` to contain ``incident_id`` and ``root_cause``.
    Writes a ``.py`` file under ``tmp/patches/<incident_id>/``.
    Updates ``state`` with ``patch_path`` and ``patch_generated``.
    """
    incident_id = state.get("incident_id")
    root_cause = state.get("root_cause")
    if not incident_id or not root_cause:
        raise ValueError("incident_id and root_cause required")

    # Simple prompt template
    prompt = (
        f"You are an AIOps assistant. Generate a Python adapter that fixes the following issue: {root_cause}. "
        "Provide only the code without any explanations."
    )
    try:
        code = await _generate_patch(prompt)
    except Exception as e:
        # On failure, mark as not generated
        state.update({"patch_generated": False, "error": str(e)})
        return state

    # Ensure directory exists
    incident_dir = os.path.join(PATCH_DIR, incident_id)
    os.makedirs(incident_dir, exist_ok=True)
    patch_path = os.path.join(incident_dir, "adapter.py")
    with open(patch_path, "w", encoding="utf-8") as f:
        f.write(code)

    state.update({"patch_path": patch_path, "patch_generated": True})
    return state
