import os
import httpx
from abc import ABC, abstractmethod
from typing import Any, Dict

class NLProvider(ABC):
    """Abstract base class for NL‑to‑Cypher providers."""

    @abstractmethod
    async def to_cypher(self, prompt: str) -> str:
        """Convert a natural‑language prompt to a Cypher query string."""
        raise NotImplementedError

class OllamaProvider(NLProvider):
    """Ollama implementation – calls a locally‑running Llama model.
    Expects ``OLLAMA_BASE_URL`` env var (default ``http://localhost:11434``).
    """

    def __init__(self):
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=30)

    async def to_cypher(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "prompt": f"Translate the following natural‑language request into a Cypher query for a Neo4j knowledge graph. Return only the Cypher statement.\n\n{prompt}",
            "stream": False,
        }
        response = await self.client.post("/api/generate", json=payload)
        response.raise_for_status()
        data = response.json()
        # Ollama returns a 'response' field containing the generated text
        cypher = data.get("response", "").strip()
        # Ensure the text ends without commentary – keep only the query up to first semicolon
        if ";" in cypher:
            cypher = cypher.split(";")[0] + ";"
        return cypher

# Helper to instantiate the configured provider based on settings
def get_provider() -> NLProvider:
    from config.settings import settings
    provider_name = settings.NL_CYPHER_PROVIDER.lower()
    if provider_name == "ollama":
        return OllamaProvider()
    # Extend with additional providers (OpenAI, Groq, etc.) as needed
    raise ValueError(f"Unsupported NL‑to‑Cypher provider: {provider_name}")
