import traceback
from bson.objectid import ObjectId
from typing import Annotated

import yaml
from fastapi import HTTPException, Depends, Path, Header
from pymongo import MongoClient

import app.auth.utils as auth_utils

with open('/lerepairedeletalon/server/current/etc/config.yaml', 'r') as f:
    config = yaml.load(f, Loader=yaml.FullLoader)

class DBConnection:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.client = MongoClient(config['mongo_url'])
            cls._instance.db = getattr(cls._instance.client, config['db_to_use'])
        return cls._instance

def get_db():
    return DBConnection().db

async def get_user_from_object_id(user_id: ObjectId, db, logger):
    try:
        user_in_db = db.users.find_one({"_id": user_id})
    except Exception as exc:
        logger.error(f'failed to read db: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail="failed to read db") from exc

    if user_in_db is None:
        raise HTTPException(status_code=404, detail="user not found")

    return user_in_db

class UserInDBGetter:
    def __init__(self, logger):
        self.logger = logger

    async def __call__(self, user_id: str = Path(...), db = Depends(get_db)):
        try:
            user_id = ObjectId(user_id)
        except Exception as exc:
            raise HTTPException(status_code=422, detail="user_id not readable") from exc

        return await get_user_from_object_id(user_id, db, self.logger)

class CurrentUserGetter:
    def __init__(self, logger):
        self.logger = logger

    async def __call__(self, authorization: Annotated[str | None, Header()] = None, db = Depends(get_db)):
        try:
            fields = authorization.split(' ')
            token = fields[1]
        except Exception as exc:
            raise HTTPException(status_code=401, detail='token not found in the request') from exc

        _id = auth_utils.verify_token(token, 'access')

        try:
            user_in_db = db.users.find_one({'_id': _id})
        except Exception as exc:
            self.logger.error(f'failed to read db: {traceback.format_exc()}')
            raise HTTPException(status_code=500, detail='failed to read db') from exc

        if user_in_db is None:
            raise HTTPException(status_code=404, detail='user not found')
        return user_in_db

class CoverInDBGetter:
    def __init__(self, logger):
        self.logger = logger

    async def __call__(self, cover_id: str = Path(...), db = Depends(get_db)):
        try:
            cover_id = ObjectId(cover_id)
        except Exception as exc:
            raise HTTPException(status_code=422, detail="cover_id not readable") from exc

        try:
            cover_in_db = db.covers.find_one({"_id": cover_id})
        except Exception as exc:
            self.logger.error("failed to read db: %s", traceback.format_exc())
            raise HTTPException(status_code=500, detail="failed to read db") from exc

        if cover_in_db is None:
            raise HTTPException(status_code=404, detail="cover not found")

        return cover_in_db
