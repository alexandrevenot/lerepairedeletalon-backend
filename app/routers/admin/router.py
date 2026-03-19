import logging
import logging.handlers
import traceback

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import SecretStr
from pymongo.errors import PyMongoError

from app.config import settings

from ...dependencies import StallionInDBGetter, StallionOwnerInDBGetter, UserInDBGetter, get_db
from ..auth.utils import verify_password
from . import schemas

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
get_stallion_in_db = StallionInDBGetter(logger)
get_user_in_db = UserInDBGetter(logger)
get_stallion_owner_in_db = StallionOwnerInDBGetter(logger)

# routes
router = APIRouter(prefix='/admin')

async def verify_admin_password(password: SecretStr = Query(...)):
    if not verify_password(password.get_secret_value(), settings.admin_hashed_password):
        raise HTTPException(status_code=401, detail='invalid password')

@router.get('/stallions-to-be-validated', response_model=schemas.IdList)
async def get_stallions_to_be_validated(_ = Depends(verify_admin_password), db = Depends(get_db)):
    id_list = []
    try:
        for document in db.stallions.find({"profile_status": "to_be_validated"}, {"_id": 1}):
            id_list.append(str(document["_id"]))
    except PyMongoError as exc:
        logger.error("failed to read db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to read db") from exc

    return schemas.IdList(id_list=id_list)

@router.get('/stallion/{stallion_id}')
async def get_stallion_profile(stallion_in_db = Depends(get_stallion_in_db), _ = Depends(verify_admin_password)):
    result = {}
    fields = [
        'name',
        'breed',
        'n_sire',
        'main_desc',
        'color',
        'height',
        'offspring',
        'performance',
        'pedigree',
        'pedigree_po',
        'stallion_additional_info',
        'stallion_std_negative_tests',
        'stallion_vaccines',
        'production_breeds',
        'cover_specs',
        'cover_additional_info',
        'crossbreeding_advice',
        'location',
        'city',
        'postal_code',
        'dep_name',
        'reg_name',
        'profile_status',
        'thumbnail_photo'
    ]

    fields_to_be_serialized = [
        '_id',
        'handler_id',
        'stallion_owner_id',
        'birthdate',
        'last_update_timestamp'
    ]

    for field in fields:
        result[field] = stallion_in_db[field]

    for field in fields_to_be_serialized:
        result[field] = str(stallion_in_db[field])

    result["photos"] = [str(oid) for oid in stallion_in_db["photos"]]

    return result

@router.get('/stallion-owner/{stallion_owner_id}')
async def get_stallion_owner(stallion_owner_in_db = Depends(get_stallion_owner_in_db), _ = Depends(verify_admin_password)):
    result = {}
    fields = [
        'business_type',
        'firstname',
        'lastname',
        'gender',
        'birthdate',
        'birthplace',
        'citizenship',
        'address_line1',
        'address_line2',
        'address_postal_code',
        'address_city'
    ]

    fields_to_be_serialized = [
        'handler_id'
    ]

    for field in fields:
        result[field] = stallion_owner_in_db[field]

    for field in fields_to_be_serialized:
        result[field] = str(stallion_owner_in_db[field])

    return result

@router.put('/stallion-profile-status/{stallion_id}')
async def update_stallion_profile_status(
    new_status: str,
    stallion_in_db = Depends(get_stallion_in_db),
    _ = Depends(verify_admin_password),
    db = Depends(get_db)
    ):
    if new_status not in settings.profile_statuses:
        raise HTTPException(status_code=403, detail="status does not exist")

    if new_status == stallion_in_db["profile_status"]:
        raise HTTPException(status_code=403, detail="old status = new status")

    try:
        db.stallions.update_one(
            {"_id": stallion_in_db["_id"]},
            {
                "$set": {
                    "profile_status": new_status
                }
            })
    except PyMongoError as exc:
        logger.error("failed to write db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to write db") from exc

    return {"message": "successfully updated stallion profile status"}
