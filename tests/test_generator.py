"""
Tests targeting Contract Generator Agent.
"""

from src.engine.generator import ContractGeneratorAgent


def test_generator_only_schema() -> None:
    """
    Assert that generator successfully infers PK and enums from schema only heuristics.
    """
    agent = ContractGeneratorAgent()
    schema = {
        "customer_id": "string",
        "country": "string",
        "purchase_amt": "float"
    }
    
    contract = agent.generate("test_contract", schema)
    
    assert contract.contract_name == "test_contract"
    assert len(contract.fields) == 3
    
    # Assert primary key inference
    pk_field = next(f for f in contract.fields if f.name == "customer_id")
    assert pk_field.is_primary_key is True
    assert pk_field.unique is True
    assert pk_field.confidence_score == 0.75
    
    # Assert enum field heuristic
    enum_field = next(f for f in contract.fields if f.name == "country")
    assert enum_field.allowed_values == []
    assert enum_field.confidence_score == 0.60


def test_generator_with_samples() -> None:
    """
    Assert statistical profile inference works on complete datasets.
    """
    agent = ContractGeneratorAgent()
    schema = {
        "user_id": "string",
        "status": "string",
        "score": "integer",
        "bonus": "float"
    }
    samples = [
        {"user_id": "u1", "status": "active", "score": 90, "bonus": 5.5},
        {"user_id": "u2", "status": "inactive", "score": 85, "bonus": None},
        {"user_id": "u3", "status": "active", "score": 100, "bonus": 10.0},
        {"user_id": "u4", "status": "active", "score": 50, "bonus": 0.0},
    ]
    
    contract = agent.generate("test_samples", schema, samples)
    
    # Verify primary key candidate
    pk = next(f for f in contract.fields if f.name == "user_id")
    assert pk.is_primary_key is True
    assert pk.unique is True
    assert pk.required is True
    
    # Verify nullability detection
    status = next(f for f in contract.fields if f.name == "status")
    assert status.required is True  # no nulls in status
    
    bonus = next(f for f in contract.fields if f.name == "bonus")
    assert bonus.required is False  # contains None/null
    
    # Verify ranges
    score = next(f for f in contract.fields if f.name == "score")
    assert score.min_value == 50.0
    assert score.max_value == 100.0
    
    # Verify enum candidate
    assert set(status.allowed_values) == {"active", "inactive"}
    
    # Verify metadata distributions
    assert "distributions" in contract.metadata
    assert "score" in contract.metadata["distributions"]
    assert contract.metadata["distributions"]["score"]["mean"] == 81.25
