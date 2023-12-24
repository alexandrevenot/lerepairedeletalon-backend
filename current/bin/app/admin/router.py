import logging
import logging.handlers
import traceback

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import SecretStr

import app.admin.utils as utils
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

@router.put('/stallion-profile-status')
async def update_stallion_profile_status(
    n_sire: str,
    new_status: str,
    _ = Depends(verify_admin_password),
    db = Depends(get_db)
    ):
    try:
        stallion_in_db = db.stallions.find_one({"n_sire": n_sire})
    except Exception as exc:
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
    except Exception as exc:
        logger.error("failed to write db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to write db") from exc

    return {"message": "successfully updated stallion profile status"}
