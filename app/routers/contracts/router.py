import aiohttp
import logging
import logging.handlers
import traceback

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pymongo.errors import PyMongoError

from . import utils
from . import schemas
from ..covers import utils as covers_utils
from ..users import utils as users_utils
from ...monitoring import tools as monitoring_tools

from ...dependencies import get_db, get_user_from_object_id, CurrentUserGetter, \
    get_db_client, get_current_user_id, CoverInDBGetter, get_stallion_owner_from_object_id

# configs
global_config = utils.load_global_config()
config = utils.load_config()
monitoring_config = monitoring_tools.load_config()

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
get_cover_in_db = CoverInDBGetter(logger)

# routes
router = APIRouter(prefix='/contracts')

async def engage_signature_process(cover_in_db: dict, db = Depends(get_db), db_client = Depends(get_db_client)):
    buyer_in_db = await get_user_from_object_id(cover_in_db["buyer_id"], db, logger)
    seller_in_db = await get_user_from_object_id(cover_in_db["seller_id"], db, logger)

    # check if buyer has legal identity >= lvl 1
    try:
        buyer_legal_identity_level = buyer_in_db["legal_identity"]["level"]
    except KeyError:
        buyer_legal_identity_level = 0

    if buyer_legal_identity_level < 1:
        raise HTTPException(status_code=409, detail="insufficient legal identity level for buyer")

    # check if seller has legal identity >= lvl 3
    try:
        seller_legal_identity_level = seller_in_db["legal_identity"]["level"]
    except KeyError:
        seller_legal_identity_level = 0

    if seller_legal_identity_level < 3:
        raise HTTPException(status_code=409, detail="insufficient legal identity level for seller")

    if cover_in_db["seller_id"] == cover_in_db["stallion_owner_id"]:
        stallion_owner_in_db = None
    else:
        stallion_owner_in_db = await get_stallion_owner_from_object_id(cover_in_db["stallion_owner_id"], db, logger)

    try:
        returned_json, _ = await utils.create_and_send_contract(
            config["contracts_templates_ids"][cover_in_db["cover_type"]],
            cover_in_db,
            buyer_in_db,
            seller_in_db,
            stallion_owner_in_db,
            global_config["send_demo_contracts"],
            config['signature_request_links_expiration_delay_hours'],
            config['signature_request_delivery_methods'],
            config['signed_document_delivery_method'],
            config['multi_factor_authentications'],
            global_config["frontend_url"],
            config['esignatures_contracts_api_url'],
            config['secret_token']
        )
        assert returned_json is not None
    except KeyError as exc:
        logger.error("db content does not allow content creation: %s", traceback.format_exc())
        raise HTTPException(status_code=409, detail="db content does not allow content creation") from exc
    except aiohttp.ClientError as exc:
        logger.error("aiohttp ClientError when trying to create esignatures contract: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="esignatures.io communication failure") from exc
    except Exception as exc:
        logger.error("failed to create and fill up contract: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to create and fill up contract") from exc

    with db_client.start_session() as session:
        session.start_transaction()
        try:
            await covers_utils.step_forward_cover(cover_in_db, "signingstarted", db, logger, session)
            assert returned_json["data"]["contract"]["signers"][0]["email"] == buyer_in_db["email"]
            assert returned_json["data"]["contract"]["signers"][1]["email"] == seller_in_db["email"]
            db.covers.update_one(
                {"_id": cover_in_db["_id"]},
                {
                    "$set": {
                        "contract_id": returned_json["data"]["contract"]["id"],
                        "sign_page_urls": {
                            str(buyer_in_db["_id"]): f'{returned_json["data"]["contract"]["signers"][0]["sign_page_url"]}',
                            str(seller_in_db["_id"]): f'{returned_json["data"]["contract"]["signers"][1]["sign_page_url"]}'
                        }
                    }
                },
                session=session
            )
            message = f"Une saillie vient de changer de statut\n*ID*: {cover_in_db['_id']}"
            message += "\n*Nouveau statut*: signingstarted"
            message += f"\n*Utilisateur source*: {buyer_in_db['firstname']} {buyer_in_db['lastname']}"
            await monitoring_tools.send_telegram_message(message, monitoring_config["telegram_api_key"], logger)
            session.commit_transaction()
        except AssertionError as exc:
            session.abort_transaction()
            logger.error("error in signers order or emails: %s", traceback.format_exc())
            raise HTTPException(status_code=500, detail="failed to create and fill up contract") from exc
        except PyMongoError as exc:
            session.abort_transaction()
            logger.error("failed to write db: %s", traceback.format_exc())
            raise HTTPException(status_code=500, detail="failed to write db") from exc

    return returned_json["data"]["contract"]["signers"][0]["sign_page_url"]

@router.get('/sign-page-url/{cover_id}')
async def get_sign_page_url(
    cover_in_db = Depends(get_cover_in_db),
    user_id = Depends(get_current_user_id),
    db = Depends(get_db),
    db_client = Depends(get_db_client)
    ):
    if user_id == cover_in_db["seller_id"]:
        pov = "seller"
    elif user_id == cover_in_db["buyer_id"]:
        pov = "buyer"
    else:
        raise HTTPException(status_code=403, detail="only seller and buyer can get sign page url")

    if (pov == "buyer" and cover_in_db["status"] not in ["approved", "signingstarted"]) \
    or (pov == "seller" and cover_in_db["status"] != "buyersigned"):
        raise HTTPException(status_code=403, detail="cannot sign now")

    if cover_in_db["status"] == "approved":
        url = await engage_signature_process(cover_in_db, db, db_client)
    else:
        url = cover_in_db["sign_page_urls"][str(user_id)]

    return schemas.GetSignPageUrl(url=url)

@router.post('/esignatures-webhook')
async def manage_esignatures_wehbooks(
    query: schemas.ContractWebhookBody,
    background_tasks: BackgroundTasks,
    db = Depends(get_db)
):
    if query.secret_token != config["secret_token"]:
        raise HTTPException(status_code=401)

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
        await covers_utils.step_forward_cover(cover_in_db, "buyersigned", db, logger)
        buyer_in_db = await get_user_from_object_id(cover_in_db["buyer_id"], db, logger)
        seller_in_db = await get_user_from_object_id(cover_in_db["seller_id"], db, logger)
        background_tasks.add_task(users_utils.notify_user, "buyersigned", cover_in_db["_id"], "seller", seller_in_db, buyer_in_db, db, logger)
        message = "Un contrat vient d'être signé par l'acheteur"
        message += f"\n*Saillie*: {cover_in_db['_id']}"
        message += f"\n*Acheteur*: {buyer_in_db['firstname']} {buyer_in_db['lastname']}"
        message += f"\n*Vendeur*: {seller_in_db['firstname']} {seller_in_db['lastname']}"
        background_tasks.add_task(
            monitoring_tools.send_telegram_message,
            message,
            monitoring_config["telegram_api_key"],
            logger
        )
    elif cover_in_db["status"] == "buyersigned" and signing_order == "2":
        await covers_utils.step_forward_cover(cover_in_db, "sellersigned", db, logger)
        buyer_in_db = await get_user_from_object_id(cover_in_db["buyer_id"], db, logger)
        seller_in_db = await get_user_from_object_id(cover_in_db["seller_id"], db, logger)
        background_tasks.add_task(users_utils.notify_user, "sellersigned", cover_in_db["_id"], "buyer", buyer_in_db, seller_in_db, db, logger)
        message = "Un contrat vient d'être signé par le vendeur"
        message += f"\n*Saillie*: {cover_in_db['_id']}"
        message += f"\n*Acheteur*: {buyer_in_db['firstname']} {buyer_in_db['lastname']}"
        message += f"\n*Vendeur*: {seller_in_db['firstname']} {seller_in_db['lastname']}"
        background_tasks.add_task(
            monitoring_tools.send_telegram_message,
            message,
            monitoring_config["telegram_api_key"],
            logger
        )
    return {"message": "successfully received webhook"}
