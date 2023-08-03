import traceback
from typing import Annotated

from pymongo import MongoClient
from fastapi import APIRouter, Depends, HTTPException, Header

import src.api.auth.utils as utils
import src.api.auth.schemas as schemas

# global config
global_config = utils.load_global_config()

# config
config = utils.load_config()

# db
mongo_url = "mongodb://localhost:27017/"
client = MongoClient(mongo_url)
db = getattr(client, global_config['db_to_use'])
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
            phone_number = user.phone_number,
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
    try:
        fields = authorization.split(' ')
        token = fields[1]
    except:
        raise HTTPException(status_code=401, detail="token not found in the request")

    _id = utils.verify_token(token, "access")

    try:
        users = users_c.find({"_id": _id})
        return users.next()
    except:
        print(traceback.format_exc())
        raise HTTPException(status_code=401)

@router.get('/get-user')
async def get_user(current_user = Depends(get_current_user)):
    return schemas.GetUserRM(
        firstname=current_user['firstname'],
        lastname=current_user['lastname']
    )

async def get_user_info(id):
    try:
        user = users_c.find_one({"_id": id})
    except:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to read users collection")
    
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    
    return user

@router.get('/profile-information', response_model=schemas.GetProfileInformation)
async def get_profile_information(current_user = Depends(get_current_user)):
    try:
        user = users_c.find_one({"_id": current_user["_id"]})
    except:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to read users collection")
    
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    
    try:
        return schemas.GetProfileInformation(
            type=user["contract-identity"]["type"],
            company_name=user["contract-identity"]['company_name'],
            company_status=user["contract-identity"]['company_status'],
            head_office_address=user["contract-identity"]['head_office_address'],
            siret=user["contract-identity"]['siret'],
            postal_address=user["contract-identity"]['postal_address'],
            birthdate=user["contract-identity"]['birthdate'],
            birthplace=user["contract-identity"]['birthplace'],
            citizenship=user["contract-identity"]['citizenship'],
            gender=user["contract-identity"]['gender']
        )

    except:
        try:
            return schemas.GetProfileInformation(
                type=user["contract-identity"]["type"],
                postal_address=user["contract-identity"]['postal_address'],
                birthdate=user["contract-identity"]['birthdate'],
                birthplace=user["contract-identity"]['birthplace'],
                citizenship=user["contract-identity"]['citizenship'],
                gender=user["contract-identity"]['gender']
            )
        except:
            raise HTTPException(status_code=404, detail="profile information not found")

@router.put('/profile-information')
async def put_profile_information(query: schemas.PutProfileInformationQuery, current_user = Depends(get_current_user)):
    try:
        user = users_c.find_one({"_id": current_user["_id"]})
    except:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to read users collection")
    
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    
    try:
        update = {
                '$set': {
                    'contract-identity': {
                    }
                }
            }

        if query.type == "company":
            for field in ["type","company_name", "company_status", "head_office_address", "siret"]:
                update["$set"]["contract-identity"][field] = getattr(query, field)
        else:
            update["$set"]["contract-identity"]["type"] = query.type

        for field in ["gender", "postal_address", "birthdate", "birthplace", "citizenship"]:
            update["$set"]["contract-identity"][field] = getattr(query, field)
        
        users_c.update_one({"_id": current_user["_id"]}, update)

        return {"message": "successfully put profile information"}
    except:
        raise HTTPException(status_code=500, detail="unable to put profile information")