# src/incident/constants.py
"""Simple constants for incident statuses and recovery modes."""

class IncidentStatus:
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    FAILED = "FAILED"

class RecoveryMode:
    AUTOMATIC = "AUTOMATIC"
    MANUAL = "MANUAL"
