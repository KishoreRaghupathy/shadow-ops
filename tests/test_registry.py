"""
Tests targeting Contract Registry.
"""

import json
from src.engine.registry import ContractRegistry
from src.engine.generator import ContractGeneratorAgent


def test_registry_lifecycle(db_session) -> None:
    """
    Assert that registry registers, increments versions, diffs, and rolls back contracts correctly.
    """
    registry = ContractRegistry(db_session)
    gen = ContractGeneratorAgent()
    
    # Generate schema v1
    schema_v1 = gen.generate("customer_contract", {"customer_id": "string", "country": "string"})
    
    # 1. Register first version
    v1 = registry.register_contract("customer_contract", schema_v1, "Initial description")
    assert v1.version == 1
    
    contract_rec = registry.get_contract_by_id(v1.contract_id)
    assert contract_rec.name == "customer_contract"
    assert contract_rec.description == "Initial description"
    
    # Registering same schema again should NOT increment version
    v1_dup = registry.register_contract("customer_contract", schema_v1)
    assert v1_dup.version == 1
    assert v1_dup.id == v1.id
    
    # 2. Modify schema and register v2
    schema_v2 = gen.generate("customer_contract", {"customer_id": "string", "country": "string", "signup_date": "datetime"})
    v2 = registry.register_contract("customer_contract", schema_v2, "Added signup date")
    assert v2.version == 2
    
    # Verify history
    history = registry.get_contract_history(contract_rec.id)
    assert len(history) == 2
    assert [h.version for h in history] == [1, 2]
    
    # 3. Compare versions (diff report)
    diff = registry.compare_versions(contract_rec.id, 1, 2)
    assert diff["has_changes"] is True
    assert "signup_date" in diff["added"]
    assert len(diff["removed"]) == 0
    
    # 4. Rollback version
    # Creates version 3 with copy of version 1 schema
    v3 = registry.rollback_contract(contract_rec.id, 1)
    assert v3.version == 3
    
    v3_schema = json.loads(v3.schema_json)
    v3_fields = [f["name"] for f in v3_schema["fields"]]
    assert "signup_date" not in v3_fields
    assert "customer_id" in v3_fields
    
    # 5. Log violation
    violation = registry.log_violation(
        contract_id=contract_rec.id,
        version_id=v2.id,
        violation_type="Enum violation",
        field_name="country",
        expected_value="US",
        actual_value="XX",
        payload_preview='{"country": "XX"}'
    )
    
    assert violation.id is not None
    
    violations_list = registry.get_violations(contract_id=contract_rec.id)
    assert len(violations_list) == 1
    assert violations_list[0].violation_type == "Enum violation"
