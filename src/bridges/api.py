"""
FastAPI REST API Layer for Shadow-Ops.

Exposes endpoints for contract generation, validation, search, retrieval,
violation telemetry auditing, and drift impact reporting.
"""

import json
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from config.settings import logger
from src.engine.database import get_db, init_db
from src.engine.models import ContractSchema, FieldConstraint, ContractCreate, ContractUpdate
from src.engine.generator import ContractGeneratorAgent
from src.engine.registry import ContractRegistry
from src.engine.validator import ContractValidationAgent
from src.engine.synchronizer import DriftSynchronizer

app = FastAPI(
    title="Shadow-Ops Data Contract Intelligence Service",
    description="Enterprise API Layer for autonomous schema profiling, versioning, drift mapping, and validation.",
    version="1.0.0"
)

# Enable CORS for Streamlit dashboard integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include additional routers
from src.graph.router import router as graph_router
from src.nl_cypher.router import router as nl_router

app.include_router(graph_router)
app.include_router(nl_router)


@app.on_event("startup")
def on_startup():
    """
    Initialize database schemas on startup.
    """
    logger.info("Starting Shadow-Ops Contract Service. Initializing database...")
    init_db()


# ==============================================================================
# API Request / Response DTOs
# ==============================================================================

class GenerateRequest(BaseModel):
    contract_name: str = Field(..., example="customer_contract")
    discovered_schema: Dict[str, str] = Field(..., example={"customer_id": "string", "country": "string", "purchase_amt": "float"})
    sample_data: Optional[List[Dict[str, Any]]] = Field(default=None, example=[
        {"customer_id": "cust_101", "country": "US", "purchase_amt": 99.50},
        {"customer_id": "cust_102", "country": "CA", "purchase_amt": 150.00}
    ])
    description: Optional[str] = Field(default=None, example="Customer purchases core transaction stream contract")


class ValidateRequest(BaseModel):
    contract_id: str = Field(..., description="Database ID or contract name to validate against")
    records: List[Dict[str, Any]] = Field(..., description="Batch records or API payload dictionaries to validate")


# ==============================================================================
# Endpoints
# ==============================================================================

@app.post("/contracts/generate", response_model=ContractSchema, status_code=status.HTTP_200_OK)
def generate_contract(payload: GenerateRequest):
    """
    Generates a schema contract with inferred constraints, nullability, uniqueness,
    numeric ranges, allowed enums, and confidence scores.
    """
    try:
        agent = ContractGeneratorAgent()
        contract = agent.generate(
            contract_name=payload.contract_name,
            discovered_schema=payload.discovered_schema,
            sample_data=payload.sample_data,
            description=payload.description
        )
        return contract
    except Exception as e:
        logger.error(f"Error generating contract: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference run failed: {str(e)}"
        )


@app.post("/contracts", status_code=status.HTTP_201_CREATED)
def register_contract(payload: ContractCreate, db: Session = Depends(get_db)):
    """
    Registers a contract definition or versions it if the schema structure has changed.
    """
    try:
        registry = ContractRegistry(db)
        version_rec = registry.register_contract(
            name=payload.name,
            schema_data=payload.schema_data,
            description=payload.description
        )
        return {
            "message": "Contract registered successfully",
            "contract_id": version_rec.contract_id,
            "version_id": version_rec.id,
            "version": version_rec.version
        }
    except Exception as e:
        logger.error(f"Error registering contract: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database write failed: {str(e)}"
        )


@app.get("/contracts")
def get_contracts(query: Optional[str] = Query(default=None, description="Search query string"), db: Session = Depends(get_db)):
    """
    Retrieves and searches registered contracts inventory list.
    """
    registry = ContractRegistry(db)
    contracts = registry.search_contracts(query)
    
    results = []
    for c in contracts:
        latest_version = registry.get_latest_version(c.id)
        latest_schema = json.loads(latest_version.schema_json) if latest_version else None
        
        results.append({
            "id": c.id,
            "name": c.name,
            "description": c.description,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            "latest_version": latest_version.version if latest_version else None,
            "schema": latest_schema
        })
    return results


@app.get("/contracts/{id}")
def get_contract_by_id_or_name(id: str, db: Session = Depends(get_db)):
    """
    Retrieves a single contract's detailed record including active version and schema.
    """
    registry = ContractRegistry(db)
    # Check if id matches UUID or name
    contract = registry.get_contract_by_id(id)
    if not contract:
        contract = registry.get_contract_by_name(id)
        
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract '{id}' not found in registry."
        )
        
    latest_version = registry.get_latest_version(contract.id)
    history = registry.get_contract_history(contract.id)
    
    latest_schema = None
    if latest_version:
        latest_schema = json.loads(latest_version.schema_json)

    return {
        "id": contract.id,
        "name": contract.name,
        "description": contract.description,
        "created_at": contract.created_at.isoformat() if contract.created_at else None,
        "updated_at": contract.updated_at.isoformat() if contract.updated_at else None,
        "latest_version": latest_version.version if latest_version else None,
        "latest_version_id": latest_version.id if latest_version else None,
        "schema": latest_schema,
        "history": [
            {
                "version_id": h.id,
                "version": h.version,
                "created_at": h.created_at.isoformat()
            } for h in history
        ]
    }


@app.post("/contracts/{id}/rollback")
def rollback_contract_version(id: str, target_version: int, db: Session = Depends(get_db)):
    """
    Executes a safe rollback of a contract schema to a target past version.
    Creates a new version containing the schema of the targeted past version.
    """
    registry = ContractRegistry(db)
    contract = registry.get_contract_by_id(id) or registry.get_contract_by_name(id)
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract '{id}' not found."
        )
        
    try:
        new_version = registry.rollback_contract(contract.id, target_version)
        return {
            "message": f"Successfully rolled back contract '{contract.name}' to version {target_version}",
            "new_version": new_version.version,
            "version_id": new_version.id
        }
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/contracts/{id}/diff")
def get_version_diff(id: str, v1: int, v2: int, db: Session = Depends(get_db)):
    """
    Generates a structural schema diff comparing two versions of a contract.
    """
    registry = ContractRegistry(db)
    contract = registry.get_contract_by_id(id) or registry.get_contract_by_name(id)
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Contract '{id}' not found.")
        
    try:
        diff_report = registry.compare_versions(contract.id, v1, v2)
        return diff_report
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.post("/contracts/validate")
def validate_payload(payload: ValidateRequest, db: Session = Depends(get_db)):
    """
    Validates a record payload batch against the selected contract.
    Auto-registers any validation violations in the database.
    """
    registry = ContractRegistry(db)
    
    # Resolve contract by ID or Name
    contract = registry.get_contract_by_id(payload.contract_id)
    if not contract:
        contract = registry.get_contract_by_name(payload.contract_id)
        
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract '{payload.contract_id}' not found."
        )

    latest_version = registry.get_latest_version(contract.id)
    if not latest_version:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Contract '{contract.name}' exists but has no registered versions."
        )

    # Decode target contract schema structure
    schema_dict = json.loads(latest_version.schema_json)
    contract_schema = ContractSchema(**schema_dict)

    # Perform validation
    validator = ContractValidationAgent()
    report = validator.validate_dataset(payload.records, contract_schema)

    # Persist violations if found
    violations_logged = 0
    if report["violations"]:
        for v in report["violations"]:
            registry.log_violation(
                contract_id=contract.id,
                version_id=latest_version.id,
                violation_type=v["violation_type"],
                field_name=v.get("field_name"),
                expected_value=v.get("expected_value"),
                actual_value=v.get("actual_value"),
                payload_preview=v.get("payload_preview")
            )
            violations_logged += 1

    return {
        "contract_name": contract.name,
        "contract_id": contract.id,
        "version": latest_version.version,
        "version_id": latest_version.id,
        "is_valid": report["is_valid"],
        "violations_logged": violations_logged,
        "metrics": report["metrics"],
        "violations": report["violations"],
        "ge_report": report["ge_report"]
    }


@app.get("/violations")
def get_violations(
    contract_id: Optional[str] = Query(default=None, description="Filter by contract ID"),
    violation_type: Optional[str] = Query(default=None, description="Filter by violation type"),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """
    Audits and queries logged validation violations from the database.
    """
    registry = ContractRegistry(db)
    violations = registry.get_violations(contract_id=contract_id, violation_type=violation_type, limit=limit)
    return [v.to_dict() for v in violations]


@app.get("/drift-report")
def get_drift_report(
    contract_id: str = Query(..., description="Target Contract name or ID"),
    discovered_schema: str = Query(..., description="Newly discovered schema serialized as JSON"),
    db: Session = Depends(get_db)
):
    """
    Performs drift analysis between an active contract schema and a newly discovered schema.
    
    discovered_schema parameter should be a JSON string like:
    {"customer_id": "string", "country": "string"}
    """
    registry = ContractRegistry(db)
    contract = registry.get_contract_by_id(contract_id) or registry.get_contract_by_name(contract_id)
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract '{contract_id}' not found."
        )

    latest_version = registry.get_latest_version(contract.id)
    if not latest_version:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Contract '{contract.name}' has no active version to run drift checks against."
        )

    # Parse inputs
    try:
        schema_dict = json.loads(latest_version.schema_json)
        contract_schema = ContractSchema(**schema_dict)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error parsing registered contract version schema: {str(e)}"
        )

    try:
        parsed_discovered_schema = json.loads(discovered_schema)
        if not isinstance(parsed_discovered_schema, dict):
            raise ValueError()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="discovered_schema must be a valid serialized JSON object of field_name -> type_name pairs."
        )

    synchronizer = DriftSynchronizer()
    report = synchronizer.analyze_drift(
        contract=contract_schema,
        discovered_schema=parsed_discovered_schema,
        affected_contracts_count=4 # Standard sample impact count
    )

    return report
