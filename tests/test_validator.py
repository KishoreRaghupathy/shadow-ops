"""
Tests targeting Contract Validation Agent.
"""

from src.engine.validator import ContractValidationAgent
from src.engine.generator import ContractGeneratorAgent


def test_validator_compliance() -> None:
    """
    Assert that validator correctly identifies all six contract violation categories.
    """
    agent = ContractGeneratorAgent()
    validator = ContractValidationAgent()
    
    # Establish a contract schema with constraints
    schema = {
        "customer_id": "string",
        "age": "integer",
        "purchase_amt": "float",
        "country": "string"
    }
    
    # Statistical samples to derive constraints
    samples = [
        {"customer_id": "c1", "age": 25, "purchase_amt": 10.0, "country": "US"},
        {"customer_id": "c2", "age": 40, "purchase_amt": 50.5, "country": "CA"},
        {"customer_id": "c3", "age": 18, "purchase_amt": 5.0, "country": "US"},
    ]
    
    contract_schema = agent.generate("validation_contract", schema, samples)
    
    # Override constraints to test boundaries
    # Age: min=18, max=100
    age_field = next(f for f in contract_schema.fields if f.name == "age")
    age_field.min_value = 18.0
    age_field.max_value = 100.0
    
    # Country enum: ["US", "CA"]
    country_field = next(f for f in contract_schema.fields if f.name == "country")
    country_field.allowed_values = ["US", "CA"]
    
    # customer_id: required & unique
    cid_field = next(f for f in contract_schema.fields if f.name == "customer_id")
    cid_field.required = True
    cid_field.unique = True
    
    # Reset purchase_amt range bounds to prevent range violations on passing data
    pamt_field = next(f for f in contract_schema.fields if f.name == "purchase_amt")
    pamt_field.min_value = None
    pamt_field.max_value = None
    
    # 1. Test Passing Payload
    passing_data = [
        {"customer_id": "c101", "age": 30, "purchase_amt": 100.0, "country": "US"},
        {"customer_id": "c102", "age": 18, "purchase_amt": 0.0, "country": "CA"}
    ]
    report_pass = validator.validate_dataset(passing_data, contract_schema)
    assert report_pass["is_valid"] is True
    assert len(report_pass["violations"]) == 0
    assert report_pass["metrics"]["health_score"] == 100.0
    assert report_pass["ge_report"]["success"] is True
    
    # 2. Test Violations Payload
    failing_data = [
        # Nullability violation: customer_id is None (required)
        {"customer_id": None, "age": 30, "purchase_amt": 12.0, "country": "US"},
        # Type mismatch: age is 'twenty' (expected integer)
        {"customer_id": "c202", "age": "twenty", "purchase_amt": 50.0, "country": "US"},
        # Range violation: age is 15 (less than 18)
        {"customer_id": "c203", "age": 15, "purchase_amt": 5.0, "country": "US"},
        # Enum violation: country is 'MX' (not in US, CA)
        {"customer_id": "c204", "age": 50, "purchase_amt": 12.5, "country": "MX"},
        # Duplicate key violation: customer_id is duplicated below (and missing field test)
        {"customer_id": "c204", "age": 42, "purchase_amt": 10.0} # country missing (required is False by default if inferred, but let's test missing)
    ]
    
    # Make country required to test Missing field
    country_field.required = True
    
    report_fail = validator.validate_dataset(failing_data, contract_schema)
    assert report_fail["is_valid"] is False
    assert len(report_fail["violations"]) > 0
    
    v_types = [v["violation_type"] for v in report_fail["violations"]]
    
    assert "Nullability violation" in v_types
    assert "Type mismatch" in v_types
    assert "Range violation" in v_types
    assert "Enum violation" in v_types
    assert "Missing field" in v_types
    assert "Duplicate key violation" in v_types
    
    # Verify Great Expectations report structures
    assert report_fail["ge_report"]["success"] is False
    assert report_fail["ge_report"]["statistics"]["evaluated_expectations"] > 0
    assert report_fail["ge_report"]["statistics"]["success_percent"] < 100.0
