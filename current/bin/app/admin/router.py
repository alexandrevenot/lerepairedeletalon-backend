import logging
import logging.handlers
import traceback

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import SecretStr
from pymongo.errors import PyMongoError

import app.admin.utils as utils
import app.admin.schemas as schemas
import app.stallions.utils as stallion_utils

from app.dependencies import get_db
from app.auth.utils import verify_password

# configs
config = utils.load_config()
stallions_config = stallion_utils.load_config()

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
router = APIRouter(prefix='/admin')

async def verify_admin_password(password: SecretStr = Query(...)):
    if not verify_password(password.get_secret_value(), config['hashed_password']):
        raise HTTPException(status_code=401, detail='invalid password')

@router.get('/stallions-to-be-validated', response_model=schemas.StallionsToBeValidated)
async def get_stallions_to_be_validated(_ = Depends(verify_admin_password), db = Depends(get_db)):
    nsire_list = []
    try:
        for document in db.stallions.find({"profile_status": "to_be_validated"}, {"n_sire": 1}):
            nsire_list.append(document["n_sire"])
    except PyMongoError as exc:
        logger.error("failed to read db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to read db") from exc

    return schemas.StallionsToBeValidated(nsire_list=nsire_list)

@router.get('/stallion/{nsire}')
async def get_stallion_profile(nsire, _ = Depends(verify_admin_password), db = Depends(get_db)):
    try:
        stallion_in_db = db.stallions.find_one({"n_sire": nsire})
    except PyMongoError as exc:
        logger.error("failed to read db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to read db") from exc

    if stallion_in_db is None:
        raise HTTPException(status_code=404, detail="stallion not found")

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
        'thumbnail_photo',
        'verification_file'
    ]

    fields_to_be_serialized = [
        '_id',
        'owner',
        'birthdate',
        'last_update_timestamp'
    ]

    for field in fields:
        result[field] = stallion_in_db[field]

    for field in fields_to_be_serialized:
        result[field] = str(stallion_in_db[field])

    result["photos"] = [str(oid) for oid in stallion_in_db["photos"]]

    return result

@router.put('/stallion-profile-status')
async def update_stallion_profile_status(
    n_sire: str,
    new_status: str,
    _ = Depends(verify_admin_password),
    db = Depends(get_db)
    ):
    try:
        stallion_in_db = db.stallions.find_one({"n_sire": n_sire})
    except PyMongoError as exc:
        logger.error("failed to read db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to read db") from exc

    if stallion_in_db is None:
        raise HTTPException(status_code=404, detail="stallion not found")

    if new_status not in stallions_config['profile_statuses']:
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
