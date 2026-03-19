import logging
import logging.handlers
import os
import smtplib
import traceback
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pymongo.errors import PyMongoError

from app.config import settings

from ...dependencies import get_db, get_db_client
from ...monitoring import tools as monitoring_tools
from ..mailing import utils as mailing_utils
from . import schemas, utils

# logging
log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(exist_ok=True)
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

# routes
router = APIRouter(prefix='/auth')

@router.post('/register')
async def register(
    user: schemas.RegisterQuery,
    background_tasks: BackgroundTasks,
    db = Depends(get_db),
    db_client = Depends(get_db_client)
):
    try:
        user_in_db = db.users.find_one({'email': user.email})
    except PyMongoError as exc:
        logger.error('failed to read db: %s', traceback.format_exc())
        raise HTTPException(status_code=500, detail='failed to read db') from exc

    if user_in_db is not None:
        raise HTTPException(status_code=400, detail='a user already exists with this email')

    user_to_create = {
        "firstname": user.firstname,
        "lastname": user.lastname,
        "email": user.email,
        "phone_number": user.phone_number,
        "hashedpassword": utils.get_password_hash(user.password),
        "email_is_verified": False
    }

    with db_client.start_session() as session:
        session.start_transaction()
        try:
            db.users.insert_one(user_to_create, session=session)

            code = utils.generate_sensitive_action_code(user.email, os.urandom(16).hex())

            db.email_verification_codes.insert_one(
                {
                    "email": user.email,
                    "code": code
                },
                session=session
            )

            mailing_utils.send_action_email(
                "email_verification",
                f"{user.firstname} {user.lastname}",
                code,
                user.email
            )
            session.commit_transaction()
            background_tasks.add_task(
                monitoring_tools.send_telegram_message,
                f"Un compte vient d'être créé\n*Prénom*: {user.firstname}\n*Nom*: {user.lastname}",
                settings.telegram_api_key,
                logger
            )

        except PyMongoError as exc:
            session.abort_transaction()
            logger.error('failed to write db: %s', traceback.format_exc())
            raise HTTPException(status_code=500, detail='failed to write db') from exc

        except smtplib.SMTPException as exc:
            session.abort_transaction()
            logger.error('failed to send email verification email: %s', traceback.format_exc())
            raise HTTPException(status_code=500, detail='failed to send email verification email') from exc

    return {'message': 'successfully registered user'}

@router.post('/login')
async def login(user: schemas.LoginQuery, db = Depends(get_db)):
    try:
        user_in_db = db.users.find_one({'email': user.email})
    except PyMongoError as exc:
        logger.error('failed to read db: %s', traceback.format_exc())
        raise HTTPException(status_code=500, detail='failed to read db') from exc

    if user_in_db is None:
        raise HTTPException(status_code=404, detail='user not found')

    if not utils.verify_password(user.password, user_in_db['hashedpassword']):
        raise HTTPException(status_code=401, detail='invalid credentials')

    return {
        'accessToken': utils.create_access_token(user_in_db, settings.access_token_expire_minutes),
        'refreshToken': utils.create_refresh_token(user_in_db, settings.refresh_token_expire_days)
    }

@router.post('/refresh-token')
async def refresh_token(query: schemas.RefreshTokenQuery, db = Depends(get_db)):
    _id = utils.verify_token(query.token, 'refresh')

    try:
        user_in_db = db.users.find_one({'_id': _id})
    except PyMongoError as exc:
        logger.error('failed to read db: %s', traceback.format_exc())
        raise HTTPException(status_code=500, detail='failed to read db') from exc

    if user_in_db is None:
        raise HTTPException(status_code=404, detail='user not found')

    return {
        'accessToken': utils.create_access_token(user_in_db, settings.access_token_expire_minutes),
        'refreshToken': utils.create_refresh_token(user_in_db, settings.refresh_token_expire_days)
    }
