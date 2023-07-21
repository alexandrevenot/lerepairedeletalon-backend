import traceback
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
                "n_sire": cover.stallion_nsire
            },{
                "prices": 1,
                "name": 1
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
        "timestamps": timestamps,
        "subtotal": subtotal,
        "buyer_fees": pricing_config["buyer_fees"],
        "seller_fees": pricing_config["seller_fees"],
        "TVA_coeff_HT": pricing_config["TVA_coeff_HT"]
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
    else:
        if (cover_in_db["status"] in ["offered", "downpaid"] and current_user["_id"] != cover_in_db["seller_id"]) \
            or (cover_in_db["status"] in ["approved"] and current_user["_id"] != cover_in_db["buyer_id"]):
            raise HTTPException(status_code=403, detail="no permissions to step this cover forward")

        try:
            index = config["status"].index(cover_in_db["status"])
            new_value = config["status"][index + 1]
            update = {'$set': {'status': new_value}}
            if new_value == "approved": # remove message to sender from db when cover is approved
                update['$unset'] = {'message': 1}
            covers_c.update_one({"_id": query.cover_id}, update)
        except:
            raise HTTPException(status_code=422, detail="unable to step cover forward")
        
        return {"message": "successfully step-forwarded cover"}

@router.get('/get-cover-group', response_model=schemas.GetCoverGroupRM)
async def get_cover(group: str, point_of_view: str, current_user = Depends(auth_router.get_current_user)):
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
            cover_items.append({
                "id": str(document["_id"]),
                "stallion_name": document["stallion_name"],
                "mare_name": document["mare_name"],
                "status": document["status"],
                "income": pricing_utils.calculate_income(document["subtotal"], document["seller_fees"]).income
            })
        
        return schemas.GetCoverGroupRM(items=cover_items)
    except:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to read covers collection")