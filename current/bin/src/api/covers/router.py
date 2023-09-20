import logging
import logging.handlers
import traceback
import base64
from bson.objectid import ObjectId
from typing import Annotated
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Header

import src.api.covers.utils as utils
import src.api.covers.schemas as schemas
import src.api.pricing.utils as pricing_utils
import src.api.pricing.schemas as pricing_schemas
import src.api.contracts.utils as contracts_utils
import src.api.stallions.utils as stallions_utils

from src.api.auth.router import get_current_user, get_user_from_id
from src.database.db import get_db

# configs
global_config = utils.load_global_config()
config = utils.load_config()
pricing_config = pricing_utils.load_config()
contracts_config = contracts_utils.load_config()
stallions_config = stallions_utils.load_config()

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
router = APIRouter(prefix='/covers')

@router.post('/create-cover')
async def create_cover(cover: schemas.CoverQuery, current_user = Depends(get_current_user), db = Depends(get_db)):
    # user cant buy a cover to himself
    if cover.seller_id == current_user["_id"]:
        raise HTTPException(status_code=400, detail="seller_id is equal to buyer_id")

    # check that all existing covers with this stallion/mare couple are over
    try:
        cover_in_db_cursor = db.covers.find({
            "stallion_nsire": cover.stallion_nsire,
            "mare_nsire": cover.mare_nsire
        },
        {
            "status": 1
        })
    except Exception as exc:
        logger.error(f'failed to read db: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail="failed to read db") from exc
    
    for cover_in_db in cover_in_db_cursor:
        if cover_in_db["status"] != config["status"][-1]:
            raise HTTPException(status_code=400, detail="cover already exists")
    
    # fetching price
    try:
        stallion_in_db = db.stallions.find_one(
            {
                "n_sire": cover.stallion_nsire,
                "owner": cover.seller_id
            },{
                "prices": 1,
                "name": 1,
                "breed": 1,
                "production_breeds": 1
            })
    except Exception as exc:
        logger.error(f'failed to read db: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail="failed to read db") from exc
    
    if stallion_in_db is None:
        raise HTTPException(status_code=404, detail="stallion not found")

    # building document
    ## calculting price
    subtotal = None
    for line in stallion_in_db["prices"]:
        if line["cover_type"] == cover.cover_type:
            subtotal = line["price"]
            cover_place = line["cover_place"]
            advance_percentage = line["advance_percentage"]
            balance_payment_condition = line["balance_payment_condition"]
            left_straws_owner = line["left_straws_owner"]
    
    if subtotal is None:
        raise HTTPException(status_code=404, detail="cover type does not exist on stallion")

    if cover.cover_type in stallions_config["cover_types_for_which_cover_place_has_to_be_offered"]:
        if cover.offered_cover_place == "":
            raise HTTPException(status_code=422, detail="a cover place has to be offered")
        else:
            cover_place = cover.offered_cover_place
    else:
        if cover.offered_cover_place != "":
            raise HTTPException(status_code=422, detail="cover place imposed on this cover")

    new_document = cover.dict()

    timestamps = {}
    for step in config["status"]:
        if step == config["status"][0]:
            timestamps[step] = datetime.now()
        else:
            timestamps[step] = None

    ## adding buyer_id, timestamps and price
    new_document.update({
        "status": "offered",
        "buyer_id": current_user["_id"],
        "stallion_name": stallion_in_db["name"],
        "stallion_breed": stallion_in_db["breed"],
        "stallion_production_breeds": stallion_in_db["production_breeds"],
        "balance_payment_condition": balance_payment_condition,
        "left_straws_owner": left_straws_owner,
        "timestamps": timestamps,
        "cover_place": cover_place,
        "advance": pricing_utils.calculate_advance(subtotal, advance_percentage),
        "balance": pricing_utils.calculate_balance(subtotal, advance_percentage),
        "buyer_fees": pricing_config["buyer_fees"],
        "seller_fees": pricing_config["seller_fees"],
        "notes" : {
            "seller": "",
            "buyer": ""
        }
        })

    try:
        db.covers.insert_one(new_document)
        return {"message": "cover registered successfully"}
    except Exception as exc:
        logger.error(f'failed to write db: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail="failed to write db") from exc

@router.post('/step-forward-cover') # manually only, does not apply to signing or paying
async def step_forward_cover(query: schemas.StepForwardCoverQuery, current_user = Depends(get_current_user), db = Depends(get_db)):
    try:
        cover_in_db = db.covers.find_one({"_id": query.cover_id})
    except Exception as exc:
        logger.error(f'failed to read db: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail="failed to read db") from exc
    
    if cover_in_db is None:
        raise HTTPException(status_code=404, detail="no cover exists with this id")

    if not ((cover_in_db["status"] == "offered" and current_user["_id"] == cover_in_db["seller_id"]) \
            or (cover_in_db["status"] == "approved" and current_user["_id"] == cover_in_db["buyer_id"])):
        raise HTTPException(status_code=403, detail="no permissions to step this cover forward")

    try:
        index = config["status"].index(cover_in_db["status"])
        new_value = config["status"][index + 1]
        update = {
            '$set': {
                'status': new_value,
                'timestamps' + '.' + new_value: datetime.now()
                }
            }
        db.covers.update_one({"_id": query.cover_id}, update)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="cover is over") from exc
    
    return {"message": "successfully step-forwarded cover"}

@router.get('/cover-group', response_model=schemas.GetCoverGroupRM)
async def get_cover_group(group: str, point_of_view: str, current_user = Depends(get_current_user), db = Depends(get_db)):
    # data validation
    if group not in config["groups"].keys():
        raise HTTPException(status_code=422, detail="invalid group")
    
    if point_of_view not in ["seller", "buyer"]:
        raise HTTPException(status_code=422, detail="invalid point of view")
    
    # db querying
    status_l = config["groups"][group]
    pattern = {
        'status': {'$in': status_l},
        point_of_view + '_id': current_user["_id"]
    }
    
    try:
        cursor = db.covers.find(pattern).sort('date', -1)
    except Exception as exc:
        logger.error(f'failed to read db: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail="failed to read db") from exc

    cover_items = []
    for document in cursor:
        if point_of_view == "seller":
            price = pricing_utils.calculate_income(document["advance"] + document["balance"], document["seller_fees"], pricing_config["TVA_coeff_HT"]).total
        else:
            price = pricing_utils.calculate_checkout(document["advance"] + document["balance"], document["buyer_fees"], pricing_config["TVA_coeff_HT"]).total

        cover_items.append({
            "id": str(document["_id"]),
            "stallion_name": document["stallion_name"],
            "mare_name": document["mare_name"],
            "status": document["status"],
            "price": price
        })
    
    return schemas.GetCoverGroupRM(items=cover_items)

@router.get('/cover-information', response_model=schemas.GetCoverInformation)
async def get_cover_information(cover_id: str, current_user = Depends(get_current_user), db = Depends(get_db)):
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
        raise HTTPException(status_code=401, detail="only seller and buyer can get cover information")
    
    contact_in_db = await get_user_from_id(cover_in_db[("seller" if pov == "buyer" else "buyer") + "_id"], db)

    contact_name = contact_in_db["firstname"] + " " + contact_in_db["lastname"]
    if pov == "buyer" and cover_in_db["status"] == "offered":
        contact_phone_number = ""
        contact_email = ""
    else:
        contact_phone_number = contact_in_db["phone_number"]
        contact_email = contact_in_db["email"]

    # price
    if pov == "seller":
        price = pricing_utils.calculate_income(cover_in_db["advance"] + cover_in_db["balance"], cover_in_db["seller_fees"], pricing_config["TVA_coeff_HT"]).total
    else:
        price = pricing_utils.calculate_checkout(cover_in_db["advance"] + cover_in_db["balance"], cover_in_db["buyer_fees"], pricing_config["TVA_coeff_HT"]).total

    # timestamps
    timestamps_src = cover_in_db["timestamps"]
    timestamps = {}

    for key, value in timestamps_src.items():
        if value is None:
            timestamps[key] = "-"
        else:
            timestamps[key] = value.strftime("Le %d/%m/%Y à %H:%M:%S")

    return schemas.GetCoverInformation(
        stallion_name=cover_in_db["stallion_name"],
        stallion_breed=cover_in_db["stallion_breed"],
        stallion_nsire=cover_in_db["stallion_nsire"],
        stallion_production_breeds=cover_in_db["stallion_production_breeds"],
        mare_name=cover_in_db["mare_name"],
        mare_breed=cover_in_db["mare_breed"],
        mare_nsire=cover_in_db["mare_nsire"],
        cover_type=cover_in_db["cover_type"],
        cover_place=cover_in_db["cover_place"],
        status=cover_in_db["status"],
        price=price,
        buyer_message=cover_in_db["message"],
        timestamps=timestamps,
        notes=cover_in_db["notes"][pov],
        contact_name=contact_name,
        contact_phone_number=contact_phone_number,
        contact_email=contact_email,
        pov=pov
    )

@router.put('/update-notes')
async def update_notes(query: schemas.UpdateNotesQuery, current_user = Depends(get_current_user), db = Depends(get_db)):
    try:
        cover_in_db = db.covers.find_one({"_id": query.cover_id})
    except Exception as exc:
        logger.error(f'failed to read db: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail="failed to read db") from exc

    if not cover_in_db:
        raise HTTPException(status_code=404, detail="cover not found.")
    
    if current_user['_id'] == cover_in_db["seller_id"]:
        pov = "seller"
    elif current_user['_id'] == cover_in_db["buyer_id"]:
        pov = "buyer"
    else:
        raise HTTPException(status_code=401, detail="only seller and buyer can edit notes")
    
    try:
        db.covers.update_one(
            {"_id": query.cover_id},
            {
                "$set": {
                    f"notes.{pov}": query.notes
                }
            }
        )

        return {"message": "updated notes successfully"}
    except Exception as exc:
        logger.error(f'failed to write db: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail="failed to write db") from exc

@router.post("/step-forward-signature")
async def step_forward_signature(query: schemas.StepForwardSignatureQuery, authorization: Annotated[str | None, Header()] = None, db = Depends(get_db)):
    try:
        assert authorization.split(" ")[1].encode('utf-8') == base64.b64encode((contracts_config["secret-token"] + ":").encode('utf-8'))
    except Exception as exc:
        raise HTTPException(status_code=401) from exc
    
    try:
        cover_in_db = db.covers.find_one({"contract_id": query.contract_id})
    except Exception as exc:
        logger.error(f'failed to read db: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail="failed to read db") from exc
    
    if cover_in_db is None:
        raise HTTPException(status_code=404, detail="no cover exists with this contract id")
    
    if cover_in_db["status"] not in ["signingstarted", "buyersigned"]:
        raise HTTPException(status_code=403, detail="no permissions to step this cover forward")

    index = config["status"].index(cover_in_db["status"])
    new_value = config["status"][index + 1]
    update = {
        '$set': {
            'status': new_value,
            'timestamps' + '.' + new_value: datetime.now()
            }
        }
    
    try:
        db.covers.update_one({"contract_id": query.contract_id}, update)
    except Exception as exc:
        logger.error(f'failed to write db: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail="failed to write db") from exc
    
    return {"message": "successfully step-forwarded signature"}

@router.get('/checkout', response_model=pricing_schemas.Checkout)
async def get_checkout(cover_id: str, current_user = Depends(get_current_user), db = Depends(get_db)):
    try:
        cover_id = ObjectId(cover_id)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="unprocessable cover_id") from exc

    try:
        cover_in_db = db.covers.find_one({"_id": cover_id})
    except Exception as exc:
        logger.error(f'failed to read db: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail="failed to read db") from exc

    if not cover_in_db:
        raise HTTPException(status_code=404, detail="cover not found")
    
    if current_user["_id"] != cover_in_db["buyer_id"]:
        raise HTTPException(status_code=403, detail="only buyer can get checkout")
    
    if cover_in_db["status"] == "sellersigned":
        checkout = pricing_utils.calculate_checkout(cover_in_db["advance"], cover_in_db["buyer_fees"], pricing_config["TVA_coeff_HT"])
    elif cover_in_db["status"] == "downpaid":
        checkout = pricing_utils.calculate_checkout(cover_in_db["balance"], cover_in_db["buyer_fees"], pricing_config["TVA_coeff_HT"])
    else:
        raise HTTPException(status_code=403, detail="status does not allow payment")

    return pricing_schemas.Checkout(
        subtotal=checkout.subtotal,
        service_fees=checkout.service_fees,
        total=checkout.total,
        status=cover_in_db["status"]
    )

@router.post("/step-forward-payment")
async def step_forward_payment(query: schemas.StepForwardPaymentQuery, current_user = Depends(get_current_user), db = Depends(get_db)):
    # no security yet: the current user can just use postman and step forward the status without actually paying
    try:
        cover_in_db = db.covers.find_one({"_id": query.cover_id})
    except Exception as exc:
        logger.error(f'failed to read db: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail="failed to read db") from exc

    if not cover_in_db:
        raise HTTPException(status_code=404, detail="cover not found")

    if cover_in_db["status"] not in ["sellersigned", "downpaid"]:
        raise HTTPException(status_code=403, detail="no permissions to step this cover forward")

    index = config["status"].index(cover_in_db["status"])
    new_value = config["status"][index + 1]
    update = {
        '$set': {
            'status': new_value,
            'timestamps' + '.' + new_value: datetime.now()
            }
        }
    
    try:
        db.covers.update_one({"_id": query.cover_id}, update)
    except Exception as exc:
        logger.error(f'failed to write db: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail="failed to write db") from exc
    
    return {"message": "successfully step-forwarded payment"}