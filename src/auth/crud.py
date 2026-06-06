from typing import Dict
from src.auth.models import User, Role

# Simple in‑memory store – replace with DB later
_user_store: Dict[str, User] = {}


def create_user(username: str, password_hash: str, role: Role) -> User:
    if username in _user_store:
        raise ValueError("User already exists")
    user = User(username=username, hashed_password=password_hash, role=role)
    _user_store[username] = user
    return user


def get_user(username: str) -> User:
    return _user_store.get(username)


def authenticate_user(username: str, password: str, verify_func) -> User:
    user = get_user(username)
    if not user:
        return None
    if not verify_func(password, user.hashed_password):
        return None
    return user
