"""
Contract Registry for Shadow-Ops.

Manages contract creation, schema version history, rollbacks, version comparisons,
searching, and logging validations/violations in the database.
"""

import json
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import or_

from src.engine.models import Contract, ContractVersion, ContractViolation, ContractSchema, FieldConstraint


class ContractRegistry:
    """
    Registry that coordinates versioning, rollbacks, search, comparison,
    and violation telemetry storage using the underlying database session.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_contract_by_id(self, contract_id: str) -> Optional[Contract]:
        """
        Retrieves a contract by its database ID.
        """
        return self.db.query(Contract).filter(Contract.id == contract_id).first()

    def get_contract_by_name(self, name: str) -> Optional[Contract]:
        """
        Retrieves a contract by its unique name.
        """
        return self.db.query(Contract).filter(Contract.name == name).first()

    def get_latest_version(self, contract_id: str) -> Optional[ContractVersion]:
        """
        Retrieves the latest version record for a given contract.
        """
        return self.db.query(ContractVersion)\
            .filter(ContractVersion.contract_id == contract_id)\
            .order_by(ContractVersion.version.desc())\
            .first()

    def get_version_by_number(self, contract_id: str, version_num: int) -> Optional[ContractVersion]:
        """
        Retrieves a specific contract version by number.
        """
        return self.db.query(ContractVersion)\
            .filter(ContractVersion.contract_id == contract_id, ContractVersion.version == version_num)\
            .first()

    def get_contract_history(self, contract_id: str) -> List[ContractVersion]:
        """
        Retrieves the full version history for a given contract, sorted by version ascending.
        """
        return self.db.query(ContractVersion)\
            .filter(ContractVersion.contract_id == contract_id)\
            .order_by(ContractVersion.version.asc())\
            .all()

    def search_contracts(self, query: str) -> List[Contract]:
        """
        Searches contracts matching name or description.
        """
        if not query:
            return self.db.query(Contract).all()
        
        search_filter = or_(
            Contract.name.ilike(f"%{query}%"),
            Contract.description.ilike(f"%{query}%")
        )
        return self.db.query(Contract).filter(search_filter).all()

    def register_contract(
        self,
        name: str,
        schema_data: ContractSchema,
        description: Optional[str] = None
    ) -> ContractVersion:
        """
        Registers a new contract or versions an existing contract if the schema has changed.
        
        If the schema is identical to the latest version, it returns the latest version.
        Otherwise, it increments the version number and creates a new ContractVersion record.
        """
        # Clean the input name and check existence
        contract = self.get_contract_by_name(name)
        new_schema_json = schema_data.model_dump_json()

        if not contract:
            # Create new Contract record
            contract = Contract(
                name=name,
                description=description or schema_data.description
            )
            self.db.add(contract)
            self.db.flush()  # Populates contract.id
            
            # Create version 1
            version = ContractVersion(
                contract_id=contract.id,
                version=1,
                schema_json=new_schema_json
            )
            self.db.add(version)
            self.db.commit()
            self.db.refresh(version)
            return version
        
        # Contract exists, check if schema has changed compared to the latest version
        latest_version = self.get_latest_version(contract.id)
        if latest_version:
            # Parse both schemas for comparison (ignoring description or root name changes)
            try:
                latest_schema_dict = json.loads(latest_version.schema_json)
                new_schema_dict = json.loads(new_schema_json)
                
                # Check structural equality of fields
                fields_identical = (latest_schema_dict.get("fields") == new_schema_dict.get("fields"))
                
                if fields_identical:
                    # No schema changes, update description if provided and return latest
                    if description and description != contract.description:
                        contract.description = description
                        contract.updated_at = datetime.now(timezone.utc)
                        self.db.commit()
                    return latest_version
            except Exception:
                pass # If parsing fail, proceed to force update
            
            # Schema changed, create new version
            next_version_num = latest_version.version + 1
        else:
            # Safeguard in case contract exists but versions are missing
            next_version_num = 1

        # Update parent contract timestamps
        contract.updated_at = datetime.now(timezone.utc)
        if description:
            contract.description = description
            
        version = ContractVersion(
            contract_id=contract.id,
            version=next_version_num,
            schema_json=new_schema_json
        )
        self.db.add(version)
        self.db.commit()
        self.db.refresh(version)
        return version

    def compare_versions(self, contract_id: str, v1_num: int, v2_num: int) -> Dict[str, Any]:
        """
        Compares two versions of a contract and generates a structural diff report.
        """
        v1 = self.get_version_by_number(contract_id, v1_num)
        v2 = self.get_version_by_number(contract_id, v2_num)

        if not v1 or not v2:
            raise ValueError(f"One or both contract versions ({v1_num}, {v2_num}) do not exist.")

        schema1 = json.loads(v1.schema_json)
        schema2 = json.loads(v2.schema_json)

        fields1 = {f["name"]: f for f in schema1.get("fields", [])}
        fields2 = {f["name"]: f for f in schema2.get("fields", [])}

        added = []
        removed = []
        modified = {}

        # Detect added and modified
        for name, f2 in fields2.items():
            if name not in fields1:
                added.append(name)
            else:
                f1 = fields1[name]
                diffs = {}
                for key, val in f2.items():
                    if f1.get(key) != val:
                        diffs[key] = {"old": f1.get(key), "new": val}
                if diffs:
                    modified[name] = diffs

        # Detect removed
        for name in fields1:
            if name not in fields2:
                removed.append(name)

        return {
            "contract_id": contract_id,
            "comparison": f"v{v1_num} -> v{v2_num}",
            "added": added,
            "removed": removed,
            "modified": modified,
            "has_changes": bool(added or removed or modified)
        }

    def rollback_contract(self, contract_id: str, target_version_num: int) -> ContractVersion:
        """
        Rolls back a contract to a past version's schema.
        
        To prevent history destruction, this is performed by creating a new version
        holding the exact copy of the schema from target_version_num.
        """
        contract = self.get_contract_by_id(contract_id)
        if not contract:
            raise ValueError(f"Contract ID {contract_id} does not exist.")

        target_version = self.get_version_by_number(contract_id, target_version_num)
        if not target_version:
            raise ValueError(f"Target version {target_version_num} not found for contract {contract.name}.")

        latest_version = self.get_latest_version(contract_id)
        if latest_version and latest_version.version == target_version_num:
            # Already at target version
            return latest_version

        # Parse target schema
        target_schema_dict = json.loads(target_version.schema_json)
        schema_obj = ContractSchema(**target_schema_dict)
        schema_obj.metadata["rollback_source_version"] = target_version_num

        # Register target schema as a new version
        return self.register_contract(
            name=contract.name,
            schema_data=schema_obj,
            description=f"Rollback to version {target_version_num} from {latest_version.version if latest_version else 'unknown'}"
        )

    def log_violation(
        self,
        contract_id: str,
        version_id: Optional[str],
        violation_type: str,
        field_name: Optional[str],
        expected_value: Optional[str],
        actual_value: Optional[str],
        payload_preview: Optional[str] = None
    ) -> ContractViolation:
        """
        Logs a contract violation record in the database.
        """
        violation = ContractViolation(
            contract_id=contract_id,
            version_id=version_id,
            violation_type=violation_type,
            field_name=field_name,
            expected_value=expected_value,
            actual_value=actual_value,
            payload_preview=payload_preview
        )
        self.db.add(violation)
        self.db.commit()
        self.db.refresh(violation)
        return violation

    def get_violations(
        self,
        contract_id: Optional[str] = None,
        violation_type: Optional[str] = None,
        limit: int = 100
    ) -> List[ContractViolation]:
        """
        Retrieves violation records with filtering support.
        """
        query = self.db.query(ContractViolation)
        if contract_id:
            query = query.filter(ContractViolation.contract_id == contract_id)
        if violation_type:
            query = query.filter(ContractViolation.violation_type == violation_type)
        
        return query.order_by(ContractViolation.created_at.desc()).limit(limit).all()
