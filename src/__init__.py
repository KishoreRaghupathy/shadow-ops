"""
Aegis-Ops Root Package Initialization.

Exposes globally validated configuration settings and the telemetry logger
to ensure clean modular imports across the platform.
"""

from config.settings import logger, settings

__all__ = ["logger", "settings"]
