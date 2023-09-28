import logging
import logging.handlers
import traceback
from bson.objectid import ObjectId
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

import src.api.covers.utils as utils
import src.api.covers.schemas as schemas
import src.api.pricing.utils as pricing_utils
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
    seller_id = ObjectId(cover.seller_id)
    if seller_id == current_user["_id"]:
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
                "owner": seller_id
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
    ## calculating price
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

    if cover.cover_type in stallions_config["cover_types_for_which_cover_place_has_to_be_provided"]:
        if cover.provided_cover_place == "":
            raise HTTPException(status_code=422, detail="a cover place has to be provided")
        else:
            cover_place = cover.provided_cover_place
    else:
        if cover.provided_cover_place != "":
            raise HTTPException(status_code=422, detail="cover place imposed on this cover")

    ## insert cover query information
    new_document = cover.model_dump(exclude="seller_id")
    new_document["seller_id"] = seller_id

    timestamps = {}
    for step in config["status"]:
        if step == config["status"][0]:
            timestamps[step] = datetime.now()
        else:
            timestamps[step] = None

    cover_payment_details = pricing_utils.get_cover_payment_details(
        subtotal,
        pricing_config["buyer_fees_coeff"],
        pricing_config["buyer_fees_offset"],
        pricing_config["seller_fees_coeff"],
        pricing_config["seller_fees_offset"],
        advance_percentage
    )

    ## insert payment details
    new_document.update(cover_payment_details.model_dump())

    ## insert information left
    new_document.update({
        "status": config["status"][0],
        "buyer_id": current_user["_id"],
        "stallion_name": stallion_in_db["name"],
        "stallion_breed": stallion_in_db["breed"],
        "stallion_production_breeds": stallion_in_db["production_breeds"],
        "balance_payment_condition": balance_payment_condition,
        "left_straws_owner": left_straws_owner,
        "timestamps": timestamps,
        "cover_place": cover_place,
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

async def step_forward_cover(cover_id: ObjectId, db = Depends(get_db)):
    try:
        cover_in_db = db.covers.find_one({"_id": cover_id})
    except Exception as exc:
        logger.error(f'failed to read db: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail="failed to read db") from exc

    try:
        index = config["status"].index(cover_in_db["status"])
        new_value = config["status"][index + 1]
        update = {
            '$set': {
                'status': new_value,
                'timestamps' + '.' + new_value: datetime.now()
                }
            }
        db.covers.update_one({"_id": cover_id}, update)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="cover is over") from exc
    
    return {"message": "successfully step-forwarded cover"}

@router.post('/approve-requested-cover')
async def approve_requested_cover(query: schemas.ApproveRequestedCoverQuery, current_user = Depends(get_current_user), db = Depends(get_db)):
    cover_id = ObjectId(query.cover_id)
    try:
        cover_in_db = db.covers.find_one({"_id": cover_id})
    except Exception as exc:
        logger.error(f'failed to read db: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail="failed to read db") from exc
    
    if cover_in_db is None:
        raise HTTPException(status_code=404, detail="cover not found")

    if not (cover_in_db["status"] == "requested" and current_user["_id"] == cover_in_db["seller_id"]):
        raise HTTPException(status_code=403, detail="no permissions to step this cover forward")
    
    await step_forward_cover(cover_id, db)

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
        cursor = db.covers.find(pattern).sort([(f"timestamps.{status}", -1) for status in reversed(config["status"])])
    except Exception as exc:
        logger.error(f'failed to read db: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail="failed to read db") from exc

    cover_items = []
    for document in cursor:
        if point_of_view == "seller":
            price = pricing_utils.calculate_income(
                document["advance_subtotal"] + document["balance_subtotal"],
                document["advance_seller_fees_ht"] + document["balance_seller_fees_ht"],
                pricing_config["TVA_coeff_HT"]
                ).total
        else:
            price = pricing_utils.calculate_checkout(
                document["advance_subtotal"] + document["balance_subtotal"],
                document["advance_buyer_fees_ht"] + document["balance_buyer_fees_ht"],
                pricing_config["TVA_coeff_HT"]
                ).total

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
    if pov == "buyer" and cover_in_db["status"] == config["status"][0]:
        contact_phone_number = ""
        contact_email = ""
    else:
        contact_phone_number = contact_in_db["phone_number"]
        contact_email = contact_in_db["email"]

    # price
    if pov == "seller":
        price = pricing_utils.calculate_income(
            cover_in_db["advance_subtotal"] + cover_in_db["balance_subtotal"],
            cover_in_db["advance_seller_fees_ht"] + cover_in_db["balance_seller_fees_ht"],
            pricing_config["TVA_coeff_HT"]
            ).total
    else:
        price = pricing_utils.calculate_checkout(
            cover_in_db["advance_subtotal"] + cover_in_db["balance_subtotal"],
            cover_in_db["advance_buyer_fees_ht"] + cover_in_db["balance_buyer_fees_ht"],
            pricing_config["TVA_coeff_HT"]
            ).total

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
    cover_id = ObjectId(query.cover_id)
    try:
        cover_in_db = db.covers.find_one({"_id": cover_id})
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
            {"_id": cover_id},
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

@router.post("/step-forward-payment")
async def step_forward_payment(query: schemas.StepForwardPaymentQuery, db = Depends(get_db)):
    await step_forward_cover(ObjectId(query.cover_id), db)
    
    return {"message": "successfully step-forwarded payment"}