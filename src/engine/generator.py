"""
Contract Generator Agent for Shadow-Ops.

Infers schemas, constraints, value distributions, and candidate primary keys
from raw schema definitions or sample datasets with confidence scoring.
"""

from typing import Any, Dict, List, Optional
import pandas as pd
import numpy as np
from src.engine.models import ContractSchema, FieldConstraint


class ContractGeneratorAgent:
    """
    Agent that automatically generates Data Contracts with constraints,
    distributions, and confidence scores from schemas and sample data.
    """

    def __init__(self, name: str = "ContractGeneratorAgent"):
        self.name = name

    def generate(
        self,
        contract_name: str,
        discovered_schema: Optional[Dict[str, str]] = None,
        sample_data: Optional[List[Dict[str, Any]]] = None,
        description: Optional[str] = None
    ) -> ContractSchema:
        """
        Generates a contract schema.
        
        Args:
            contract_name: Name of the contract to create
            discovered_schema: Dict of field_name -> type_name (e.g., {"id": "int"})
            sample_data: Optional list of dictionaries representing database rows
            description: Optional text description of the contract
            
        Returns:
            ContractSchema: A fully validated Pydantic contract definition.
        """
        fields: List[FieldConstraint] = []
        metadata: Dict[str, Any] = {
            "inferred_at_count": len(sample_data) if sample_data else 0,
            "has_sample_data": sample_data is not None
        }

        # Case 1: Sample data is provided. Run statistical profiling.
        if sample_data and len(sample_data) > 0:
            df = pd.DataFrame(sample_data)
            
            # If discovered schema is not provided, infer from dataframe
            if not discovered_schema:
                discovered_schema = {}
                for col in df.columns:
                    dtype = str(df[col].dtype)
                    if "int" in dtype:
                        discovered_schema[col] = "integer"
                    elif "float" in dtype:
                        discovered_schema[col] = "float"
                    elif "bool" in dtype:
                        discovered_schema[col] = "boolean"
                    elif "datetime" in dtype or "date" in dtype:
                        discovered_schema[col] = "datetime"
                    elif "object" in dtype:
                        discovered_schema[col] = "string"
                    else:
                        discovered_schema[col] = "json"

            # Profile columns
            candidate_pks = []
            distributions = {}

            for field_name, field_type in discovered_schema.items():
                if field_name not in df.columns:
                    # Column defined in schema but not present in sample data
                    fields.append(FieldConstraint(
                        name=field_name,
                        type=field_type,
                        required=True,
                        unique=False,
                        confidence_score=0.5
                    ))
                    continue

                col_data = df[field_name]
                total_count = len(col_data)
                null_count = col_data.isnull().sum()
                non_null_count = total_count - null_count
                
                # Check nullability
                required = bool(null_count == 0)
                
                # Check uniqueness
                unique_values = col_data.dropna().unique()
                unique_count = len(unique_values)
                unique = bool(unique_count == non_null_count and non_null_count > 0)

                # Heuristic for PK candidates
                is_pk = False
                if unique and required:
                    if field_name.lower() in ("id", "uuid", "pk") or field_name.lower().endswith("_id"):
                        is_pk = True
                        candidate_pks.append(field_name)

                # Build constraints
                min_val = None
                max_val = None
                allowed_vals = None
                
                # Assign type-specific validation metadata and stats
                if field_type in ("integer", "float") or "int" in field_type or "float" in field_type:
                    numeric_data = pd.to_numeric(col_data.dropna(), errors="coerce")
                    if not numeric_data.empty:
                        min_val = float(numeric_data.min())
                        max_val = float(numeric_data.max())
                        distributions[field_name] = {
                            "mean": float(numeric_data.mean()) if not np.isnan(numeric_data.mean()) else 0.0,
                            "std": float(numeric_data.std()) if not np.isnan(numeric_data.std()) else 0.0,
                            "null_rate": float(null_count / total_count)
                        }
                elif field_type == "string" and not unique and not is_pk:
                    # Check if enum candidate (small cardinality)
                    # If number of unique values is low (<= 15 and either <= 50% of data size or total count is small)
                    if 0 < unique_count <= 15 and ((unique_count / non_null_count) <= 0.5 or non_null_count <= 20):
                        allowed_vals = [str(x) for x in unique_values]
                    
                    distributions[field_name] = {
                        "cardinality": int(unique_count),
                        "null_rate": float(null_count / total_count)
                    }

                # Confidence scoring logic:
                # - High sample size leads to higher confidence
                # - Presence of nulls, card, type stability
                sample_factor = min(1.0, non_null_count / 10.0) # Need at least 10 non-null values for full confidence
                confidence = float(round(0.6 + (0.4 * sample_factor), 2))
                
                # If unique key was found, raise its PK candidate score
                if is_pk:
                    confidence = 1.0

                fields.append(FieldConstraint(
                    name=field_name,
                    type=field_type,
                    required=required,
                    unique=unique,
                    is_primary_key=is_pk,
                    allowed_values=allowed_vals,
                    min_value=min_val,
                    max_value=max_val,
                    confidence_score=confidence
                ))

            # Store computed distributions and PK findings in metadata
            metadata["distributions"] = distributions
            metadata["candidate_primary_keys"] = candidate_pks

        # Case 2: Only schema is provided. Rely on type-based heuristics.
        else:
            discovered_schema = discovered_schema or {}
            for field_name, field_type in discovered_schema.items():
                required = True
                unique = False
                is_pk = False
                allowed_vals = None
                confidence = 0.5  # Low confidence because we don't have sample data

                # Smart heuristics
                name_lower = field_name.lower()
                if name_lower in ("id", "uuid") or name_lower.endswith("_id"):
                    required = True
                    unique = True
                    is_pk = True
                    confidence = 0.75
                
                if name_lower in ("country", "status", "role", "state", "type"):
                    allowed_vals = [] # Let user fill, but inferred as enum field
                    confidence = 0.60

                fields.append(FieldConstraint(
                    name=field_name,
                    type=field_type,
                    required=required,
                    unique=unique,
                    is_primary_key=is_pk,
                    allowed_values=allowed_vals,
                    confidence_score=confidence
                ))

        return ContractSchema(
            contract_name=contract_name,
            description=description,
            fields=fields,
            metadata=metadata
        )
