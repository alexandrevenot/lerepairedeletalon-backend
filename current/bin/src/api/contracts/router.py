import traceback
from bson.objectid import ObjectId

from pymongo import MongoClient
from fastapi import APIRouter, Depends, HTTPException

import src.api.contracts.utils as utils
import src.api.contracts.schemas as schemas
import src.api.auth.router as auth_router
import src.api.covers.router as covers_router
import src.api.covers.schemas as covers_schemas

# global config
global_config = utils.load_global_config()

# config
config = utils.load_config()

# db
mongo_url = "mongodb://localhost:27017/"
client = MongoClient(mongo_url)
db = getattr(client, global_config['db_to_use'])
covers_c = db.covers

# routes
router = APIRouter(prefix='/contracts')

@router.put('/sign-contract')
async def sign_contract(query: schemas.SignContract, current_user = Depends(auth_router.get_current_user)):
    # build contract data
    try:
        cover = covers_c.find_one({"_id": query.cover_id})
    except:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to read covers collection")
    
    if cover is None:
        raise HTTPException(status_code=404, detail="no cover exists with this id")

    if current_user["_id"]!= cover["buyer_id"]:
        raise HTTPException(status_code=401, detail="only buyer can ask for signature")

    buyer_info = await auth_router.get_user_info(cover["buyer_id"])
    seller_info = await auth_router.get_user_info(cover["seller_id"])

    try:
        returned_json = await utils.create_and_send_contract(
            config["contracts-templates-ids"][cover["cover_type"]],
            cover,
            buyer_info,
            seller_info,
            True,
            config['signature-request-links-expiration-delay-hours'],
            config['signature_request_delivery_method'],
            config['signed_document_delivery_method'],
            config['required_identification_methods'],
            config['secret-token']
        )
        assert returned_json is not None
    except:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="unable to fill up contract template and engage signature")

    try:
        await covers_router.step_forward_cover(covers_schemas.StepForwardCoverQuery(cover_id=str(query.cover_id)), current_user={"_id": current_user["_id"]})
        covers_c.update_one(
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
    except:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to write covers collection")

@router.get('/sign-page-url')
async def get_sign_page_url(cover_id: str, current_user = Depends(auth_router.get_current_user)):
    try:
        objectified_id = ObjectId(cover_id)
    except:
        raise HTTPException(status_code=422, detail="Unprocessable id.")

    cover = covers_c.find_one(
        {"_id": objectified_id}
    )

    if not cover:
        raise HTTPException(status_code=404, detail="Cover not found.")
    
    if current_user['_id'] == cover["seller_id"]:
        pov = "seller"
    elif current_user['_id'] == cover["buyer_id"]:
        pov = "buyer"
    else:
        raise HTTPException(status_code=401, detail="Only seller and buyer can get sign page url.")

    if (pov == "buyer" and cover["status"] != "signingstarted") or (pov == "seller" and cover["status"] != "buyersigned"):
        raise HTTPException(status_code=403, detail="cannot sign now")

    # get user email
    user_info = await auth_router.get_user_info(cover[pov + "_id"])
    user_email = user_info["email"]

    return schemas.GetSignPageUrl(url=cover["sign_page_urls"][user_email])