from pydantic import BaseModel, Field
from typing import Dict, Any

class Node(BaseModel):
    id: str = Field(..., description="Unique identifier for the node")
    label: str = Field(..., description="Node type, e.g., API, TABLE, PIPELINE")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary key/value pairs")

class Relationship(BaseModel):
    start_node: str = Field(..., description="ID of the source node")
    end_node: str = Field(..., description="ID of the target node")
    type: str = Field(..., description="Relationship type, e.g., FEEDS, DEPENDS_ON")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Optional edge properties")
