import traceback
from typing import Annotated

from pymongo import MongoClient
from fastapi import APIRouter, Depends, HTTPException, Header

import src.api.auth.utils as utils
import src.api.auth.schemas as schemas

# config
config = utils.load_config()

# db
mongo_url = "mongodb://localhost:27017/"
client = MongoClient(mongo_url)
db = client.test
users_c = db.users

# routes
router = APIRouter(prefix='/auth')

@router.post('/register')
async def register(user: schemas.RegisterQuery):
    try:
        user_in_db = users_c.find_one({"email": user.email})
    except:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to read users collection")

    if user_in_db is not None:
        raise HTTPException(status_code=400, detail="a user already exists with this email")
    else:
        user_to_create = schemas.UserInDB(
            firstname = user.firstname,
            lastname = user.lastname,
            email = user.email,
            hashedpassword = utils.get_password_hash(user.password)
        )

        try:
            users_c.insert_one(user_to_create.dict())
            return {"message": "successfully registered user"}

        except:
            print(traceback.format_exc())
            raise HTTPException(status_code=500, detail="failed to write users collection")

@router.post('/login')
async def login(user: schemas.LoginQuery):
    try:
        users = users_c.find({"email": user.email})
    except:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to read users collection")
    
    try:
        user_in_db = users.next()
    except:
        raise HTTPException(status_code=404, detail="user not found")

    if not utils.verify_password(user.password, user_in_db["hashedpassword"]):
        raise HTTPException(status_code=401, detail="invalid credentials")
    else:
        return {
            "accessToken": utils.create_access_token(user_in_db, config['access_token_expire_minutes']),
            "refreshToken": utils.create_refresh_token(user_in_db, config['refresh_token_expire_days'])
        }

@router.post('/refresh-token')
async def refresh_token(query: schemas.RefreshTokenQuery):
    _id = utils.verify_token(query.token, "refresh")

    try:
        users = users_c.find({"_id": _id})
        user_in_db = users.next()
    except:
        raise HTTPException(status_code=401)

    return {
        "accessToken": utils.create_access_token(user_in_db, config['access_token_expire_minutes']),
        "refreshToken": utils.create_refresh_token(user_in_db, config['refresh_token_expire_days'])
    }

async def get_current_user(authorization: Annotated[str | None, Header()] = None):
    fields = authorization.split(' ')
    if len(fields) != 2:
        raise HTTPException(status_code=422, detail="token not found in the request")

    _id = utils.verify_token(fields[1], "access")

    try:
        users = users_c.find({"_id": _id})
        return users.next()
    except:
        print(traceback.format_exc())
        raise HTTPException(status_code=401)

@router.get('/protected-route')
async def gg(current_user = Depends(get_current_user)):
    return {"message": "gg"}