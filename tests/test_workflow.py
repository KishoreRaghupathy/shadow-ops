"""
Tests targeting LangGraph Agent Workflow.
"""

from src.cognitive.workflow import execute_workflow


def test_langgraph_workflow_run(db_session) -> None:
    """
    Assert that the compiled LangGraph StateGraph executes nodes in sequence,
    populates state, registers schemas, validates records, logs violations,
    and updates governance records.
    """
    contract_name = "workflow_test_contract"
    raw_schema = {
        "device_id": "string",
        "temperature": "float",
        "active": "boolean"
    }
    sample_records = [
        {"device_id": "d1", "temperature": 98.6, "active": True},
        {"device_id": "d2", "temperature": 101.2, "active": False},
    ]
    
    # Violations in payload: temperature is string, active is missing
    validation_payload = [
        {"device_id": "d3", "temperature": "hot", "active": True},
        {"device_id": "d4", "temperature": 99.0}  # active missing (required = True by default)
    ]
    
    # Run the workflow using the execution helper
    state = execute_workflow(
        contract_name=contract_name,
        raw_schema=raw_schema,
        sample_records=sample_records,
        validation_payload=validation_payload,
        description="Testing LangGraph integration flow"
    )
    
    # Verify execution output state keys
    assert state["contract_name"] == contract_name
    assert state["registered_version_num"] == 1
    assert state["registered_version_id"] is not None
    
    assert state["generated_contract"] is not None
    assert state["generated_contract"]["contract_name"] == contract_name
    
    # Verify validation report execution and logging
    assert state["validation_report"] is not None
    assert state["validation_report"]["is_valid"] is False
    assert state["violations_logged_count"] == 2
    
    # Verify step logs sequence
    logs = state["governance_logs"]
    assert any("Executing Schema Discovery Node" in l for l in logs)
    assert any("Executing Contract Generator Node" in l for l in logs)
    assert any("Executing Contract Registry Node" in l for l in logs)
    assert any("Executing Validation Agent Node" in l for l in logs)
    assert any("Executing Violation Monitor Node" in l for l in logs)
    assert any("Executing Governance Update Node" in l for l in logs)
    assert any("Governance workflow successfully finalized" in l for l in logs)
