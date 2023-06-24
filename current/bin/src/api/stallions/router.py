import traceback
from bson.objectid import ObjectId
from typing import Annotated
from datetime import datetime

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
stallions_photos_c = db.stallions_photos
c_saillies_c = db.c_saillies

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
    if min_price is not None:
        price_query["$gte"] = min_price
    if max_price is not None:
        price_query["$lte"] = max_price
    
    if price_query:
        query["price"] = price_query

    # breed
    if breeds is not None:
        query["breed"] = {"$in": breeds}
    if colors is not None:
        query["color"] = {"$in": colors}

    cursor = stallions_c.find(query, {"_id": 1, "name": 1, "location": 1, "price": 1, "photos": 1}).skip((page - 1) * limit).limit(limit)

    mp_l = []
    for document in cursor:
        mp_l.append(schemas.MosaicProfileInfo(
            id=str(document["_id"]),
            name=document["name"],
            location=document["location"],
            price=document["price"],
            photoId=str(document["photos"][0])
        ))
    
    return schemas.SearchRM(content=mp_l)

@router.get('/get-stallion-photo')
async def get_stallion_photo(id: str):
    photo = stallions_photos_c.find_one({"_id": ObjectId(id)})

    if photo:
        image_data = photo["data"]
        image_content_type = photo["content_type"]
        return Response(content=image_data, media_type=image_content_type)
    else:
        return HTTPException(status_code=404, detail="Image not found.")

@router.get('/get-stallion-profile-information')
async def get_stallion_profile(id: str, current_user = Depends(auth_router.get_current_user)):
    stallion = stallions_c.find_one(
        {"_id": ObjectId(id)},
        {
            "_id": 0
        }
    )
    
    if stallion:
        stallion["owner"] = str(stallion["owner"])
        stallion["c_saillies"] = str(stallion["c_saillies"])
        for i in range(len(stallion["photos"])):
            stallion["photos"][i] = str(stallion["photos"][i])

        return {"stallionProfile": stallion}
    else:
        return HTTPException(status_code=404, detail="Stallion not found.")

@router.get('/get-my-stallions', response_model=schemas.GetMyStallionsRM)
async def get_my_stallions(current_user = Depends(auth_router.get_current_user)):
    query = {"owner": current_user['_id']}
    cursor = stallions_c.find(query, {"_id": 1, "name": 1, "breed": 1, "photos": 1})

    content = []
    for document in cursor:
        content.append(schemas.DashboardStallionBox(
            id=str(document["_id"]),
            name=document["name"],
            breed=document["breed"],
            photoId=str(document["photos"][0])
        ))
    
    return schemas.GetMyStallionsRM(content=content)

@router.post('/register-new-stallion')
async def register_new_stallion(
    name: Annotated[str, Form()],
    breed: Annotated[str, Form()],
    n_sire: Annotated[str, Form()],
    c_saillies: Annotated[UploadFile, File()],
    photos: list[UploadFile],
    main_desc: Annotated[str, Form()],
    color: Annotated[str, Form()],
    birthdate: Annotated[str, Form()],
    height: Annotated[int, Form()],
    offspring: Annotated[str, Form()],
    performance: Annotated[str, Form()],
    pedigree: Annotated[str, Form()],
    pedigree_po: Annotated[str, Form()],
    comments: Annotated[str, Form()],
    r_types: Annotated[str, Form()],
    price: Annotated[int, Form()],
    location: Annotated[str, Form()],
    current_user = Depends(auth_router.get_current_user)
):
    # parameters parsing
    if c_saillies.size > config['c_saillies_max_size']:
        raise HTTPException(status_code=422, detail="c_saillies exceeds 10Mo")

    c_saillies_f = {}
    c_saillies_f["content_type"] = c_saillies.content_type
    c_saillies_f["data"] = await c_saillies.read()

 
    photos_f = []
    for uploadfile_obj in photos:
        if uploadfile_obj.size > config['photo_max_size']:
            raise HTTPException(status_code=422, detail="one of the photos exceeds 4Mo")
        p = {
            "content_type": uploadfile_obj.content_type,
            "data": await uploadfile_obj.read()
        } 
        photos_f.append(p)
    
    processed_r_types = {}
    r_types_list = r_types.split(',')
    for r_type in config["r_types"]:
        processed_r_types[r_type] = r_type in r_types_list
    
    processed_pedigree = {}
    for i, parent_name in zip(range(1,15), pedigree.split('~')):
        processed_pedigree["p" + str(i)] = parent_name

    try:
        processed_birthdate = str(datetime.strptime(birthdate, "%d/%m/%Y").date())
    except:
        raise HTTPException(status_code=422, detail="Incorrect birth_date date format.")

    # add to db
    try:
        stallion_in_db = stallions_c.find_one({"n_sire": n_sire})
    except:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to read stallions collection")

    if stallion_in_db is not None:
        raise HTTPException(status_code=400, detail="a stallion already exists with this SIRE number")
    else:
        # c_saillies
        try:
            c_saillies_iores = c_saillies_c.insert_one(c_saillies_f)
            c_saillies_id = c_saillies_iores.inserted_id

            photos_ids = []
            for photo in photos_f:
                photos_ids.append(stallions_photos_c.insert_one(photo).inserted_id)
            stallions_c.insert_one({
                "owner": current_user["_id"],
                "name": name,
                "breed": breed,
                "n_sire": n_sire,
                "c_saillies": c_saillies_id,
                "photos": photos_ids,
                "main_desc": main_desc,
                "color": color,
                "birthdate": processed_birthdate,
                "height": height,
                "offspring": offspring,
                "performance": performance,
                "pedigree": pedigree,
                "pedigree_po": pedigree_po,
                "comments": comments,
                "r_types": processed_r_types,
                "price": price,
                "location": location
            })
        except:
            print(traceback.format_exc())
            raise HTTPException(status_code=500, detail="failed to write into database")

    return {"message": "stallion registered successfully"}    