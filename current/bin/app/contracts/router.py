import aiohttp
import base64
import logging
import logging.handlers
import traceback

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Header
from pymongo.errors import PyMongoError

import app.contracts.utils as utils
import app.contracts.schemas as schemas
import app.covers.router as covers_router

from app.dependencies import get_db, get_user_from_object_id, CurrentUserGetter, get_db_client

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

# dependencies
get_current_user = CurrentUserGetter(logger)

# routes
router = APIRouter(prefix='/contracts')

async def engage_signature_process(cover_in_db: dict, db = Depends(get_db), db_client = Depends(get_db_client)):
    buyer_in_db = await get_user_from_object_id(cover_in_db["buyer_id"], db, logger)
    seller_in_db = await get_user_from_object_id(cover_in_db["seller_id"], db, logger)

    try:
        returned_json, _ = await utils.create_and_send_contract(
            config["contracts-templates-ids"][cover_in_db["cover_type"]],
            cover_in_db,
            buyer_in_db,
            seller_in_db,
            global_config["send_demo_contracts"],
            config['signature-request-links-expiration-delay-hours'],
            config['signature_request_delivery_method'],
            config['signed_document_delivery_method'],
            config['required_identification_methods'],
            global_config["frontend_url"],
            config['esignatures_contracts_api_url'],
            config['secret-token']
        )
        assert returned_json is not None
    except KeyError as exc:
        raise HTTPException(status_code=409, detail="db content does not allow content creation") from exc
    except aiohttp.ClientError as exc:
        logger.error("aiohttp ClientError when trying to create esignatures contract: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="esignatures.io communication failure") from exc
    except Exception as exc:
        logger.error("failed to create and fill up contract: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to create and fill up contract") from exc

    with db_client.start_session() as session:
        with session.start_transaction():
            await covers_router.step_forward_cover(cover_in_db, "signingstarted", db)

            try:
                assert returned_json["data"]["contract"]["signers"][0]["email"] == buyer_in_db["email"]
                assert returned_json["data"]["contract"]["signers"][1]["email"] == seller_in_db["email"]
                db.covers.update_one(
                    {"_id": cover_in_db["_id"]},
                    {
                        "$set": {
                            "contract_id": returned_json["data"]["contract"]["id"],
                            "sign_page_urls": {
                                str(buyer_in_db["_id"]): returned_json["data"]["contract"]["signers"][0]["sign_page_url"],
                                str(seller_in_db["_id"]): returned_json["data"]["contract"]["signers"][1]["sign_page_url"]
                            }
                        }
                    }
                )
            except AssertionError as exc:
                logger.error("error in signers order or emails: %s", traceback.format_exc())
                raise HTTPException(status_code=500, detail="failed to create and fill up contract") from exc
            except PyMongoError as exc:
                logger.error("failed to write db: %s", traceback.format_exc())
                raise HTTPException(status_code=500, detail="failed to write db") from exc

    return returned_json["data"]["contract"]["signers"][0]["sign_page_url"]

@router.get('/sign-page-url/{cover_id}')
async def get_sign_page_url(
    cover_in_db = Depends(covers_router.get_cover_in_db),
    current_user = Depends(get_current_user),
    db = Depends(get_db),
    db_client = Depends(get_db_client)
    ):
    if current_user['_id'] == cover_in_db["seller_id"]:
        pov = "seller"
    elif current_user['_id'] == cover_in_db["buyer_id"]:
        pov = "buyer"
    else:
        raise HTTPException(status_code=403, detail="only seller and buyer can get sign page url")

    if (pov == "buyer" and cover_in_db["status"] not in ["approved", "signingstarted"]) \
    or (pov == "seller" and cover_in_db["status"] != "buyersigned"):
        raise HTTPException(status_code=403, detail="can not sign now")

    if cover_in_db["status"] == "approved":
        url = await engage_signature_process(cover_in_db, db, db_client)
    else:
        url = cover_in_db["sign_page_urls"][str(current_user["_id"])]

    return schemas.GetSignPageUrl(url=url)

@router.post('/esignatures-webhook')
async def manage_esignatures_wehbooks(query: schemas.ContractWebhookBody, authorization: Annotated[str | None, Header()] = None, db = Depends(get_db)):
    try:
        assert authorization.split(" ")[1].encode('utf-8') == base64.b64encode((config["secret-token"] + ":").encode('utf-8'))
    except AssertionError as exc:
        raise HTTPException(status_code=401) from exc

    if query.status != "signer-signed":
        return {"message": "successfully received webhook"}

    try:
        contract_id = query.data["contract"]["id"]
        signing_order = query.data["signer"]["signing_order"]
    except KeyError as exc:
        logger.error("error when parsing webhook data: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail='error when parsing webhook data') from exc

    try:
        cover_in_db = db.covers.find_one({"contract_id": contract_id})
    except PyMongoError as exc:
        logger.error("failed to read db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to read db") from exc

    if cover_in_db is None:
        logger.error("received webhook with signer-signed status but no cover found associated to contract_id %s", contract_id)
        raise HTTPException(status_code=500, detail="cover not found")

    if cover_in_db["status"] == "signingstarted" and signing_order == "1":
        await covers_router.step_forward_cover(cover_in_db, "buyersigned", db)
    elif cover_in_db["status"] == "buyersigned" and signing_order == "2":
        await covers_router.step_forward_cover(cover_in_db, "sellersigned", db)

    return {"message": "successfully received webhook"}
