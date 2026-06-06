from typing import Dict, List
from src.graph.neo4j_driver import run_query
from src.graph.models import Node, Relationship

# Simple mapping from metadata keys to node labels
_LABEL_MAP = {
    "api": "API",
    "table": "TABLE",
    "column": "COLUMN",
    "pipeline": "PIPELINE",
    "contract": "CONTRACT",
    "model": "MODEL",
    "dashboard": "DASHBOARD",
    "business_domain": "BUSINESS_DOMAIN",
    "owner": "OWNER",
}

def _create_node(node: Node):
    query = (
        "MERGE (n:{label} {{id: $id}}) "
        "SET n += $props "
    ).format(label=node.label)
    run_query(query, {"id": node.id, "props": node.properties})

def _create_relationship(rel: Relationship):
    query = (
        "MATCH (a {{id: $start}}), (b {{id: $end}}) "
        "MERGE (a)-[r:{type}]->(b) "
        "SET r += $props "
    ).format(type=rel.type)
    run_query(query, {"start": rel.start_node, "end": rel.end_node, "props": rel.properties})

def build_graph(metadata: Dict) -> None:
    """Transform discovered metadata into Neo4j graph.
    Expected `metadata` format (example)::
        {
            "apis": [{"id": "api_1", "name": "Orders API"}],
            "tables": [{"id": "tbl_orders", "name": "orders"}],
            "relationships": [
                {"source": "api_1", "target": "tbl_orders", "type": "FEEDS"}
            ]
        }
    """
    # Create nodes
    for collection_name, items in metadata.items():
        if collection_name == "relationships":
            continue
        label = _LABEL_MAP.get(collection_name.rstrip('s'), collection_name.upper())
        for item in items:
            node = Node(id=item["id"], label=label, properties=item)
            _create_node(node)
    # Create relationships
    for rel in metadata.get("relationships", []):
        relationship = Relationship(
            start_node=rel["source"],
            end_node=rel["target"],
            type=rel["type"],
            properties=rel.get("properties", {}),
        )
        _create_relationship(relationship)
