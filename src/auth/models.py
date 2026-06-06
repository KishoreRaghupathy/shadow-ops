from enum import Enum
from pydantic import BaseModel, Field

class Role(str, Enum):
    ADMIN = "admin"
    DATA_ENGINEER = "data_engineer"
    DATA_STEWARD = "data_steward"
    VIEWER = "viewer"
    SERVICE_ACCOUNT = "service_account"

class User(BaseModel):
    username: str = Field(..., example="jdoe")
    hashed_password: str = Field(..., example="$2b$12$...")
    role: Role
    active: bool = True

    class Config:
        orm_mode = True
