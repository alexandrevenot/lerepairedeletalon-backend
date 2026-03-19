import hashlib
import json
from datetime import datetime, timedelta

from bson import ObjectId
from fastapi import HTTPException
from jose import jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        elif isinstance(o, datetime):
            return o.isoformat()
        return json.JSONEncoder.default(self, o)

def create_access_token(data: dict, duration: int):
    to_encode = {}
    to_encode["_id"] = str(data["_id"])
    expire = datetime.utcnow() + timedelta(minutes=duration)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.access_secret_key, algorithm=settings.algorithm)
    return encoded_jwt

def create_refresh_token(data: dict, duration: int):
    to_encode = {}
    to_encode["_id"] = str(data["_id"])
    expire = datetime.utcnow() + timedelta(days=duration)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.refresh_secret_key, algorithm=settings.algorithm)
    return encoded_jwt

def verify_token(token: str, token_type: str):
    key = settings.refresh_secret_key if token_type == "refresh" else settings.access_secret_key
    try:
        payload = jwt.decode(token, key, algorithms=[settings.algorithm])
    except Exception as exc:
        raise HTTPException(status_code=401, detail="invalid token") from exc

    _id = payload.get("_id")

    if _id is None:
        raise HTTPException(status_code=401)

    return ObjectId(_id)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def generate_sensitive_action_code(chain: str, salt: str):
    data_to_hash = chain + salt
    hasher = hashlib.sha256()
    hasher.update(data_to_hash.encode('utf-8'))
    return hasher.hexdigest()
