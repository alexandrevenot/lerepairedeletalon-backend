import json
from datetime import datetime, timedelta
import hashlib

import yaml
from fastapi import HTTPException
from bson import ObjectId
from jose import jwt
from passlib.context import CryptContext

ACCESS_SECRET_KEY = "433c8905cbe2837e7f68b9c3f0775eb044b090c55dc54006168a46efabb4c351"
REFRESH_SECRET_KEY = "f2e57723a47668afdf5f605d916c392e4f9e2c988bb432c748c9b08aea58f329"
ALGORITHM = "HS256"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def load_global_config() -> dict:
    with open('/lerepairedeletalon/server/current/etc/config.yaml', 'r') as f:
        return yaml.load(f, Loader=yaml.FullLoader)

def load_config() -> dict:
    with open('/lerepairedeletalon/server/current/etc/auth/config.yaml', 'r') as f:
        return yaml.load(f, Loader=yaml.FullLoader)

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
    encoded_jwt = jwt.encode(to_encode, ACCESS_SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict, duration: int):
    to_encode = {}
    to_encode["_id"] = str(data["_id"])
    expire = datetime.utcnow() + timedelta(days=duration)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, REFRESH_SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str, token_type: str):
    key = REFRESH_SECRET_KEY if token_type == "refresh" else ACCESS_SECRET_KEY
    try:
        payload = jwt.decode(token, key, algorithms=[ALGORITHM])
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
