import os
import jwt
from datetime import datetime
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

from config.settings import settings
from src.auth.models import Role, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

class TokenData(BaseModel):
    sub: str
    roles: list[str] = []
    exp: int

def decode_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return TokenData(**payload)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    token_data = decode_token(token)
    # In a real system retrieve user from DB; here we mock a user object
    user = User(username=token_data.sub, roles=token_data.roles)
    return user

def require_role(required_role: Role):
    async def role_dependency(user: User = Depends(get_current_user)):
        if required_role.value not in user.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions; required role: {required_role.value}"
            )
        return user
    return role_dependency
