import logging
import logging.handlers
import traceback
from bson.objectid import ObjectId

from fastapi import APIRouter, Depends, HTTPException

import src.api.contracts.utils as utils
import src.api.contracts.schemas as schemas
import src.api.covers.router as covers_router
import src.api.covers.schemas as covers_schemas

from src.api.auth.router import get_current_user, get_user_from_id
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
router = APIRouter(prefix='/contracts')

@router.post('/engage-signature-process')
async def engage_signature_process(query: schemas.SignContract, current_user = Depends(get_current_user), db = Depends(get_db)):
    # build contract data
    try:
        cover_in_db = db.covers.find_one({"_id": query.cover_id})
    except Exception as exc:
        logger.error(f'failed to read db: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail='failed to read db') from exc
    
    if cover_in_db is None:
        raise HTTPException(status_code=404, detail="cover not found")

    if current_user["_id"]!= cover_in_db["buyer_id"]:
        raise HTTPException(status_code=401, detail="only buyer can engage signature process")

    buyer_in_db = await get_user_from_id(cover_in_db["buyer_id"], db)
    seller_in_db = await get_user_from_id(cover_in_db["seller_id"], db)

    try:
        returned_json = await utils.create_and_send_contract(
            config["contracts-templates-ids"][cover_in_db["cover_type"]],
            cover_in_db,
            buyer_in_db,
            seller_in_db,
            True,
            config['signature-request-links-expiration-delay-hours'],
            config['signature_request_delivery_method'],
            config['signed_document_delivery_method'],
            config['required_identification_methods'],
            config['secret-token']
        )
        assert returned_json is not None
    except Exception as exc:
        logger.error(f'failed to create and fill up contract: {traceback.format_exc()}')
        raise HTTPException(status_code=422, detail="failed to create and fill up contract") from exc

    await covers_router.step_forward_cover(covers_schemas.StepForwardCoverQuery(cover_id=str(query.cover_id)), current_user={"_id": current_user["_id"]}, db = db)

    try:
        db.covers.update_one(
            {"_id": query.cover_id},
            {
                "$set": {
                    "contract_id": returned_json["data"]["contract"]["id"],
                    "sign_page_urls": {
                        returned_json["data"]["contract"]["signers"][0]["email"]: returned_json["data"]["contract"]["signers"][0]["sign_page_url"],
                        returned_json["data"]["contract"]["signers"][1]["email"]: returned_json["data"]["contract"]["signers"][1]["sign_page_url"]
                    }
                }
            }
        )

        return {"message": "created and sent contract successfully"}
    except Exception as exc:
        logger.error(f'failed to read db: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail="failed to write db") from exc

@router.get('/sign-page-url')
async def get_sign_page_url(cover_id: str, current_user = Depends(get_current_user), db = Depends(get_db)):
    try:
        cover_id = ObjectId(cover_id)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="unprocessable cover_id") from exc

    try:
        cover_in_db = db.covers.find_one({"_id": cover_id})
    except Exception as exc:
        logger.error(f'failed to read db: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail="failed to read db") from exc
    
    if cover_in_db is None:
        raise HTTPException(status_code=404, detail="cover not found")
    
    if current_user['_id'] == cover_in_db["seller_id"]:
        pov = "seller"
    elif current_user['_id'] == cover_in_db["buyer_id"]:
        pov = "buyer"
    else:
        raise HTTPException(status_code=401, detail="only seller and buyer can get sign page url")

    if (pov == "buyer" and cover_in_db["status"] != "signingstarted") or (pov == "seller" and cover_in_db["status"] != "buyersigned"):
        raise HTTPException(status_code=403, detail="can not sign now")

    # get user email
    user_in_db = await get_user_from_id(cover_in_db[pov + "_id"], db)
    user_email = user_in_db["email"]

    return schemas.GetSignPageUrl(url=cover_in_db["sign_page_urls"][user_email])