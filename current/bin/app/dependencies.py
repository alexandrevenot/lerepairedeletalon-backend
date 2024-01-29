import traceback
from bson.objectid import ObjectId
from typing import Annotated

import yaml
from fastapi import HTTPException, Depends, Path, Header
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from google.cloud import storage

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

def get_db_client():
    return DBConnection().client

async def get_user_from_object_id(user_id: ObjectId, db, logger):
    try:
        user_in_db = db.users.find_one({"_id": user_id})
    except PyMongoError as exc:
        logger.error('failed to read db: %s', traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to read db") from exc

    if user_in_db is None:
        raise HTTPException(status_code=404, detail="user not found")

    return user_in_db

class UserInDBGetter:
    def __init__(self, logger):
        self.logger = logger

    async def __call__(self, user_id: str = Path(...), db = Depends(get_db)):
        if not ObjectId.is_valid(user_id):
            raise HTTPException(status_code=422, detail="user_id is not readable")

        user_id = ObjectId(user_id)

        return await get_user_from_object_id(user_id, db, self.logger)

class CurrentUserGetter:
    def __init__(self, logger):
        self.logger = logger

    async def __call__(self, authorization: Annotated[str | None, Header()] = None, db = Depends(get_db)):
        try:
            fields = authorization.split(' ')
            token = fields[1]
        except (IndexError, AttributeError) as exc:
            raise HTTPException(status_code=401, detail='token not found in the request') from exc

        _id = auth_utils.verify_token(token, 'access')

        try:
            user_in_db = db.users.find_one({'_id': _id})
        except PyMongoError as exc:
            self.logger.error('failed to read db: %s', traceback.format_exc())
            raise HTTPException(status_code=500, detail='failed to read db') from exc

        if user_in_db is None:
            raise HTTPException(status_code=404, detail='user not found')

        return user_in_db

async def get_current_user_id(authorization: Annotated[str | None, Header()] = None):
    try:
        fields = authorization.split(' ')
        token = fields[1]
    except (IndexError, AttributeError) as exc:
        raise HTTPException(status_code=401, detail='token not found in the request') from exc

    return auth_utils.verify_token(token, 'access')

class CoverInDBGetter:
    def __init__(self, logger):
        self.logger = logger

    async def __call__(self, cover_id: str = Path(...), db = Depends(get_db)):
        if not ObjectId.is_valid(cover_id):
            raise HTTPException(status_code=422, detail="cover_id not readable")

        cover_id = ObjectId(cover_id)

        try:
            cover_in_db = db.covers.find_one({"_id": cover_id})
        except PyMongoError as exc:
            self.logger.error("failed to read db: %s", traceback.format_exc())
            raise HTTPException(status_code=500, detail="failed to read db") from exc

        if cover_in_db is None:
            raise HTTPException(status_code=404, detail="cover not found")

        return cover_in_db

class StallionInDBGetter:
    def __init__(self, logger):
        self.logger = logger

    async def __call__(self, stallion_id: str = Path(...), db = Depends(get_db)):
        if not ObjectId.is_valid(stallion_id):
            raise HTTPException(status_code=422, detail="stallion_id not readable")

        stallion_id = ObjectId(stallion_id)

        try:
            stallion_in_db = db.stallions.find_one({"_id": stallion_id})
        except PyMongoError as exc:
            self.logger.error("failed to read db: %s", traceback.format_exc())
            raise HTTPException(status_code=500, detail="failed to read db") from exc

        if stallion_in_db is None:
            raise HTTPException(status_code=404, detail="stallion not found")

        return stallion_in_db

class ObjectStorageManager:
    _instance = None

    def __new__(cls, bucket_name: str):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.client = storage.Client()
            cls._instance.buckets = {}

        if bucket_name not in cls._instance.buckets.keys():
            cls._instance.buckets[bucket_name] = cls._instance.client.bucket(bucket_name)

        return cls._instance

class BucketGetter:
    def __init__(self, bucket_name: str):
        self.bucket_name = bucket_name

    async def __call__(self):
        return ObjectStorageManager(self.bucket_name).buckets[self.bucket_name]
