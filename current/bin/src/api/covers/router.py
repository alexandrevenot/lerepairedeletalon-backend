import traceback
from bson.objectid import ObjectId
from typing import Annotated
from datetime import datetime

from pymongo import MongoClient
from fastapi import APIRouter, Depends, HTTPException

import src.api.covers.utils as utils
import src.api.covers.schemas as schemas
import src.api.auth.router as auth_router
import src.api.pricing.utils as pricing_utils

# global config
global_config = utils.load_global_config()

# config
config = utils.load_config()
pricing_config = pricing_utils.load_config()

# db
mongo_url = "mongodb://localhost:27017/"
client = MongoClient(mongo_url)
db = getattr(client, global_config['db_to_use'])
covers_c = db.covers
stallions_c = db.stallions

# routes
router = APIRouter(prefix='/covers')

@router.post('/create-cover')
async def create_cover(cover: schemas.CoverQuery, current_user = Depends(auth_router.get_current_user)):
    if cover.seller_id == current_user["_id"]:
        raise HTTPException(status_code=400, detail="seller_id is equal to buyer_id")

    try:
        cover_in_db = covers_c.find_one({
            "stallion_nsire": cover.stallion_nsire,
            "mare_nsire": cover.mare_nsire
        },
        {
            "status": 1
        })
    except:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to read covers collection")
    
    if cover_in_db is not None and cover_in_db["status"] != config["status"][-1]:
        raise HTTPException(status_code=400, detail="cover already exists")
    
    ## fetching price
    try:
        stallion_in_db = stallions_c.find_one(
            {
                "n_sire": cover.stallion_nsire,
            },{
                "prices": 1,
                "name": 1,
                "breed": 1
            })
    except:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to read stallions collection")
    
    if stallion_in_db is None:
        print(traceback.format_exc())
        raise HTTPException(status_code=404, detail="stallion does not exist in base")

    # building document
    ## calculting price
    subtotal = None
    for line in stallion_in_db["prices"]:
        if line["cover_type"] == cover.cover_type:
            subtotal = line["price"]
    
    if subtotal is None:
        raise HTTPException(status_code=404, detail="cover type does not exist on stallion")

    new_document = cover.dict()

    timestamps = {}
    for step in config["status"]:
        if step == config["status"][0]:
            timestamps[step] = datetime.now()
        else:
            timestamps[step] = None

    ## adding buyer_id, timestamps and price
    new_document.update({
        "buyer_id": current_user["_id"],
        "stallion_name": stallion_in_db["name"],
        "stallion_breed": stallion_in_db["breed"],
        "timestamps": timestamps,
        "subtotal": subtotal,
        "buyer_fees": pricing_config["buyer_fees"],
        "seller_fees": pricing_config["seller_fees"],
        "notes" : {
            "seller": "",
            "buyer": ""
        }
        })

    try:
        covers_c.insert_one(new_document)
        return {"message": "cover registered successfully"}
    except:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to write covers collection")

@router.put('/step-forward-cover')
async def step_forward_cover(query: schemas.StepForwardCoverQuery, current_user = Depends(auth_router.get_current_user)):
    try:
        cover_in_db = covers_c.find_one({"_id": query.cover_id})
    except:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to read covers collection")
    
    if cover_in_db is None:
        raise HTTPException(status_code=404, detail="no cover exists with this id")

    if current_user["_id"] not in [cover_in_db["seller_id"], cover_in_db["buyer_id"]]:
        raise HTTPException(status_code=401, detail="only seller or buyer can step this cover forward")

    if (cover_in_db["status"] in ["offered", "downpaid", "buyersigned"] and current_user["_id"] != cover_in_db["seller_id"]) \
        or (cover_in_db["status"] in ["approved", "sellersigned"] and current_user["_id"] != cover_in_db["buyer_id"]):
        raise HTTPException(status_code=403, detail="no permissions to step this cover forward")

    try:
        if cover_in_db["status"] == "offered" and query.refuse:
            covers_c.delete_one({"_id": query.cover_id})
        else:
            index = config["status"].index(cover_in_db["status"])
            new_value = config["status"][index + 1]
            update = {
                '$set': {
                    'status': new_value,
                    'timestamps' + '.' + new_value: datetime.now()
                    }
                }
            covers_c.update_one({"_id": query.cover_id}, update)
    except:
        raise HTTPException(status_code=422, detail="unable to step cover forward")
    
    return {"message": "successfully step-forwarded cover"}

@router.get('/get-cover-group', response_model=schemas.GetCoverGroupRM)
async def get_cover_group(group: str, point_of_view: str, current_user = Depends(auth_router.get_current_user)):
    # data validation
    if group not in config["groups"].keys():
        raise HTTPException(status_code=422, detail=f"group has to be in {list(config['groups'].keys())}")
    
    if point_of_view not in ["seller", "buyer"]:
        raise HTTPException(status_code=422, detail=f"point_of_view has to be either 'seller' or 'buyer' ")
    
    # db querying
    status_l = config["groups"][group]
    pattern = {
        'status': {'$in': status_l},
        point_of_view + '_id': current_user["_id"]
    }

    try:
        cursor = covers_c.find(pattern).sort('date', -1)
        cover_items = []
        for document in cursor:
            if point_of_view == "seller":
                price = pricing_utils.calculate_income(document["subtotal"], document["seller_fees"], pricing_config["TVA_coeff_HT"]).total
            else:
                price = pricing_utils.calculate_checkout(document["subtotal"], document["buyer_fees"], pricing_config["TVA_coeff_HT"]).total

            cover_items.append({
                "id": str(document["_id"]),
                "stallion_name": document["stallion_name"],
                "mare_name": document["mare_name"],
                "status": document["status"],
                "price": price
            })
        
        return schemas.GetCoverGroupRM(items=cover_items)
    except:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to read covers collection")

@router.get('/get-cover-information', response_model=schemas.GetCoverInformation)
async def get_cover_information(id: str, current_user = Depends(auth_router.get_current_user)):
    try:
        objectified_id = ObjectId(id)
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
        raise HTTPException(status_code=401, detail="Only seller and buyer can get cover information.")
    
    # contact
    user_info = await auth_router.get_user_info(cover[("seller" if pov == "buyer" else "buyer") + "_id"])

    if pov == "buyer" and cover["status"] == "offered":
        contact_name = user_info["firstname"] + " " + user_info["lastname"]
        contact_phone_number = ""
        contact_email = ""
    else:
        contact_name = user_info["name"]
        contact_phone_number = user_info["phone_number"]
        contact_email = user_info["email"]

    # price
    if pov == "seller":
        price = pricing_utils.calculate_income(cover["subtotal"], cover["seller_fees"], pricing_config["TVA_coeff_HT"]).total
    else:
        price = pricing_utils.calculate_checkout(cover["subtotal"], cover["buyer_fees"], pricing_config["TVA_coeff_HT"]).total

    # timestamps
    timestamps_src = cover["timestamps"]
    timestamps = {}

    for key, value in timestamps_src.items():
        if value is None:
            timestamps[key] = "-"
        else:
            timestamps[key] = value.strftime("Le %d/%m/%Y à %H:%M:%S")


    return schemas.GetCoverInformation(
        stallion_name=cover["stallion_name"],
        stallion_breed=cover["stallion_breed"],
        stallion_nsire=cover["stallion_nsire"],
        mare_name=cover["mare_name"],
        mare_breed=cover["mare_breed"],
        mare_nsire=cover["mare_nsire"],
        cover_type=cover["cover_type"],
        status=cover["status"],
        price=price,
        buyer_message=cover["message"],
        timestamps=timestamps,
        notes=cover["notes"][pov],
        contact_name=contact_name,
        contact_phone_number=contact_phone_number,
        contact_email=contact_email,
        pov=pov
    )

@router.put('/update-notes')
async def update_notes(query: schemas.UpdateNotesQuery, current_user = Depends(auth_router.get_current_user)):
    try:
        cover = covers_c.find_one({"_id": query.cover_id})
    except:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to read covers collection")

    if not cover:
        raise HTTPException(status_code=404, detail="cover not found.")
    
    if current_user['_id'] == cover["seller_id"]:
        pov = "seller"
    elif current_user['_id'] == cover["buyer_id"]:
        pov = "buyer"
    else:
        raise HTTPException(status_code=401, detail="only seller and buyer can edit notes.")
    
    try:
        covers_c.update_one(
            {"_id": query.cover_id},
            {
                "$set": {
                    f"notes.{pov}": query.notes
                }
            }
        )

        return {"message": "updated notes successfully"}
    except:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to write covers collection")