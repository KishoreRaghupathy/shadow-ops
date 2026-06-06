"""
LangGraph Workflow compiler for Shadow-Ops.

Builds and compiles the StateGraph connecting Schema Discovery,
Contract Generator, Contract Registry, Validation Agent, Violation Monitor,
and Governance Update.
"""

from typing import Any, Dict, List, Optional
from langgraph.graph import StateGraph, END

from src.cognitive.agents import (
    AgentState,
    schema_discovery_node,
    contract_generator_node,
    contract_registry_node,
    validation_agent_node,
    violation_monitor_node,
    governance_update_node
)


def build_contract_workflow():
    """
    Assembles and compiles the StateGraph workflow for contract processing.
    """
    workflow = StateGraph(AgentState)
    
    # Register Nodes
    workflow.add_node("schema_discovery", schema_discovery_node)
    workflow.add_node("contract_generator", contract_generator_node)
    workflow.add_node("contract_registry", contract_registry_node)
    workflow.add_node("validation_agent", validation_agent_node)
    workflow.add_node("violation_monitor", violation_monitor_node)
    workflow.add_node("governance_update", governance_update_node)
    
    # Establish Edges
    workflow.set_entry_point("schema_discovery")
    workflow.add_edge("schema_discovery", "contract_generator")
    workflow.add_edge("contract_generator", "contract_registry")
    workflow.add_edge("contract_registry", "validation_agent")
    workflow.add_edge("validation_agent", "violation_monitor")
    workflow.add_edge("violation_monitor", "governance_update")
    workflow.add_edge("governance_update", END)
    
    return workflow.compile()


# Compile default runnable application instance
contract_workflow_app = build_contract_workflow()


def execute_workflow(
    contract_name: str,
    raw_schema: Dict[str, str],
    sample_records: Optional[List[Dict[str, Any]]] = None,
    validation_payload: Optional[List[Dict[str, Any]]] = None,
    description: Optional[str] = None
) -> Dict[str, Any]:
    """
    Synchronously executes the full contract intelligence workflow.
    
    Returns:
        The final workflow state.
    """
    initial_state: AgentState = {
        "contract_name": contract_name,
        "description": description,
        "raw_schema": raw_schema,
        "sample_records": sample_records,
        "generated_contract": None,
        "registered_version_id": None,
        "registered_version_num": None,
        "validation_payload": validation_payload,
        "validation_report": None,
        "violations_logged_count": 0,
        "drift_detected": False,
        "drift_report": None,
        "governance_logs": []
    }
    
    return contract_workflow_app.invoke(initial_state)
