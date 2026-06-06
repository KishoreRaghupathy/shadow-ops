"""
Tests targeting REST API endpoints.
"""

import json
from fastapi.testclient import TestClient
from src.bridges.api import app


def test_api_endpoints(db_session) -> None:
    """
    Assert FastAPI endpoint behaviors using the TestClient lifecycle.
    """
    # Use context manager to trigger startup/shutdown events
    with TestClient(app) as client:
        # 1. Test POST /contracts/generate
        gen_payload = {
            "contract_name": "api_test_contract",
            "discovered_schema": {
                "user_id": "string",
                "score": "integer",
                "premium": "boolean"
            },
            "sample_data": [
                {"user_id": "u101", "score": 90, "premium": True},
                {"user_id": "u102", "score": 100, "premium": False}
            ],
            "description": "Generated via API client testing"
        }
        
        response = client.post("/contracts/generate", json=gen_payload)
        assert response.status_code == 200
        contract_schema = response.json()
        assert contract_schema["contract_name"] == "api_test_contract"
        assert len(contract_schema["fields"]) == 3
        
        # Clear range and enum boundaries to isolate only the type mismatch test
        for field in contract_schema["fields"]:
            field["min_value"] = None
            field["max_value"] = None
            field["allowed_values"] = None
        
        # 2. Test POST /contracts to register it in DB
        reg_payload = {
            "name": "api_test_contract",
            "description": "Registered via API client",
            "schema_data": contract_schema
        }
        response = client.post("/contracts", json=reg_payload)
        assert response.status_code == 201
        reg_res = response.json()
        assert reg_res["contract_id"] is not None
        assert reg_res["version"] == 1
        
        contract_uuid = reg_res["contract_id"]
        
        # 3. Test GET /contracts
        response = client.get("/contracts")
        assert response.status_code == 200
        contracts_list = response.json()
        assert len(contracts_list) >= 1
        assert any(c["name"] == "api_test_contract" for c in contracts_list)
        
        # 4. Test GET /contracts/{id}
        response = client.get(f"/contracts/{contract_uuid}")
        assert response.status_code == 200
        c_details = response.json()
        assert c_details["name"] == "api_test_contract"
        assert c_details["latest_version"] == 1
        
        # 5. Test POST /contracts/validate
        val_payload = {
            "contract_id": "api_test_contract",
            "records": [
                {"user_id": "u103", "score": 85, "premium": True},
                {"user_id": "u104", "score": "invalid_score", "premium": False} # Type mismatch violation
            ]
        }
        response = client.post("/contracts/validate", json=val_payload)
        assert response.status_code == 200
        val_res = response.json()
        assert val_res["is_valid"] is False
        assert val_res["violations_logged"] == 1
        assert val_res["violations"][0]["violation_type"] == "Type mismatch"
        assert val_res["violations"][0]["field_name"] == "score"
        
        # 6. Test GET /violations
        response = client.get("/violations?violation_type=Type mismatch")
        assert response.status_code == 200
        violations_list = response.json()
        assert len(violations_list) >= 1
        assert violations_list[0]["field_name"] == "score"
        
        # 7. Test GET /drift-report
        disc_schema = json.dumps({
            "user_id": "string",
            "score": "float", # type changed from integer to float
            "premium": "boolean",
            "new_column": "string" # added
        })
        response = client.get(f"/drift-report?contract_id=api_test_contract&discovered_schema={disc_schema}")
        assert response.status_code == 200
        drift_res = response.json()
        assert drift_res["has_drift"] is True
        assert drift_res["risk"] == "medium" # int -> float is medium risk
        assert len(drift_res["changes"]) == 2
