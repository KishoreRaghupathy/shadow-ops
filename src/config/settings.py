import os
from pydantic import BaseSettings, Field, validator
from typing import Optional

class Settings(BaseSettings):
    # Core settings (already present from Phase 2)
    POSTGRES_HOST: str = Field(default="localhost")
    POSTGRES_PORT: int = Field(default=5432)
    POSTGRES_DB: str = Field(default="shadow_ops")
    POSTGRES_USER: str = Field(default="postgres")
    POSTGRES_PASSWORD: str = Field(default="postgres")

    # Neo4j settings
    NEO4J_URI: str = Field(default="bolt://neo4j:7687")
    NEO4J_USER: str = Field(default="neo4j")
    NEO4J_PASSWORD: str = Field(default="neo4j")

    # Redis settings
    REDIS_URL: str = Field(default="redis://localhost:6379/0")

    # JWT / OAuth2 settings
    JWT_SECRET_KEY: str = Field(default="change_this_secret")
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60)

    # NL‑to‑Cypher provider configuration
    NL_CYPHER_PROVIDER: str = Field(default="ollama")  # options: ollama, openai, groq, anthropic, cohere
    OLLAMA_BASE_URL: str = Field(default="http://localhost:11434")
    # Add other provider keys as needed (e.g., OPENAI_API_KEY)

    class Config:
        env_file = ".env"
        case_sensitive = False

    @validator("NEO4J_URI")
    def validate_neo4j_uri(cls, v):
        if not v.startswith("bolt://"):
            raise ValueError("NEO4J_URI must start with bolt://")
        return v

settings = Settings()
