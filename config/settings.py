"""
Aegis-Ops Configuration and Structured Logging Subsystem.

Implements robust configuration parsing via Pydantic Settings,
environment validation, and structured cloud-ready logging outputs.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict

from pydantic import SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class JSONFormatter(logging.Formatter):
    """
    Structured JSON formatter for Aegis-Ops log records.
    
    Transforms log telemetry into standardized JSON objects with keys:
    - timestamp (ISO UTC format)
    - level (Logging level name)
    - module (Source file module name)
    - function (Function name where log was emitted)
    - message (The formatted log message)
    - exception (Gracefully serialized exception stack trace if available)
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "module": record.module,
            "function": record.funcName,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data)


def _log_fatal_error(message: str, exc_info: Any = None) -> None:
    """
    Fallback stdout/stderr logging mechanism.
    
    Used when the main application logger cannot be configured due to 
    validation failure or startup runtime exception.
    """
    error_data: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "level": "CRITICAL",
        "module": "settings",
        "function": "<module>",
        "message": message,
    }
    if exc_info:
        import traceback
        error_data["exception"] = "".join(traceback.format_exception(*exc_info))
    
    sys.stderr.write(json.dumps(error_data) + "\n")
    sys.stderr.flush()


class Settings(BaseSettings):
    """
    Immutable Configuration Boundary for Aegis-Ops.
    
    Validates mandatory variables and provides defaults for optional settings.
    Integrates automatically with environment variables and local .env file.
    """

    ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    
    # Mandatory secrets and tokens (properly type-hinted and masked in standard serialization)
    GROQ_API_KEY: SecretStr
    NOTION_TOKEN: SecretStr
    NOTION_DATABASE_ID: str
    
    # Database and Integration configuration
    DATABASE_URL: str = "sqlite:///./shadow_ops.db"
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    
    # Platform tuning parameters
    MAX_CONCURRENT_PROBES: int = 10
    TIMEOUT_SECONDS: int = 30

    # Auto-load variables from the environment and optional local .env file
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """
        Validate and standardize the logging level.
        """
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper_v = v.upper()
        if upper_v not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of {valid_levels}")
        return upper_v


# Fail-fast instantiation of environment configurations
try:
    settings = Settings()
except ValidationError as val_err:
    _log_fatal_error(
        f"Aegis-Ops environment validation failed. Missing or malformed configurations: {val_err.errors()}",
        sys.exc_info()
    )
    raise SystemExit(1) from val_err
except Exception as err:
    _log_fatal_error(
        f"Aegis-Ops system startup failed due to configuration initialization error: {str(err)}",
        sys.exc_info()
    )
    raise SystemExit(1) from err


# Initialize the global exportable logger
logger = logging.getLogger("aegis_ops")
logger.setLevel(settings.LOG_LEVEL.upper())

# Prevent duplicate handlers if settings.py is imported multiple times
if not logger.handlers:
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(JSONFormatter())
    logger.addHandler(stdout_handler)

# Disable propagation to the root logger to ensure clean, controlled outputs
logger.propagate = False
