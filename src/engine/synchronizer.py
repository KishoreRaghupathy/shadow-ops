"""
Drift-to-Contract Synchronizer for Shadow-Ops.

Detects structural changes (drift) between registered active contracts
and newly discovered database schemas, categorizing risks and generating recommendations.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from src.engine.models import ContractSchema, FieldConstraint


class DriftSynchronizer:
    """
    Component that compares active contracts against runtime schemas
    to assess impact, risk levels, and auto-generate structural update proposals.
    """

    def __init__(self, name: str = "DriftSynchronizer"):
        self.name = name

    def analyze_drift(
        self,
        contract: ContractSchema,
        discovered_schema: Dict[str, str],
        affected_contracts_count: int = 1
    ) -> Dict[str, Any]:
        """
        Analyzes drift between an active contract schema and a newly discovered schema.
        
        Args:
            contract: The registered ContractSchema
            discovered_schema: A dictionary mapping field_name -> type_name
            affected_contracts_count: Simulated count of related downstream contracts
            
        Returns:
            Dict containing the drift report.
        """
        contract_fields = {f.name: f for f in contract.fields}
        discovered_fields = discovered_schema

        changes: List[Dict[str, Any]] = []
        max_risk = "low"

        # Track processed fields to detect potential renames
        removed_fields = []
        added_fields = []

        # 1. Detect Removed Fields
        for name, field in contract_fields.items():
            if name not in discovered_fields:
                removed_fields.append(name)

        # 2. Detect Added Fields
        for name, dtype in discovered_fields.items():
            if name not in contract_fields:
                added_fields.append((name, dtype))

        # 3. Handle Potential Renames and Removals
        # Simple heuristic: if 1 field is removed and 1 field is added of the same type,
        # it is classified as a "potential_rename"
        renamed_pairs = {}
        if len(removed_fields) == 1 and len(added_fields) == 1:
            old_name = removed_fields[0]
            new_name, new_type = added_fields[0]
            old_field = contract_fields[old_name]
            
            if old_field.type == new_type or (old_field.type in ("integer", "float") and new_type in ("integer", "float")):
                renamed_pairs[old_name] = new_name
                changes.append({
                    "field": f"{old_name} → {new_name}",
                    "change_type": "potential_rename",
                    "details": f"Field '{old_name}' seems to have been renamed to '{new_name}' (type: {new_type})",
                    "risk": "high"
                })
                max_risk = "high"
                # Remove from tracking list so they aren't processed as separate add/remove
                removed_fields.remove(old_name)
                added_fields.remove((new_name, new_type))

        # Log remaining removed fields
        for old_name in removed_fields:
            old_field = contract_fields[old_name]
            risk = "high" if old_field.required else "medium"
            if risk == "high":
                max_risk = "high"
            elif risk == "medium" and max_risk != "high":
                max_risk = "medium"

            changes.append({
                "field": old_name,
                "change_type": "removed",
                "details": f"Required field '{old_name}' is missing" if old_field.required else f"Optional field '{old_name}' is missing",
                "risk": risk
            })

        # Log remaining added fields
        for new_name, new_type in added_fields:
            changes.append({
                "field": new_name,
                "change_type": "added",
                "details": f"New field '{new_name}' (type: {new_type}) discovered",
                "risk": "low"
            })

        # 4. Detect Type Changes
        for name, dtype in discovered_fields.items():
            if name in contract_fields and name not in renamed_pairs.values():
                old_field = contract_fields[name]
                old_type = old_field.type
                new_type = dtype
                
                # Check for structural mismatch
                if old_type != new_type:
                    risk = "high"
                    # Soften risk if it's int -> float (widening)
                    if old_type in ("integer", "int") and new_type in ("float", "double"):
                        risk = "medium"
                    
                    if risk == "high":
                        max_risk = "high"
                    elif risk == "medium" and max_risk != "high":
                        max_risk = "medium"

                    changes.append({
                        "field": name,
                        "change_type": "type_changed",
                        "details": f"Field type changed from '{old_type}' to '{new_type}'",
                        "risk": risk
                    })

        # 5. Build Recommendations
        has_drift = len(changes) > 0
        recommendations = []
        if not has_drift:
            recommendations.append("No schema drift detected. Current contract is fully aligned.")
        else:
            for change in changes:
                ft = change["field"]
                ctype = change["change_type"]
                risk = change["risk"]
                
                if ctype == "potential_rename":
                    recommendations.append(f"CRITICAL: Update contract schema mapping from '{ft}' to prevent downstream mapping failures.")
                elif ctype == "removed" and risk == "high":
                    recommendations.append(f"CRITICAL: Required field '{ft}' was removed! downstream queries will fail. Investigate database schema migrations.")
                elif ctype == "type_changed" and risk == "high":
                    recommendations.append(f"CRITICAL: Type incompatibility on field '{ft}'. Coercion failures expected. Upgrade schema contract to reflect new type.")
                elif ctype == "added":
                    recommendations.append(f"INFO: Add new field '{ft}' as optional in a new contract version.")
                else:
                    recommendations.append(f"WARNING: Schema has drifted on '{ft}' (Type: {ctype}). Register a revised contract version.")

        # Structure final output to match example exactly
        # Example output: { "change": "user_id -> customer_uuid", "risk": "high", "affected_contracts": 4 }
        summary_change = "No change"
        if changes:
            main_change = changes[0]
            if main_change["change_type"] == "potential_rename":
                summary_change = main_change["field"]
            else:
                summary_change = f"{main_change['change_type']}: {main_change['field']}"

        return {
            "has_drift": has_drift,
            "change": summary_change,
            "risk": max_risk,
            "affected_contracts": affected_contracts_count,
            "changes": changes,
            "recommendations": recommendations,
            "analyzed_at": datetime.now().isoformat()
        }
