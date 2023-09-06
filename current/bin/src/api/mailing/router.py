import os
import logging
import logging.handlers
import traceback

from fastapi import APIRouter, Depends, HTTPException

import src.api.mailing.utils as utils
import src.api.mailing.schemas as schemas

from src.api.auth.router import get_current_user
from src.api.auth.utils import generate_sensitive_action_code, get_password_hash
from src.database.db import get_db

# configs
global_config = utils.load_global_config()
config = utils.load_config()

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
router = APIRouter(prefix='/mailing')

@router.put('/verify-email-address')
async def verify_email_address(code: str, db = Depends(get_db)):
    try:
        document = db.email_verification_codes.find_one({'code': code})
    except Exception as exc:
        logger.error(f'failed to read db: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail='failed to read db') from exc

    if document is None:
        raise HTTPException(status_code=404, detail='cant find code')
    
    try:
        db.users.update_one(
            {'email': document["email"]},
            {"$set": {
                "email_is_verified": True
            }}
            )
        
    except Exception as exc:
        logger.error(f'failed to read db: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail='failed to write db') from exc

    try:
        db.email_verification_codes.delete_one({'code': code})
    except Exception as exc:
        logger.error(f'failed to read db: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail='failed to write db') from exc

@router.post('/send-email-verification-email')
async def post_send_email_verification_email(current_user = Depends(get_current_user), db = Depends(get_db)):
    if current_user["email_is_verified"]:
        raise HTTPException(status_code=400, detail='email already verified for this user')

    try:
        db.email_verification_codes.delete_one({'email': current_user["email"]})
    except Exception as exc:
        logger.error(f'failed to write db: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail='failed to write db') from exc
    
    try:
        code = generate_sensitive_action_code(current_user["email"], os.urandom(16).hex())

        db.email_verification_codes.insert_one({
            "email": current_user["email"],
            "code": code
        })

        utils.send_email_verification_email(
            f"{current_user['firstname']} {current_user['lastname']}",
            global_config["company_name"],
            config["logo_url"],
            f"{global_config['frontend_url']}{config['email_verification_route']}?code={code}",
            config["service_email"],
            config["password"],
            config["service_email"],
            current_user["email"]
        )
        return {'message': 'successfully sent email verification email'}
    except Exception as exc:
        logger.error(f'failed to send email verification email: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail='failed to send email verification email') from exc
    
@router.post('/send-password-recovery-email')
async def send_password_recovery_email(query: schemas.SendPasswordRecoveryEmailQuery, db = Depends(get_db)):
    try:
        user_in_db = db.users.find_one({"email": query.email})
    except Exception as exc:
        logger.error(f'failed to write db: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail='failed to read db') from exc

    if user_in_db is None:
        raise HTTPException(status_code=404, detail='user not found')

    try:
        db.password_recovery_codes.delete_one({'email': query.email})
    except Exception as exc:
        logger.error(f'failed to write db: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail='failed to write db') from exc

    try:
        code = generate_sensitive_action_code(query.email, os.urandom(16).hex())

        db.password_recovery_codes.insert_one({
            "email": query.email,
            "code": code
        })

        utils.send_password_recovery_email(
            f"{user_in_db['firstname']} {user_in_db['lastname']}",
            global_config["company_name"],
            config["logo_url"],
            f"{global_config['frontend_url']}{config['email_verification_route']}?code={code}",
            config["service_email"],
            config["password"],
            config["service_email"],
            query.email
        )
        return {'message': 'successfully sent password recovery email'}
    except Exception as exc:
        logger.error(f'failed to send password recovery email: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail='failed to send password recovery email') from exc

@router.put('/recover-password')
async def recover_password(query: schemas.RecoverPasswordQuery, db = Depends(get_db)):
    try:
        document = db.password_recovery_codes.find_one({'code': query.code})
    except Exception as exc:
        logger.error(f'failed to read db: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail='failed to read db') from exc

    if document is None:
        raise HTTPException(status_code=404, detail='cant find code')
    
    try:
        db.users.update_one(
            {'email': document["email"]},
            {"$set": {
                "hashedpassword": get_password_hash(query.new_password)
            }}
            )
        
    except Exception as exc:
        logger.error(f'failed to read db: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail='failed to write db') from exc

    try:
        db.password_recovery_codes.delete_one({'code': query.code})
    except Exception as exc:
        logger.error(f'failed to read db: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail='failed to write db') from exc
