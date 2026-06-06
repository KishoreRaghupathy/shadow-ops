"""
Streamlit Web Dashboard for Shadow-Ops Data Contract Intelligence Layer.

Implements Contract Inventory, Violation Audit, Schema Drift Analysis,
Live Validation Playground, and Contract Health Score visualizations.
"""

import json
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# Import database and models directly for direct, high-performance DB interaction
from src.engine.database import SessionLocal, init_db
from src.engine.models import Contract, ContractVersion, ContractViolation, ContractSchema
from src.engine.registry import ContractRegistry
from src.engine.generator import ContractGeneratorAgent
from src.engine.validator import ContractValidationAgent
from src.engine.synchronizer import DriftSynchronizer

# Page Configurations
st.set_page_config(
    page_title="Shadow-Ops Data Contract Intelligence",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database tables
init_db()

# Custom Premium Styling & Typography
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    /* Global Background Adjustments */
    .stApp {
        background: linear-gradient(135deg, #0e1117 0%, #161a24 100%);
        color: #e2e8f0;
    }
    
    /* Glassmorphism containers */
    .glass-card {
        background: rgba(30, 41, 59, 0.45);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2);
        backdrop-filter: blur(8px);
        margin-bottom: 20px;
    }
    
    /* Headers styling */
    h1, h2, h3 {
        color: #f8fafc;
        font-weight: 700;
    }
    
    /* Metrics panel */
    .metric-value {
        font-size: 2.2rem;
        font-weight: 700;
        color: #38bdf8;
    }
    .metric-label {
        font-size: 0.9rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    /* Status pills */
    .badge-success {
        background-color: rgba(16, 185, 129, 0.15);
        color: #10b981;
        padding: 4px 10px;
        border-radius: 9999px;
        border: 1px solid rgba(16, 185, 129, 0.3);
        font-weight: 600;
        font-size: 0.8rem;
    }
    .badge-warning {
        background-color: rgba(245, 158, 11, 0.15);
        color: #f59e0b;
        padding: 4px 10px;
        border-radius: 9999px;
        border: 1px solid rgba(245, 158, 11, 0.3);
        font-weight: 600;
        font-size: 0.8rem;
    }
    .badge-danger {
        background-color: rgba(239, 68, 68, 0.15);
        color: #ef4444;
        padding: 4px 10px;
        border-radius: 9999px;
        border: 1px solid rgba(239, 68, 68, 0.3);
        font-weight: 600;
        font-size: 0.8rem;
    }
</style>
""", unsafe_allow_html=True)


def load_demo_data(registry: ContractRegistry):
    """
    Seeds the registry with sample data for demonstration if none exists.
    """
    contracts = registry.search_contracts("")
    if len(contracts) > 0:
        return

    # Seed User Contract
    user_schema = {
        "user_id": "string",
        "email": "string",
        "age": "integer",
        "country": "string",
        "signup_timestamp": "datetime"
    }
    user_samples = [
        {"user_id": "usr_001", "email": "alice@gmail.com", "age": 28, "country": "US", "signup_timestamp": "2026-06-01T10:00:00Z"},
        {"user_id": "usr_002", "email": "bob@yahoo.com", "age": 34, "country": "CA", "signup_timestamp": "2026-06-01T11:30:00Z"},
        {"user_id": "usr_003", "email": "charlie@outlook.com", "age": 22, "country": "UK", "signup_timestamp": "2026-06-02T08:15:00Z"},
        {"user_id": "usr_004", "email": "david@corp.com", "age": 45, "country": "DE", "signup_timestamp": "2026-06-02T15:20:00Z"},
    ]
    
    gen = ContractGeneratorAgent()
    contract_schema = gen.generate("user_contract", user_schema, user_samples, "Central user authentication and demographic registry contract")
    registry.register_contract("user_contract", contract_schema, "Central user authentication and demographic registry contract")

    # Seed Transaction Contract
    txn_schema = {
        "transaction_id": "string",
        "user_id": "string",
        "amount": "float",
        "status": "string"
    }
    txn_samples = [
        {"transaction_id": "tx_8801", "user_id": "usr_001", "amount": 120.50, "status": "completed"},
        {"transaction_id": "tx_8802", "user_id": "usr_002", "amount": 15.00, "status": "completed"},
        {"transaction_id": "tx_8803", "user_id": "usr_003", "amount": 250.00, "status": "pending"},
        {"transaction_id": "tx_8804", "user_id": "usr_004", "amount": 9.99, "status": "failed"},
    ]
    contract_schema2 = gen.generate("transaction_contract", txn_schema, txn_samples, "E-commerce order transaction log and settlement status")
    v2 = registry.register_contract("transaction_contract", contract_schema2, "E-commerce order transaction log and settlement status")

    # Add historical violations for UI demo
    registry.log_violation(
        contract_id=v2.contract_id,
        version_id=v2.id,
        violation_type="Nullability violation",
        field_name="user_id",
        expected_value="NON-NULL",
        actual_value="NULL",
        payload_preview='{"transaction_id": "tx_8805", "user_id": null, "amount": 42.0, "status": "pending"}'
    )
    registry.log_violation(
        contract_id=v2.contract_id,
        version_id=v2.id,
        violation_type="Type mismatch",
        field_name="amount",
        expected_value="float",
        actual_value="string ('one hundred')",
        payload_preview='{"transaction_id": "tx_8806", "user_id": "usr_002", "amount": "one hundred", "status": "completed"}'
    )
    registry.log_violation(
        contract_id=v2.contract_id,
        version_id=v2.id,
        violation_type="Enum violation",
        field_name="status",
        expected_value="One of ['completed', 'pending', 'failed']",
        actual_value="cancelled",
        payload_preview='{"transaction_id": "tx_8807", "user_id": "usr_003", "amount": 55.4, "status": "cancelled"}'
    )


# App Sidebar Navigation
st.sidebar.markdown("""
<div style="text-align: center; margin-bottom: 20px;">
    <h2 style="color: #38bdf8; margin:0;">SHADOW-OPS</h2>
    <span style="font-size: 0.8rem; color:#64748b; letter-spacing:0.1em; text-transform:uppercase;">Data Intelligence Layer</span>
</div>
""", unsafe_allow_html=True)

menu = st.sidebar.radio(
    "Navigation Views",
    ["Dashboard Overview", "Contract Inventory", "Violations Log", "Schema Drift Sync", "Validation Playground"]
)

# Connect to database via session
db = SessionLocal()
registry = ContractRegistry(db)
load_demo_data(registry)


# ==============================================================================
# VIEW: Dashboard Overview
# ==============================================================================
if menu == "Dashboard Overview":
    st.markdown("<h1>🛡️ Data Contract Operations Center</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:#94a3b8; font-size:1.1rem; margin-top:-10px;'>A real-time control plane monitoring contract compliance, execution metrics, anomalies, and schema drift.</p>", unsafe_allow_html=True)
    
    # Calculate global telemetry indicators
    contracts = registry.search_contracts("")
    violations = registry.get_violations(limit=1000)
    
    total_contracts = len(contracts)
    total_violations = len(violations)
    
    # Simple Health Score computation: 100 - (number of violations * weight) capped at 10
    violations_24h = [v for v in violations if v.created_at > datetime.utcnow() - timedelta(days=1)]
    violations_24h_count = len(violations_24h)
    
    # Aggregated health score calculation
    health_score = 100.0
    if total_contracts > 0:
        health_score = max(0.0, round(100.0 - (violations_24h_count * 12.5 / total_contracts), 1))

    # Metric Row Grid
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
        <div class="glass-card" style="text-align: center;">
            <div class="metric-label">Active Contracts</div>
            <div class="metric-value">{total_contracts}</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="glass-card" style="text-align: center;">
            <div class="metric-label">Total Violations</div>
            <div class="metric-value" style="color:#ef4444;">{total_violations}</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="glass-card" style="text-align: center;">
            <div class="metric-label">Violations (24h)</div>
            <div class="metric-value" style="color:#f59e0b;">{violations_24h_count}</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        color = "#10b981" if health_score >= 90 else ("#f59e0b" if health_score >= 70 else "#ef4444")
        st.markdown(f"""
        <div class="glass-card" style="text-align: center;">
            <div class="metric-label">Network Health Score</div>
            <div class="metric-value" style="color:{color};">{health_score}%</div>
        </div>
        """, unsafe_allow_html=True)

    # Secondary Charts Row
    st.subheader("Violation Trends & Distribution")
    chart_col, stat_col = st.columns([2, 1])
    
    with chart_col:
        # Create a mock timeline of violations over the last 7 days
        days = [(datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]
        # Map actual violations to these days
        daily_counts = {d: 0 for d in days}
        for v in violations:
            v_day = v.created_at.strftime("%Y-%m-%d")
            if v_day in daily_counts:
                daily_counts[v_day] += 1
                
        trend_df = pd.DataFrame({
            "Day": list(daily_counts.keys()),
            "Violations Count": list(daily_counts.values())
        }).set_index("Day")
        
        st.line_chart(trend_df, height=220)
        
    with stat_col:
        # Pie/Bar of violations by type
        if violations:
            violation_types = [v.violation_type for v in violations]
            type_counts = pd.Series(violation_types).value_counts()
            st.bar_chart(type_counts, height=220)
        else:
            st.info("No contract violations logged in DB yet.")

    # Recent Violations Preview
    st.subheader("Critical Alerts & Schema Anomalies")
    if violations:
        recent_list = []
        for v in violations[:5]:
            c = registry.get_contract_by_id(v.contract_id)
            recent_list.append({
                "Contract": c.name if c else "Unknown",
                "Violation Type": v.violation_type,
                "Field": v.field_name,
                "Actual Value": v.actual_value,
                "Detected At (UTC)": v.created_at.strftime("%Y-%m-%d %H:%M:%S")
            })
        st.table(pd.DataFrame(recent_list))
    else:
        st.success("Clean Sheet! No schema violations detected.")


# ==============================================================================
# VIEW: Contract Inventory
# ==============================================================================
elif menu == "Contract Inventory":
    st.markdown("<h1>🛡️ Data Contract Registry Inventory</h1>", unsafe_allow_html=True)
    
    search_q = st.text_input("🔍 Search Contracts by name or keyword...", "")
    contracts = registry.search_contracts(search_q)
    
    if not contracts:
        st.info("No contracts found matching query.")
    else:
        for c in contracts:
            latest = registry.get_latest_version(c.id)
            history = registry.get_contract_history(c.id)
            
            with st.expander(f"📜 {c.name} (Active Version: v{latest.version if latest else 'N/A'})", expanded=True):
                st.markdown(f"**Description**: {c.description or 'No description provided.'}")
                st.markdown(f"*Registered: {c.created_at.strftime('%Y-%m-%d %H:%M:%S')} UTC | Last Updated: {c.updated_at.strftime('%Y-%m-%d %H:%M:%S')} UTC*")
                
                # Render constraints table
                if latest:
                    schema_data = json.loads(latest.schema_json)
                    fields_list = []
                    for f in schema_data.get("fields", []):
                        fields_list.append({
                            "Field Name": f.get("name"),
                            "Data Type": f.get("type"),
                            "Required": "Yes" if f.get("required") else "No",
                            "Unique": "Yes" if f.get("unique") else "No",
                            "Primary Key": "Yes" if f.get("is_primary_key") else "No",
                            "Allowed Enums": str(f.get("allowed_values")) if f.get("allowed_values") else "None",
                            "Range Boundaries": f"[{f.get('min_value')}, {f.get('max_value')}]" if (f.get("min_value") is not None or f.get("max_value") is not None) else "None",
                            "Confidence": f"{int(f.get('confidence_score', 1.0) * 100)}%"
                        })
                    
                    st.dataframe(pd.DataFrame(fields_list), use_container_width=True)
                    
                    # Version logs
                    st.markdown("**Version History & Audit Log**")
                    v_history_str = " | ".join([f"v{h.version} ({h.created_at.strftime('%m-%d %H:%M')})" for h in history])
                    st.markdown(f"<span style='color:#94a3b8; font-size:0.9rem;'>{v_history_str}</span>", unsafe_allow_html=True)
                    
                    # Rollback Tooling inside expander
                    if len(history) > 1:
                        target_v = st.selectbox(
                            f"Rollback {c.name} to version:",
                            [h.version for h in history[:-1]],
                            key=f"rollback_sel_{c.id}"
                        )
                        if st.button(f"Execute Rollback to v{target_v}", key=f"rollback_btn_{c.id}"):
                            try:
                                rolled = registry.rollback_contract(c.id, target_v)
                                st.success(f"Rollback successful! Contract '{c.name}' has been updated to v{rolled.version} copying v{target_v}.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Rollback failed: {str(e)}")
                else:
                    st.warning("No versions found for this contract.")


# ==============================================================================
# VIEW: Violations Log
# ==============================================================================
elif menu == "Violations Log":
    st.markdown("<h1>🚨 Contract Violation Telemetry Audit</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:#94a3b8; font-size:1.1rem; margin-top:-10px;'>Detailed diagnostics on structural, range, duplicate key, and enum violations detected during ingestion processes.</p>", unsafe_allow_html=True)
    
    contracts = registry.search_contracts("")
    contract_options = {"All Contracts": None}
    for c in contracts:
        contract_options[c.name] = c.id
        
    v_types = [
        "All Violations",
        "Missing field",
        "Type mismatch",
        "Range violation",
        "Enum violation",
        "Nullability violation",
        "Duplicate key violation"
    ]
    
    col1, col2 = st.columns(2)
    with col1:
        c_filter = st.selectbox("Filter by Contract Table", list(contract_options.keys()))
    with col2:
        t_filter = st.selectbox("Filter by Anomaly Type", v_types)
        
    contract_id = contract_options[c_filter]
    violation_type = None if t_filter == "All Violations" else t_filter
    
    violations = registry.get_violations(contract_id=contract_id, violation_type=violation_type, limit=200)
    
    if not violations:
        st.success("No violations logged matching the criteria.")
    else:
        v_list = []
        for v in violations:
            c = registry.get_contract_by_id(v.contract_id)
            ver = registry.get_version_by_number(v.contract_id, v.version.version) if (v.version_id and v.version) else None
            
            v_list.append({
                "ID": v.id[:8] + "...",
                "Contract Table": c.name if c else "Unknown",
                "Contract Version": f"v{v.version.version}" if (v.version_id and v.version) else "N/A",
                "Violation Type": v.violation_type,
                "Field name": v.field_name or "Global",
                "Expected Value": v.expected_value or "None",
                "Actual Value": v.actual_value or "None",
                "Payload Snippet": v.payload_preview or "None",
                "Timestamp (UTC)": v.created_at.strftime("%Y-%m-%d %H:%M:%S")
            })
            
        st.dataframe(pd.DataFrame(v_list), use_container_width=True)


# ==============================================================================
# VIEW: Schema Drift Sync
# ==============================================================================
elif menu == "Schema Drift Sync":
    st.markdown("<h1>🔄 Drift-to-Contract Synchronizer</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:#94a3b8; font-size:1.1rem; margin-top:-10px;'>Simulate or evaluate structural schema modifications against active production contracts to run impact assessment reports.</p>", unsafe_allow_html=True)
    
    contracts = registry.search_contracts("")
    if not contracts:
        st.warning("Please create a contract first in the registry to evaluate schema drift.")
    else:
        c_names = [c.name for c in contracts]
        selected_c_name = st.selectbox("Select Target Contract to Compare", c_names)
        
        contract = registry.get_contract_by_name(selected_c_name)
        latest_version = registry.get_latest_version(contract.id)
        latest_schema_dict = json.loads(latest_version.schema_json)
        contract_obj = ContractSchema(**latest_schema_dict)
        
        st.subheader("Define Discovered Schema (Input Schema from Prober)")
        
        # Build JSON template of current fields for easy editing
        current_fields_dict = {f.name: f.type for f in contract_obj.fields}
        schema_json_input = st.text_area(
            "Modify schema JSON below to simulate database changes:",
            value=json.dumps(current_fields_dict, indent=2),
            height=150
        )
        
        if st.button("Run Drift Impact Analysis"):
            try:
                new_schema = json.loads(schema_json_input)
                if not isinstance(new_schema, dict):
                    st.error("Invalid JSON: Schema must be an object with field_name -> type_name mapping.")
                else:
                    sync = DriftSynchronizer()
                    report = sync.analyze_drift(
                        contract=contract_obj,
                        discovered_schema=new_schema,
                        affected_contracts_count=4
                    )
                    
                    # Display summary cards
                    st.subheader("Impact Report Cards")
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.markdown(f"""
                        <div class="glass-card" style="text-align: center;">
                            <div class="metric-label">Has Drift</div>
                            <div class="metric-value">{"YES" if report["has_drift"] else "NO"}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    with col2:
                        risk_color = "#ef4444" if report["risk"] == "high" else ("#f59e0b" if report["risk"] == "medium" else "#10b981")
                        st.markdown(f"""
                        <div class="glass-card" style="text-align: center;">
                            <div class="metric-label">Drift Risk Rating</div>
                            <div class="metric-value" style="color:{risk_color};">{report["risk"].upper()}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    with col3:
                        st.markdown(f"""
                        <div class="glass-card" style="text-align: center;">
                            <div class="metric-label">Affected Contracts</div>
                            <div class="metric-value">{report["affected_contracts"]}</div>
                        </div>
                        """, unsafe_allow_html=True)

                    # List changes
                    st.subheader("Structural Changes Identified")
                    if not report["changes"]:
                        st.success("No structural changes detected between contract and prober schema.")
                    else:
                        changes_list = []
                        for ch in report["changes"]:
                            changes_list.append({
                                "Field": ch["field"],
                                "Change Type": ch["change_type"],
                                "Description": ch["details"],
                                "Risk": ch["risk"].upper()
                            })
                        st.table(pd.DataFrame(changes_list))
                        
                        # Show recommendations
                        st.subheader("Governance Action Plan & Update Suggestions")
                        for rec in report["recommendations"]:
                            if "CRITICAL" in rec:
                                st.error(rec)
                            elif "WARNING" in rec:
                                st.warning(rec)
                            else:
                                st.info(rec)
                                
                        # Propose Sync Option
                        if st.button("Apply Suggested Changes and Create Version"):
                            # Apply recommendations in a simple manner: build new schema list of constraints
                            # Add/remove simulated fields, and register
                            generator = ContractGeneratorAgent()
                            # Construct sample rows or schemas
                            final_schema_fields = {}
                            for f_name, f_type in new_schema.items():
                                final_schema_fields[f_name] = f_type
                                
                            new_contract_obj = generator.generate(
                                contract_name=contract.name,
                                discovered_schema=final_schema_fields,
                                description=contract.description
                            )
                            registry.register_contract(contract.name, new_contract_obj)
                            st.success(f"Successfully updated contract registry '{contract.name}' with drifted schema version.")
                            st.rerun()
            except Exception as e:
                st.error(f"Inference execution failed: {str(e)}")


# ==============================================================================
# VIEW: Validation Playground
# ==============================================================================
elif menu == "Validation Playground":
    st.markdown("<h1>🧪 Live Payload Validation Playground</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:#94a3b8; font-size:1.1rem; margin-top:-10px;'>Select a contract schema, paste a payload dataset, and run real-time contract compliance audits.</p>", unsafe_allow_html=True)
    
    contracts = registry.search_contracts("")
    if not contracts:
        st.warning("Please create a contract first in the registry to run validation checks.")
    else:
        c_names = [c.name for c in contracts]
        selected_c_name = st.selectbox("Select Target Contract", c_names)
        
        contract = registry.get_contract_by_name(selected_c_name)
        latest_version = registry.get_latest_version(contract.id)
        latest_schema_dict = json.loads(latest_version.schema_json)
        contract_obj = ContractSchema(**latest_schema_dict)

        # Set default inputs based on selected contract
        sample_payload = []
        if selected_c_name == "user_contract":
            sample_payload = [
                {"user_id": "usr_005", "email": "valid_user@corp.com", "age": 30, "country": "US", "signup_timestamp": "2026-06-03T12:00:00Z"},
                {"user_id": "usr_006", "email": "mismatched_age_user", "age": "thirty-two", "country": "US", "signup_timestamp": "2026-06-03T12:00:00Z"},
                {"user_id": "usr_005", "email": "duplicate_id_user@corp.com", "age": 25, "country": "CA", "signup_timestamp": "2026-06-03T12:05:00Z"}
            ]
        elif selected_c_name == "transaction_contract":
            sample_payload = [
                {"transaction_id": "tx_9901", "user_id": "usr_001", "amount": 88.0, "status": "completed"},
                {"transaction_id": "tx_9902", "user_id": "usr_002", "amount": -10.0, "status": "pending"}, # negative amount
                {"transaction_id": "tx_9903", "amount": 42.0, "status": "invalid_status"} # missing user_id & invalid status enum
            ]
        else:
            # Fallback mock payload matching whatever schema exists
            mock_row = {}
            for f in contract_obj.fields:
                if f.type == "string":
                    mock_row[f.name] = "test_string"
                elif f.type in ("integer", "int"):
                    mock_row[f.name] = 100
                elif f.type in ("float", "double"):
                    mock_row[f.name] = 9.99
                elif f.type == "boolean":
                    mock_row[f.name] = True
                else:
                    mock_row[f.name] = None
            sample_payload = [mock_row]

        payload_input = st.text_area(
            "Paste JSON Records Payload (as JSON array/list of objects):",
            value=json.dumps(sample_payload, indent=2),
            height=250
        )
        
        if st.button("Validate Payload against Contract"):
            try:
                records = json.loads(payload_input)
                if not isinstance(records, list):
                    st.error("Payload must be a JSON array containing records (list of objects).")
                else:
                    validator = ContractValidationAgent()
                    report = validator.validate_dataset(records, contract_obj)
                    
                    # Display summary cards
                    st.subheader("Validation Output Card")
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        color = "#10b981" if report["is_valid"] else "#ef4444"
                        status_str = "PASSING" if report["is_valid"] else "FAILED"
                        st.markdown(f"""
                        <div class="glass-card" style="text-align: center;">
                            <div class="metric-label">Compliance Result</div>
                            <div class="metric-value" style="color:{color};">{status_str}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    with col2:
                        st.markdown(f"""
                        <div class="glass-card" style="text-align: center;">
                            <div class="metric-label">Violations Count</div>
                            <div class="metric-value" style="color:#f59e0b;">{report['metrics']['total_violations']}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    with col3:
                        h_color = "#10b981" if report["metrics"]["health_score"] >= 90 else ("#f59e0b" if report["metrics"]["health_score"] >= 70 else "#ef4444")
                        st.markdown(f"""
                        <div class="glass-card" style="text-align: center;">
                            <div class="metric-label">Dataset Health Score</div>
                            <div class="metric-value" style="color:{h_color};">{report['metrics']['health_score']}%</div>
                        </div>
                        """, unsafe_allow_html=True)

                    # List violations
                    st.subheader("Detected Schema Violations")
                    if report["is_valid"]:
                        st.success("Congratulations! Dataset is fully compliant with the contract schema.")
                    else:
                        violations_list = []
                        for v in report["violations"]:
                            violations_list.append({
                                "Violation Type": v["violation_type"],
                                "Field": v["field_name"],
                                "Expected": v["expected_value"],
                                "Actual Value": v["actual_value"],
                                "Record Preview": v["payload_preview"]
                            })
                        st.table(pd.DataFrame(violations_list))
                        
                        # Store in database
                        if st.button("Log these Violations in DB Audit History"):
                            for v in report["violations"]:
                                registry.log_violation(
                                    contract_id=contract.id,
                                    version_id=latest_version.id,
                                    violation_type=v["violation_type"],
                                    field_name=v.get("field_name"),
                                    expected_value=v.get("expected_value"),
                                    actual_value=v.get("actual_value"),
                                    payload_preview=v.get("payload_preview")
                                )
                            st.success(f"Successfully logged {len(report['violations'])} violations in database for auditing.")

                    # Great Expectations Report Card
                    st.subheader("Great Expectations Compliance Report Card")
                    ge_rep = report["ge_report"]
                    
                    st.markdown(f"**Expectation Run Status**: {'PASS' if ge_rep['success'] else 'FAIL'}")
                    st.markdown(f"**Evaluated Expectations**: {ge_rep['statistics']['evaluated_expectations']} | **Successful**: {ge_rep['statistics']['successful_expectations']} | **Success Percent**: {ge_rep['statistics']['success_percent']}%")
                    
                    ge_rows = []
                    for r in ge_rep["results"]:
                        ge_rows.append({
                            "Expectation Type": r["expectation_config"]["expectation_type"],
                            "Args": str(r["expectation_config"]["kwargs"]),
                            "Run Result": "SUCCESS" if r["success"] else "FAILED",
                            "Observed / Details": str(r["result"])
                        })
                    st.dataframe(pd.DataFrame(ge_rows), use_container_width=True)

            except Exception as e:
                st.error(f"Error executing payload validation run: {str(e)}")

# Close session
db.close()
