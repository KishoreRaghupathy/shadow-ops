"""
SQLAlchemy and Pydantic Models for Phase 2: Data Contract Intelligence Layer.

Defines the database schema and serialization/deserialization logic for
Contracts, Contract Versions, and Contract Violations.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


# ==============================================================================
# SQLAlchemy DB Models
# ==============================================================================

class Contract(Base):
    """
    Contracts Table. Represents a registered schema contract.
    """
    __tablename__ = "contracts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    # Audit trail fields
    created_by = Column(String(255), nullable=False, default="system")
    updated_by = Column(String(255), nullable=False, default="system")

    # Relationships
    versions = relationship("ContractVersion", back_populates="contract", cascade="all, delete-orphan")
    violations = relationship("ContractViolation", back_populates="contract", cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ContractVersion(Base):
    """
    Contract Versions Table. Retains version history of schemas.
    """
    __tablename__ = "contract_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    contract_id = Column(String(36), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    schema_json = Column(Text, nullable=False)  # Serialized FieldConstraints schema
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    # Audit trail fields
    created_by = Column(String(255), nullable=False, default="system")
    updated_by = Column(String(255), nullable=False, default="system")

    # Relationships
    contract = relationship("Contract", back_populates="versions")
    violations = relationship("ContractViolation", back_populates="version")

    def to_dict(self) -> Dict[str, Any]:
        import json
        return {
            "id": self.id,
            "contract_id": self.contract_id,
            "version": self.version,
            "schema_json": json.loads(self.schema_json) if self.schema_json else {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ContractViolation(Base):
    """
    Contract Violations Table. Records telemetry data for anomalies.
    """
    __tablename__ = "contract_violations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    contract_id = Column(String(36), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    version_id = Column(String(36), ForeignKey("contract_versions.id", ondelete="SET NULL"), nullable=True, index=True)
    violation_type = Column(String(100), nullable=False)  # Missing field, Type mismatch, Range violation, Enum violation, Nullability violation, Duplicate key violation
    field_name = Column(String(255), nullable=True)
    expected_value = Column(Text, nullable=True)
    actual_value = Column(Text, nullable=True)
    payload_preview = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    contract = relationship("Contract", back_populates="violations")
    version = relationship("ContractVersion", back_populates="violations")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "contract_id": self.contract_id,
            "version_id": self.version_id,
            "violation_type": self.violation_type,
            "field_name": self.field_name,
            "expected_value": self.expected_value,
            "actual_value": self.actual_value,
            "payload_preview": self.payload_preview,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ==============================================================================
# Pydantic Schemas
# ==============================================================================

class FieldConstraint(BaseModel):
    """
    Validation constraints for a single schema field.
    """
    name: str = Field(..., description="Name of the schema field")
    type: str = Field(..., description="Data type: string, integer, float, boolean, datetime, json")
    required: bool = Field(default=True, description="Whether the field is mandatory")
    unique: bool = Field(default=False, description="Whether all values in the field must be unique")
    is_primary_key: bool = Field(default=False, description="Whether this is a primary key candidate")
    allowed_values: Optional[List[Any]] = Field(default=None, description="Explicit enum list for allowed values")
    min_value: Optional[float] = Field(default=None, description="Minimum numeric value boundary")
    max_value: Optional[float] = Field(default=None, description="Maximum numeric value boundary")
    confidence_score: float = Field(default=1.0, description="Confidence of inferred constraints (0.0 - 1.0)")


class ContractSchema(BaseModel):
    """
    Complete schema contract representation containing all constraints.
    """
    contract_name: str = Field(..., description="Unique name identifying this contract")
    description: Optional[str] = Field(default=None, description="Optional description of the contract purpose")
    fields: List[FieldConstraint] = Field(default=[], description="List of constraints per field")
    metadata: Dict[str, Any] = Field(default={}, description="Optional metadata (e.g., value distributions, inference logs)")


class ContractCreate(BaseModel):
    """
    Request model for creating/registering a contract.
    """
    name: str
    description: Optional[str] = None
    schema_data: ContractSchema


class ContractUpdate(BaseModel):
    """
    Request model for updating a contract (updating the schema generates a new version).
    """
    description: Optional[str] = None
    schema_data: ContractSchema


class ViolationCreate(BaseModel):
    """
    Telemetry structure for logging contract violations.
    """
    contract_id: str
    version_id: Optional[str] = None
    violation_type: str
    field_name: Optional[str] = None
    expected_value: Optional[str] = None
    actual_value: Optional[str] = None
    payload_preview: Optional[str] = None
