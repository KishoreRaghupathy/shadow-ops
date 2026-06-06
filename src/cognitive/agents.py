"""
LangGraph Agent Nodes for Shadow-Ops.

Defines the individual steps/nodes executed during the Data Contract workflow:
Schema Discovery, Contract Generator, Contract Registry, Validation Agent,
Violation Monitor, and Governance Update.
"""

from typing import Any, Dict, List, Optional, TypedDict
from pydantic import BaseModel

from src.engine.models import ContractSchema, FieldConstraint
from src.engine.generator import ContractGeneratorAgent
from src.engine.registry import ContractRegistry
from src.engine.validator import ContractValidationAgent
from src.engine.database import SessionLocal


# Define State structure for LangGraph
class AgentState(TypedDict):
    """
    Shared state across the contract intelligence workflow nodes.
    """
    contract_name: str
    description: Optional[str]
    raw_schema: Dict[str, str]                # Schema from Discovery: field_name -> type_name
    sample_records: Optional[List[Dict[str, Any]]] # Data sample for profiling
    generated_contract: Optional[Dict[str, Any]] # Serialized ContractSchema
    registered_version_id: Optional[str]
    registered_version_num: Optional[int]
    validation_payload: Optional[List[Dict[str, Any]]] # Payload to test
    validation_report: Optional[Dict[str, Any]]
    violations_logged_count: int
    drift_detected: bool
    drift_report: Optional[Dict[str, Any]]
    governance_logs: List[str]


def schema_discovery_node(state: AgentState) -> Dict[str, Any]:
    """
    Node 1: Schema Discovery.
    Prepares and profiles incoming discovered schemas and raw datasets.
    """
    logs = state.get("governance_logs", [])
    logs.append("Executing Schema Discovery Node...")
    
    # In a real environment, this might query an active database schema catalog.
    raw_schema = state.get("raw_schema") or {}
    sample_records = state.get("sample_records") or []
    
    logs.append(f"Discovered schema has {len(raw_schema)} fields. Sample records: {len(sample_records)}.")
    
    return {
        "raw_schema": raw_schema,
        "sample_records": sample_records,
        "governance_logs": logs
    }


def contract_generator_node(state: AgentState) -> Dict[str, Any]:
    """
    Node 2: Contract Generator.
    Uses ContractGeneratorAgent to infer constraints and assign confidence scores.
    """
    logs = state.get("governance_logs", [])
    logs.append("Executing Contract Generator Node...")
    
    generator = ContractGeneratorAgent()
    contract_schema = generator.generate(
        contract_name=state["contract_name"],
        discovered_schema=state["raw_schema"],
        sample_data=state["sample_records"],
        description=state.get("description")
    )
    
    logs.append(f"Generated contract '{state['contract_name']}' successfully.")
    
    return {
        "generated_contract": contract_schema.model_dump(),
        "governance_logs": logs
    }


def contract_registry_node(state: AgentState) -> Dict[str, Any]:
    """
    Node 3: Contract Registry.
    Registers/versions the generated contract schema into the database.
    """
    logs = state.get("governance_logs", [])
    logs.append("Executing Contract Registry Node...")
    
    contract_dict = state["generated_contract"]
    if not contract_dict:
        logs.append("CRITICAL: No generated contract found to register.")
        return {"governance_logs": logs}
        
    contract_schema = ContractSchema(**contract_dict)
    
    db = SessionLocal()
    try:
        registry = ContractRegistry(db)
        version_rec = registry.register_contract(
            name=state["contract_name"],
            schema_data=contract_schema,
            description=state.get("description")
        )
        version_num = version_rec.version
        version_id = version_rec.id
        logs.append(f"Contract '{state['contract_name']}' registered in DB under version {version_num} (ID: {version_id}).")
    except Exception as e:
        logs.append(f"ERROR registering contract in DB: {str(e)}")
        version_num = None
        version_id = None
    finally:
        db.close()
        
    return {
        "registered_version_num": version_num,
        "registered_version_id": version_id,
        "governance_logs": logs
    }


def validation_agent_node(state: AgentState) -> Dict[str, Any]:
    """
    Node 4: Validation Agent.
    Validates streaming payload or batch file datasets against the active contract.
    """
    logs = state.get("governance_logs", [])
    logs.append("Executing Validation Agent Node...")
    
    payload = state.get("validation_payload")
    contract_dict = state["generated_contract"]
    
    if not payload:
        logs.append("No validation payload provided. Skipping validation step.")
        return {
            "validation_report": {
                "is_valid": True,
                "violations": [],
                "metrics": {"total_records": 0, "total_violations": 0, "violation_rate": 0.0, "health_score": 100.0}
            },
            "governance_logs": logs
        }
        
    if not contract_dict:
        logs.append("ERROR: No contract loaded for validation.")
        return {"governance_logs": logs}

    contract_schema = ContractSchema(**contract_dict)
    validator = ContractValidationAgent()
    
    report = validator.validate_dataset(payload, contract_schema)
    logs.append(f"Validation completed. Is Valid: {report['is_valid']}, Violations Found: {report['metrics']['total_violations']}.")
    
    return {
        "validation_report": report,
        "governance_logs": logs
    }


def violation_monitor_node(state: AgentState) -> Dict[str, Any]:
    """
    Node 5: Violation Monitor.
    Monitors validation results and persists any violations to the database.
    """
    logs = state.get("governance_logs", [])
    logs.append("Executing Violation Monitor Node...")
    
    report = state.get("validation_report")
    version_id = state.get("registered_version_id")
    contract_name = state["contract_name"]
    
    if not report or not report.get("violations"):
        logs.append("No violations detected by monitor.")
        return {
            "violations_logged_count": 0,
            "governance_logs": logs
        }
        
    db = SessionLocal()
    violations_count = 0
    try:
        registry = ContractRegistry(db)
        contract = registry.get_contract_by_name(contract_name)
        
        if contract:
            for v in report["violations"]:
                registry.log_violation(
                    contract_id=contract.id,
                    version_id=version_id,
                    violation_type=v["violation_type"],
                    field_name=v.get("field_name"),
                    expected_value=v.get("expected_value"),
                    actual_value=v.get("actual_value"),
                    payload_preview=v.get("payload_preview")
                )
                violations_count += 1
            logs.append(f"Logged {violations_count} new violations to the database.")
        else:
            logs.append(f"ERROR: Contract '{contract_name}' not found when writing violations.")
    except Exception as e:
        logs.append(f"ERROR saving violations: {str(e)}")
    finally:
        db.close()
        
    return {
        "violations_logged_count": violations_count,
        "governance_logs": logs
    }


def governance_update_node(state: AgentState) -> Dict[str, Any]:
    """
    Node 6: Governance Update.
    Summarizes the cycle results, reports updates, and marks process completed.
    """
    logs = state.get("governance_logs", [])
    logs.append("Executing Governance Update Node...")
    
    version_num = state.get("registered_version_num")
    violations_count = state.get("violations_logged_count", 0)
    
    summary = (
        f"Governance workflow successfully finalized for '{state['contract_name']}'. "
        f"Registered version: {version_num}. Violations logged: {violations_count}."
    )
    logs.append(summary)
    
    return {
        "governance_logs": logs
    }
