"""
Contract Validation Agent for Shadow-Ops.

Validates streaming payloads, API requests, and batch files against contract schemas.
Identifies and logs violation types: Missing field, Type mismatch, Range violation,
Enum violation, Nullability violation, and Duplicate key violation.
"""

import json
from typing import Any, Dict, List, Optional
import pandas as pd
from datetime import datetime
from src.engine.models import ContractSchema, FieldConstraint


class ContractValidationAgent:
    """
    Agent responsible for running schema assertions on records and datasets.
    Computes violation details, health metrics, and Great Expectations-styled reports.
    """

    def __init__(self, name: str = "ContractValidationAgent"):
        self.name = name

    def _validate_type(self, val: Any, expected_type: str) -> bool:
        """
        Validates if val matches or can be safely coerced to expected_type.
        """
        if val is None:
            return True

        expected_type = expected_type.lower()
        
        if expected_type in ("integer", "int"):
            if isinstance(val, bool):
                return False
            try:
                int(val)
                # Check if it's a float with decimal parts
                if isinstance(val, float) and val != int(val):
                    return False
                return True
            except (ValueError, TypeError):
                return False
                
        elif expected_type in ("float", "double", "number"):
            if isinstance(val, bool):
                return False
            try:
                float(val)
                return True
            except (ValueError, TypeError):
                return False
                
        elif expected_type in ("boolean", "bool"):
            if isinstance(val, bool):
                return True
            if str(val).lower() in ("true", "false", "1", "0", "yes", "no"):
                return True
            return False
            
        elif expected_type in ("datetime", "timestamp", "date"):
            if isinstance(val, (datetime, pd.Timestamp)):
                return True
            try:
                pd.to_datetime(val)
                return True
            except Exception:
                return False
                
        elif expected_type in ("json", "dict", "list"):
            if isinstance(val, (dict, list)):
                return True
            if isinstance(val, str):
                try:
                    json.loads(val)
                    return True
                except ValueError:
                    return False
            return False
            
        elif expected_type in ("string", "str"):
            # Almost anything can be a string, but we exclude complex dicts/lists unless specified
            return not isinstance(val, (dict, list))
            
        return True

    def validate_record(self, record: Dict[str, Any], schema: ContractSchema) -> List[Dict[str, Any]]:
        """
        Validates a single record (streaming payload / API request) against the contract.
        
        Returns:
            List of violation dictionaries.
        """
        violations = []
        payload_str = json.dumps(record)

        for field in schema.fields:
            name = field.name
            expected_type = field.type
            required = field.required

            # 1. Missing Field Violation
            if name not in record:
                if required:
                    violations.append({
                        "violation_type": "Missing field",
                        "field_name": name,
                        "expected_value": f"Field of type '{expected_type}'",
                        "actual_value": "NULL/Missing",
                        "payload_preview": payload_str
                    })
                continue

            val = record[name]

            # 2. Nullability Violation
            if val is None or (isinstance(val, float) and pd.isna(val)):
                if required:
                    violations.append({
                        "violation_type": "Nullability violation",
                        "field_name": name,
                        "expected_value": "NON-NULL",
                        "actual_value": "NULL",
                        "payload_preview": payload_str
                    })
                continue

            # 3. Type Mismatch Violation
            if not self._validate_type(val, expected_type):
                violations.append({
                    "violation_type": "Type mismatch",
                    "field_name": name,
                    "expected_value": expected_type,
                    "actual_value": f"{type(val).__name__} ('{val}')",
                    "payload_preview": payload_str
                })
                continue

            # Coerce value for range checks if numeric
            coerced_val = val
            if expected_type in ("integer", "int"):
                coerced_val = int(val)
            elif expected_type in ("float", "double", "number"):
                coerced_val = float(val)

            # 4. Range Violation
            if isinstance(coerced_val, (int, float)):
                if field.min_value is not None and coerced_val < field.min_value:
                    violations.append({
                        "violation_type": "Range violation",
                        "field_name": name,
                        "expected_value": f">= {field.min_value}",
                        "actual_value": str(coerced_val),
                        "payload_preview": payload_str
                    })
                if field.max_value is not None and coerced_val > field.max_value:
                    violations.append({
                        "violation_type": "Range violation",
                        "field_name": name,
                        "expected_value": f"<= {field.max_value}",
                        "actual_value": str(coerced_val),
                        "payload_preview": payload_str
                    })

            # 5. Enum Violation
            if field.allowed_values is not None and len(field.allowed_values) > 0:
                if val not in field.allowed_values and str(val) not in [str(x) for x in field.allowed_values]:
                    violations.append({
                        "violation_type": "Enum violation",
                        "field_name": name,
                        "expected_value": f"One of {field.allowed_values}",
                        "actual_value": str(val),
                        "payload_preview": payload_str
                    })

        return violations

    def validate_dataset(self, data: List[Dict[str, Any]], schema: ContractSchema) -> Dict[str, Any]:
        """
        Validates a list of dictionaries (dataset or batch payload) against the contract schema.
        
        Returns:
            Dictionary containing validation results, metrics, and a Great Expectations compliance report.
        """
        if not data:
            return {
                "is_valid": True,
                "violations": [],
                "metrics": {
                    "total_records": 0,
                    "total_violations": 0,
                    "violation_rate": 0.0,
                    "health_score": 100.0
                },
                "ge_report": {
                    "success": True,
                    "statistics": {"evaluated_expectations": 0, "successful_expectations": 0, "success_percent": 100.0},
                    "results": []
                }
            }

        violations: List[Dict[str, Any]] = []
        total_records = len(data)

        # 1. Row-level validation (Missing, Nullability, Type, Range, Enum)
        for i, record in enumerate(data):
            row_violations = self.validate_record(record, schema)
            # Annotate with row index in preview
            for v in row_violations:
                v["payload_preview"] = f"Row {i}: {v['payload_preview']}"
            violations.extend(row_violations)

        # 2. Batch-level validation: Duplicate key violation
        for field in schema.fields:
            if field.unique or field.is_primary_key:
                seen = set()
                duplicates = set()
                for i, record in enumerate(data):
                    val = record.get(field.name)
                    if val is not None:
                        val_str = str(val)
                        if val_str in seen:
                            duplicates.add(val_str)
                        seen.add(val_str)
                
                if duplicates:
                    violations.append({
                        "violation_type": "Duplicate key violation",
                        "field_name": field.name,
                        "expected_value": "All values must be UNIQUE",
                        "actual_value": f"Found duplicate values: {list(duplicates)[:5]}",
                        "payload_preview": f"Batch check identified {len(duplicates)} duplicate values in field '{field.name}'"
                    })

        # Calculate metrics
        total_violations = len(violations)
        violation_rate = float(round(total_violations / total_records, 4)) if total_records > 0 else 0.0
        health_score = float(max(0, round(100.0 * (1.0 - (total_violations / (total_records * len(schema.fields) if total_records > 0 else 1))), 2)))

        # 3. Generate Great Expectations-styled compliance report
        ge_results = []
        successful_expectations = 0
        evaluated_expectations = 0

        # Construct expectation evaluations mimicking GE output format
        for field in schema.fields:
            name = field.name
            
            # Expectation: Column to exist
            evaluated_expectations += 1
            col_exists_viol = [v for v in violations if v["field_name"] == name and v["violation_type"] == "Missing field"]
            col_exists_success = len(col_exists_viol) == 0
            if col_exists_success:
                successful_expectations += 1
            ge_results.append({
                "expectation_config": {"expectation_type": "expect_column_to_exist", "kwargs": {"column": name}},
                "success": col_exists_success,
                "result": {"observed_value": "Present" if col_exists_success else "Missing"}
            })

            # Expectation: Column values to not be null
            if field.required:
                evaluated_expectations += 1
                null_viol = [v for v in violations if v["field_name"] == name and v["violation_type"] == "Nullability violation"]
                null_success = len(null_viol) == 0
                if null_success:
                    successful_expectations += 1
                ge_results.append({
                    "expectation_config": {"expectation_type": "expect_column_values_to_not_be_null", "kwargs": {"column": name}},
                    "success": null_success,
                    "result": {"unexpected_count": len(null_viol), "unexpected_percent": float(round(len(null_viol) / total_records * 100, 2)) if total_records > 0 else 0.0}
                })

            # Expectation: Column values to be unique
            if field.unique or field.is_primary_key:
                evaluated_expectations += 1
                unique_viol = [v for v in violations if v["field_name"] == name and v["violation_type"] == "Duplicate key violation"]
                unique_success = len(unique_viol) == 0
                if unique_success:
                    successful_expectations += 1
                ge_results.append({
                    "expectation_config": {"expectation_type": "expect_column_values_to_be_unique", "kwargs": {"column": name}},
                    "success": unique_success,
                    "result": {"unexpected_count": len(unique_viol)}
                })

            # Expectation: Column values to be between
            if field.min_value is not None or field.max_value is not None:
                evaluated_expectations += 1
                range_viol = [v for v in violations if v["field_name"] == name and v["violation_type"] == "Range violation"]
                range_success = len(range_viol) == 0
                if range_success:
                    successful_expectations += 1
                ge_results.append({
                    "expectation_config": {
                        "expectation_type": "expect_column_values_to_be_between",
                        "kwargs": {"column": name, "min_value": field.min_value, "max_value": field.max_value}
                    },
                    "success": range_success,
                    "result": {"unexpected_count": len(range_viol)}
                })

            # Expectation: Column values to be in set
            if field.allowed_values is not None and len(field.allowed_values) > 0:
                evaluated_expectations += 1
                enum_viol = [v for v in violations if v["field_name"] == name and v["violation_type"] == "Enum violation"]
                enum_success = len(enum_viol) == 0
                if enum_success:
                    successful_expectations += 1
                ge_results.append({
                    "expectation_config": {
                        "expectation_type": "expect_column_values_to_be_in_set",
                        "kwargs": {"column": name, "value_set": field.allowed_values}
                    },
                    "success": enum_success,
                    "result": {"unexpected_count": len(enum_viol)}
                })

        success_percent = float(round((successful_expectations / evaluated_expectations) * 100, 2)) if evaluated_expectations > 0 else 100.0

        ge_report = {
            "success": bool(total_violations == 0),
            "statistics": {
                "evaluated_expectations": evaluated_expectations,
                "successful_expectations": successful_expectations,
                "success_percent": success_percent
            },
            "results": ge_results
        }

        return {
            "is_valid": bool(total_violations == 0),
            "violations": violations,
            "metrics": {
                "total_records": total_records,
                "total_violations": total_violations,
                "violation_rate": violation_rate,
                "health_score": health_score
            },
            "ge_report": ge_report
        }
