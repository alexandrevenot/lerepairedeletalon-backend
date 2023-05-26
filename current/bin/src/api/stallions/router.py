import traceback
from typing import Annotated

from pymongo import MongoClient
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, Depends

import src.api.stallions.utils as utils
import src.api.stallions.schemas as schemas
import src.api.auth.router as auth_router

# config
config = utils.load_config()

# db
mongo_url = "mongodb://localhost:27017/"
client = MongoClient(mongo_url)
db = client.test
stallions_c = db.stallions

# routes
router = APIRouter(prefix='/stallions')

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
    price: Annotated[str, Form()],
    current_user = Depends(auth_router.get_current_user)
):
    # parameters check
    c_saillies_f = await c_saillies.read()
    if len(c_saillies_f) > config['c_saillies_max_size']:
        raise HTTPException(status_code=422, detail="c_saillies exceeds 10Mo")

    photos_f = []
    for p in photos:
        photos_f.append(await p.read())
        if len(photos_f[-1]) > config['photo_max_size']:
            raise HTTPException(status_code=422, detail="one of the photos exceeds 4Mo")
    
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
            })
        except:
            print(traceback.format_exc())
            raise HTTPException(status_code=500, detail="failed to write stallions collection")

    return {"message": "stallion registered successfully"}    

@router.post("/files/")
async def create_file(file: Annotated[bytes, File()]):
    return {"file_size": len(file)}

@router.post("/uploadfile/")
async def create_upload_file(file: Annotated[UploadFile, File()], token: Annotated[str, Form()]):
    contents = await file.read()
    print(len(contents))
    return {"filename": file.filename}