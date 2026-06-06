"""
Tests targeting Drift-to-Contract Synchronizer.
"""

from src.engine.synchronizer import DriftSynchronizer
from src.engine.generator import ContractGeneratorAgent


def test_drift_synchronizer() -> None:
    """
    Assert that synchronizer flags type changes, renames, and additions with correct risk.
    """
    agent = ContractGeneratorAgent()
    sync = DriftSynchronizer()
    
    # Base Contract Schema
    schema = {
        "user_id": "string",
        "email": "string",
        "purchase_cnt": "integer"
    }
    contract = agent.generate("user_contract", schema)
    
    # Test 1: No Drift
    rep_ok = sync.analyze_drift(contract, {"user_id": "string", "email": "string", "purchase_cnt": "integer"})
    assert rep_ok["has_drift"] is False
    assert rep_ok["risk"] == "low"
    
    # Test 2: Addition (Low Risk)
    rep_add = sync.analyze_drift(contract, {
        "user_id": "string",
        "email": "string",
        "purchase_cnt": "integer",
        "signup_ip": "string"
    })
    assert rep_add["has_drift"] is True
    assert rep_add["risk"] == "low"
    assert rep_add["changes"][0]["change_type"] == "added"
    
    # Test 3: Type Mismatch (High Risk)
    rep_type = sync.analyze_drift(contract, {
        "user_id": "string",
        "email": "string",
        "purchase_cnt": "string" # integer -> string
    })
    assert rep_type["has_drift"] is True
    assert rep_type["risk"] == "high"
    assert rep_type["changes"][0]["change_type"] == "type_changed"
    
    # Test 4: Potential Rename (High Risk)
    # 1 removed (user_id), 1 added (customer_uuid) of same type
    rep_rename = sync.analyze_drift(contract, {
        "customer_uuid": "string",
        "email": "string",
        "purchase_cnt": "integer"
    })
    assert rep_rename["has_drift"] is True
    assert rep_rename["risk"] == "high"
    assert rep_rename["change"] == "user_id → customer_uuid"
    assert any(c["change_type"] == "potential_rename" for c in rep_rename["changes"])
    
    # Verify presence of recommendations
    assert len(rep_rename["recommendations"]) > 0
    assert any("CRITICAL" in r for r in rep_rename["recommendations"])
