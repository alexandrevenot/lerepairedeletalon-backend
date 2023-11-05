import os
import logging
import logging.handlers
import traceback
from typing import Annotated
from bson.objectid import ObjectId

from fastapi import APIRouter, Depends, HTTPException, Header

import src.api.auth.utils as utils
import src.api.auth.schemas as schemas

import src.api.mailing.utils as mailing_utils

from src.database.db import get_db

# configs
global_config = utils.load_global_config()
config = utils.load_config()
mailing_config = mailing_utils.load_config()

# logging
logger = logging.getLogger(__name__)
logger.setLevel(20)
handler = logging.handlers.RotatingFileHandler(
    f'/lerepairedeletalon/server/import/var/log/API/{__name__}.log',
    maxBytes=1024 * 1025 * 50,
    backupCount=2,
    mode='a'
    )
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.info('Logger initialized')

# routes
router = APIRouter(prefix='/auth')

@router.post('/register')
async def register(user: schemas.RegisterQuery, db = Depends(get_db)):
    try:
        user_in_db = db.users.find_one({'email': user.email})
    except Exception as exc:
        logger.error(f'failed to read db: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail='failed to read db') from exc

    if user_in_db is not None:
        raise HTTPException(status_code=400, detail='a user already exists with this email')
    else:
        user_to_create = schemas.UserInDB(
            firstname = user.firstname,
            lastname = user.lastname,
            email = user.email,
            phone_number = user.phone_number,
            hashedpassword = utils.get_password_hash(user.password),
            email_is_verified = False
        )

        try:
            db.users.insert_one(user_to_create.model_dump())

        except Exception as exc:
            logger.error(f'failed to write db: {traceback.format_exc()}')
            raise HTTPException(status_code=500, detail='failed to write db') from exc
        
        try:
            code = utils.generate_sensitive_action_code(user.email, os.urandom(16).hex())

            db.email_verification_codes.insert_one({
                "email": user.email,
                "code": code
            })

            mailing_utils.send_email_verification_email(
                f"{user.firstname} {user.lastname}",
                global_config["company_name"],
                mailing_config["logo_url"],
                f"{global_config['frontend_url']}{mailing_config['email_verification_route']}?code={code}",
                mailing_config["service_email"],
                mailing_config["password"],
                mailing_config["service_email"],
                user.email
            )
            return {'message': 'successfully registered user'}
        except Exception as exc:
            logger.error(f'failed to send email verification email: {traceback.format_exc()}')
            raise HTTPException(status_code=500, detail='failed to send email verification email') from exc


@router.post('/login')
async def login(user: schemas.LoginQuery, db = Depends(get_db)):
    try:
        user_in_db = db.users.find_one({'email': user.email})
    except Exception as exc:
        logger.error(f'failed to read db: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail='failed to read db') from exc
    
    if user_in_db is None:
        raise HTTPException(status_code=404, detail='user not found')

    if not utils.verify_password(user.password, user_in_db['hashedpassword']):
        raise HTTPException(status_code=401, detail='invalid credentials')
    else:
        return {
            'accessToken': utils.create_access_token(user_in_db, config['access_token_expire_minutes']),
            'refreshToken': utils.create_refresh_token(user_in_db, config['refresh_token_expire_days'])
        }

@router.post('/refresh-token')
async def refresh_token(query: schemas.RefreshTokenQuery, db = Depends(get_db)):
    _id = utils.verify_token(query.token, 'refresh')

    try:
        user_in_db = db.users.find_one({'_id': _id})
    except Exception as exc:
        logger.error(f'failed to read db: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail='failed to read db') from exc

    if user_in_db is None:
        raise HTTPException(status_code=404, detail='user not found')

    return {
        'accessToken': utils.create_access_token(user_in_db, config['access_token_expire_minutes']),
        'refreshToken': utils.create_refresh_token(user_in_db, config['refresh_token_expire_days'])
    }

async def get_current_user(authorization: Annotated[str | None, Header()] = None, db = Depends(get_db)):
    try:
        fields = authorization.split(' ')
        token = fields[1]
    except Exception as exc:
        raise HTTPException(status_code=401, detail='token not found in the request') from exc

    _id = utils.verify_token(token, 'access')

    try:
        user_in_db = db.users.find_one({'_id': _id})
    except Exception as exc:
        logger.error(f'failed to read db: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail='failed to read db') from exc

    if user_in_db is None:
        raise HTTPException(status_code=404, detail='user not found')
    else:
        return user_in_db

@router.get('/user-name')
async def get_user(current_user = Depends(get_current_user)):
    return schemas.GetUserRM(
        firstname=current_user['firstname'],
        lastname=current_user['lastname']
    )

@router.get('/contracts-identity', response_model=schemas.GetContractsIdentity)
async def get_contract_identity(current_user = Depends(get_current_user)):
    try:
        return schemas.GetContractsIdentity(
            type=current_user['contract_identity']['type'],
            company_name=current_user['contract_identity']['company_name'],
            company_status=current_user['contract_identity']['company_status'],
            capital=current_user['contract_identity']['capital'],
            head_office_address=current_user['contract_identity']['head_office_address'],
            siret=current_user['contract_identity']['siret'],
            postal_address=current_user['contract_identity']['postal_address'],
            birthdate=current_user['contract_identity']['birthdate'],
            birthplace=current_user['contract_identity']['birthplace'],
            citizenship=current_user['contract_identity']['citizenship'],
            gender=current_user['contract_identity']['gender']
        )

    except Exception:
        try:
            return schemas.GetContractsIdentity(
                type=current_user['contract_identity']['type'],
                postal_address=current_user['contract_identity']['postal_address'],
                birthdate=current_user['contract_identity']['birthdate'],
                birthplace=current_user['contract_identity']['birthplace'],
                citizenship=current_user['contract_identity']['citizenship'],
                gender=current_user['contract_identity']['gender']
            )
        except Exception as exc:
            raise HTTPException(status_code=404, detail='profile information not found') from exc

@router.put('/contracts-identity')
async def put_contracts_identity(query: schemas.PutContractsIdentityQuery, current_user = Depends(get_current_user), db = Depends(get_db)):
    try:
        update = {
                '$set': {
                    'contract_identity': {
                    }
                }
            }

        if query.type == 'company':
            for field in ['type','company_name', 'company_status', 'capital', 'head_office_address', 'siret']:
                update['$set']['contract_identity'][field] = getattr(query, field)
        else:
            update['$set']['contract_identity']['type'] = query.type

        for field in ['gender', 'postal_address', 'birthdate', 'birthplace', 'citizenship']:
            update['$set']['contract_identity'][field] = getattr(query, field)
        
        db.users.update_one({'_id': current_user['_id']}, update)

        return {'message': 'successfully put profile information'}
    except Exception as exc:
        raise HTTPException(status_code=500, detail='unable to put profile information') from exc

async def get_user_from_id(user_id: ObjectId, db):
    try:
        user_in_db = db.users.find_one({"_id": user_id})
    except Exception as exc:
        logger.error(f'failed to read db: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail="failed to read db") from exc
    
    if user_in_db is None:
        raise HTTPException(status_code=404, detail="user not found")
    
    return user_in_db