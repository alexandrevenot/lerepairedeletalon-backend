import traceback
from bson.objectid import ObjectId
from typing import Annotated

from pymongo import MongoClient
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, Depends, Query
from fastapi.responses import Response

import src.api.stallions.utils as utils
import src.api.stallions.schemas as schemas
import src.api.auth.router as auth_router

# global config
global_config = utils.load_global_config()

# config
config = utils.load_config()

# db
mongo_url = "mongodb://localhost:27017/"
client = MongoClient(mongo_url)
db = getattr(client, global_config['db_to_use'])
stallions_c = db.stallions

# routes
router = APIRouter(prefix='/stallions')

@router.get('/search', response_model=schemas.SearchRM)
async def search(
    page: int,
    limit: int,
    min_price: int = None,
    max_price: int = None,
    breeds: Annotated[list[str] | None, Query()] = None,
    colors: Annotated[list[str] | None, Query()] = None
):
    if page <= 0:
        raise HTTPException(status_code=422, detail="page can't be <= 0")

    query = {}

    # price
    price_query = {}
    if min_price:
        price_query["$gte"] = min_price
    if max_price:
        price_query["$lte"] = max_price
    
    if price_query:
        query["price"] = price_query

    # breed
    if breeds:
        query["breed"] = {"$in": breeds}
    if colors:
        query["color"] = {"$in": colors}
    
    cursor = stallions_c.find(query, {"_id": 1, "name": 1, "location": 1, "price": 1}).skip((page - 1) * limit).limit(limit)

    mp_l = []
    for document in cursor:
        mp_l.append(schemas.MosaicProfileInfo(
            id=str(document["_id"]),
            name=document["name"],
            location=document["location"],
            price=document["price"]
        ))
    
    return schemas.SearchRM(content=mp_l)

@router.get('/get-profile-pic')
async def get_profile_pic(id: str, current_user = Depends(auth_router.get_current_user)):
    stallion = stallions_c.find_one({"_id": ObjectId(id)})

    if stallion:
        image_data = stallion["photos"][0]["data"]
        image_content_type = stallion["photos"][0]["content_type"]
        return Response(content=image_data, media_type=image_content_type)
    else:
        return HTTPException(status_code=404, detail="Image not found.")

@router.post('/register-new-stallion')
async def register_new_stallion(
    name: Annotated[str, Form()],
    breed: Annotated[str, Form()],
    n_sire: Annotated[str, Form()],
    c_saillies: Annotated[UploadFile, File()],
    photos: list[UploadFile],
    main_desc: Annotated[str, Form()],
    color: Annotated[str, Form()],
    birth_date: Annotated[str, Form()],
    height: Annotated[str, Form()],
    offspring: Annotated[str, Form()],
    performance: Annotated[str, Form()],
    pedigree: Annotated[list[str], Form()],
    pedigree_po: Annotated[str, Form()],
    comments: Annotated[str, Form()],
    r_types: Annotated[list[str], Form()],
    price: Annotated[int, Form()],
    location: Annotated[str, Form()],
    current_user = Depends(auth_router.get_current_user)
):
    # parameters check
    c_saillies_f = await c_saillies.read()
    if c_saillies.size > config['c_saillies_max_size']:
        raise HTTPException(status_code=422, detail="c_saillies exceeds 10Mo")

    photos_f = []
    for uploadfile_obj in photos:
        if uploadfile_obj.size > config['photo_max_size']:
            raise HTTPException(status_code=422, detail="one of the photos exceeds 4Mo")
        p = {
            "content_type": uploadfile_obj.content_type,
            "data": await uploadfile_obj.read()
        } 
        photos_f.append(p)
    
    # add to db
    try:
        stallion_in_db = stallions_c.find_one({"n_sire": n_sire})
    except:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to read stallions collection")

    if stallion_in_db is not None:
        raise HTTPException(status_code=400, detail="a stallion already exists with this SIRE number")
    else:
        try:
            stallions_c.insert_one({
                "owner": current_user["_id"],
                "name": name,
                "breed": breed,
                "n_sire": n_sire,
                "c_saillies": c_saillies_f,
                "photos": photos_f,
                "main_desc": main_desc,
                "color": color,
                "birth_date": birth_date,
                "height": height,
                "offspring": offspring,
                "performance": performance,
                "pedigree": pedigree,
                "pedigree_po": pedigree_po,
                "comments": comments,
                "r_types": r_types,
                "price": price,
                "location": location
            })
        except:
            print(traceback.format_exc())
            raise HTTPException(status_code=500, detail="failed to write stallions collection")

    return {"message": "stallion registered successfully"}    