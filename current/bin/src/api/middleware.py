import json
from datetime import datetime
from bson.objectid import ObjectId

from fastapi import Request

from src.database.db import get_db

class Middleware:
    async def __call__(self, request: Request, call_next):
        return await call_next(request)
