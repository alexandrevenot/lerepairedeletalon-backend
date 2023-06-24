import traceback
from typing import Annotated
from datetime import datetime

from pymongo import MongoClient
from fastapi import APIRouter, Depends, HTTPException

import src.api.covers.utils as utils
import src.api.covers.schemas as schemas
import src.api.auth.router as auth_router

# global config
global_config = utils.load_global_config()

# config
config = utils.load_config()

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
    try:
        cover_in_db = covers_c.find_one({
            "stallion_nsire": cover.stallion_nsire,
            "mare_nsire": cover.mare_nsire
        })
    except:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to read covers collection")
    
    if cover_in_db is not None:
        raise HTTPException(status_code=400, detail="a cover already exists with this couple of nsire")
    else:
        try:
            # building document
            new_document = cover.dict()

            new_document.update({
                "buyer_id": current_user["_id"],
                "date": datetime.now()
                })
            
            stallion_in_db = stallions_c.find_one({"n_sire": new_document["stallion_nsire"]}, {"name": 1})
            try:
                new_document.update({
                    "stallion_name": stallion_in_db["name"]
                })
            except:
                raise ValueError("The stallion does not exist in base")

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
        if (cover_in_db["status"] in ["requested", "bought"] and current_user["_id"] != cover_in_db["seller_id"]) \
            or (cover_in_db["status"] in ["accepted", "declared_done"] and current_user["_id"] != cover_in_db["buyer_id"]):
            raise HTTPException(status_code=403, detail="no permissions to step this cover forward")

        try:
            index = config["status"].index(cover_in_db["status"])
            new_value = config["status"][index + 1]
            update = {'$set': {'status': new_value}}
            if new_value == "accepted": # remove message to sender from db when cover is accepted
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
                "status": document["status"]
            })
        
        return schemas.GetCoverGroupRM(items=cover_items)
    except:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to read covers collection")