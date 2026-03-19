import logging
import logging.handlers
import os
import smtplib
import traceback

from fastapi import APIRouter, Depends, HTTPException
from pymongo.errors import PyMongoError

from ...dependencies import CurrentUserGetter, get_db, get_db_client
from ..auth.utils import generate_sensitive_action_code, get_password_hash
from . import schemas, utils

# logging
logger = logging.getLogger(__name__)
logger.setLevel(20)
handler = logging.handlers.RotatingFileHandler(
    f'logs/{__name__}.log',
    maxBytes=1024 * 1025 * 50,
    backupCount=2,
    mode='a'
    )
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.info('Logger initialized')

# dependencies
get_current_user = CurrentUserGetter(logger)

# routes
router = APIRouter(prefix='/mailing')

@router.put('/verify-email-address')
async def verify_email_address(query: schemas.VerifyEmailQuery, db = Depends(get_db), db_client = Depends(get_db_client)):
    try:
        document = db.email_verification_codes.find_one({'code': query.code})
    except PyMongoError as exc:
        logger.error("failed to read db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail='failed to read db') from exc

    if document is None:
        raise HTTPException(status_code=403, detail='invalid email verifying code')

    with db_client.start_session() as session:
        session.start_transaction()
        try:
            db.users.update_one(
                {'email': document["email"]},
                {"$set": {
                    "email_is_verified": True
                }},
                session=session
            )

            db.email_verification_codes.delete_one({'code': query.code}, session=session)
            session.commit_transaction()

        except PyMongoError as exc:
            session.abort_transaction()
            logger.error("failed to read db: %s", traceback.format_exc())
            raise HTTPException(status_code=500, detail='failed to write db') from exc

    return {"message": "successfully verified email"}

@router.post('/send-email-verification-email')
async def post_send_email_verification_email(current_user = Depends(get_current_user), db = Depends(get_db), db_client = Depends(get_db_client)):
    if current_user["email_is_verified"]:
        raise HTTPException(status_code=400, detail='email already verified for this user')

    with db_client.start_session() as session:
        session.start_transaction()
        try:
            db.email_verification_codes.delete_one({'email': current_user["email"]}, session=session)

            code = generate_sensitive_action_code(current_user["email"], os.urandom(16).hex())

            db.email_verification_codes.insert_one(
                {
                    "email": current_user["email"],
                    "code": code
                },
                session=session
            )

            utils.send_action_email(
                "email_verification",
                f"{current_user['firstname']} {current_user['lastname']}",
                code,
                current_user["email"]
            )
            session.commit_transaction()

        except PyMongoError as exc:
            session.abort_transaction()
            logger.error('failed to write db: %s', traceback.format_exc())
            raise HTTPException(status_code=500, detail='failed to write db') from exc

        except smtplib.SMTPException as exc:
            session.abort_transaction()
            logger.error('failed to send email verification email: %s', traceback.format_exc())
            raise HTTPException(status_code=500, detail='failed to send email verification email') from exc

    return {'message': 'successfully sent email verification email'}

@router.post('/send-password-update-email')
async def send_password_update_email(query: schemas.SendPasswordUpdateEmailQuery, db = Depends(get_db), db_client = Depends(get_db_client)):
    try:
        user_in_db = db.users.find_one({"email": query.email})
    except PyMongoError as exc:
        logger.error('failed to read db: %s', traceback.format_exc())
        raise HTTPException(status_code=500, detail='failed to read db') from exc

    if user_in_db is None:
        raise HTTPException(status_code=404, detail='user not found')

    with db_client.start_session() as session:
        session.start_transaction()
        try:
            db.password_update_codes.delete_one({'email': query.email}, session=session)

            code = generate_sensitive_action_code(query.email, os.urandom(16).hex())

            db.password_update_codes.insert_one(
                {
                    "email": query.email,
                    "code": code
                },
                session=session
            )

            utils.send_action_email(
                "password_update",
                f"{user_in_db['firstname']} {user_in_db['lastname']}",
                code,
                query.email
            )
            session.commit_transaction()

        except PyMongoError as exc:
            session.abort_transaction()
            logger.error('failed to write db: %s', traceback.format_exc())
            raise HTTPException(status_code=500, detail='failed to write db') from exc

        except smtplib.SMTPException as exc:
            session.abort_transaction()
            logger.error('failed to send password update email: %s', traceback.format_exc())
            raise HTTPException(status_code=500, detail='failed to send password update email') from exc

    return {'message': 'successfully sent password update email'}

@router.put('/update-password')
async def update_password(query: schemas.UpdatePasswordQuery, db = Depends(get_db), db_client = Depends(get_db_client)):
    try:
        document = db.password_update_codes.find_one({'code': query.code})
    except PyMongoError as exc:
        logger.error("failed to read db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail='failed to read db') from exc

    if document is None:
        raise HTTPException(status_code=403, detail='invalid password update code')

    with db_client.start_session() as session:
        session.start_transaction()
        try:
            db.users.update_one(
                {'email': document["email"]},
                {"$set": {
                    "hashedpassword": get_password_hash(query.new_password)
                }},
                session=session
            )

            db.password_update_codes.delete_one({'code': query.code}, session=session)
            session.commit_transaction()

        except PyMongoError as exc:
            session.abort_transaction()
            logger.error("failed to write db: %s", traceback.format_exc())
            raise HTTPException(status_code=500, detail='failed to write db') from exc

    return {"message": "successfully updated password"}
