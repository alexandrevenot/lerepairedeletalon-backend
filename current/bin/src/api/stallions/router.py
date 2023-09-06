import logging
import logging.handlers
import traceback
from bson.objectid import ObjectId
from typing import Annotated
from datetime import datetime

from fastapi import APIRouter, File, UploadFile, Form, HTTPException, Depends, Query
from fastapi.responses import Response

import src.api.stallions.utils as utils
import src.api.stallions.schemas as schemas
import src.api.geoloc.utils as geoloc_utils
import src.api.pricing.utils as pricing_utils

from src.database.db import get_db
from src.api.auth.router import get_current_user

# configs
global_config = utils.load_global_config()
config = utils.load_config()
pricing_config = pricing_utils.load_config()

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
router = APIRouter(prefix='/stallions')

@router.get('/search', response_model=schemas.SearchRM)
async def search(
    page: int,
    limit: int,
    min_price: float = None,
    max_price: float = None,
    lat: float = None,
    lng: float = None,
    distance: float = None, # km
    breeds: Annotated[list[str] | None, Query()] = None,
    production_breeds: Annotated[list[str] | None, Query()] = None,
    colors: Annotated[list[str] | None, Query()] = None,
    cover_types: Annotated[list[str] | None, Query()] = None,
    db = Depends(get_db)
):
    if page <= 0:
        raise HTTPException(status_code=422, detail="page can't be <= 0")

    if limit >= 50:
        raise HTTPException(status_code=422, detail="limit can't be >= 50")

    if limit <= 0:
        raise HTTPException(status_code=422, detail="limit can't be <= 0")

    if colors is not None:
        for color in colors:
            if color not in config["colors"]:
                raise HTTPException(status_code=422, detail="a color is not allowed")

    if production_breeds is not None:
        for production_breed in production_breeds:
            if production_breed not in config["breeds"]:
                raise HTTPException(status_code=422, detail="a production breed is not allowed")

    if breeds is not None:
        for breed in breeds:
            if breed not in config["breeds"]:
                raise HTTPException(status_code=422, detail="a breed is not allowed")

    if cover_types is not None:
        for cover_type in cover_types:
            if cover_type not in config["cover_types"]:
                raise HTTPException(status_code=422, detail="a cover type is not allowed")

    query = {}

    # price
    price_query = {}
    if min_price is not None:
        min_price = pricing_utils.calculate_real_min_price(min_price, pricing_config['buyer_fees'], pricing_config['TVA_coeff_HT'])
        price_query["$gte"] = min_price

    if max_price is not None:
        max_price = pricing_utils.calculate_real_max_price(max_price, pricing_config['buyer_fees'], pricing_config['TVA_coeff_HT'])
        price_query["$lte"] = max_price

    if price_query:
        query["prices"] = {}
        query["prices"]["$elemMatch"] = {}
        query["prices"]["$elemMatch"]["price"] = price_query

    # breed
    if breeds is not None:
        query["breed"] = {"$in": breeds}

    # production breed
    if production_breeds is not None:
        query["production_breeds"] = {"$in": production_breeds}

    # color
    if colors is not None:
        query["color"] = {"$in": colors}
    
    # distance
    distance_case = 0
    for var in [lat, lng, distance]:
        if var is not None:
            distance_case += 1
    
    if distance_case in [1, 2]:
        raise HTTPException(status_code=422, detail="Incomplete distance parameters")
    if distance_case == 3:
        query["location"] = {}
        query["location"]["$geoWithin"] = {}
        query["location"]["$geoWithin"]["$centerSphere"] = [[lng, lat], distance / 6371.0]
    
    # cover type
    if cover_types is not None:
        if price_query:
            query["prices"]["$elemMatch"]["cover_type"] = {"$in": cover_types}
        else:
            query["prices"] = {}
            query["prices"]["$elemMatch"] = {}
            query["prices"]["$elemMatch"]["cover_type"] = {"$in": cover_types}

    try:
        cursor = db.stallions.find(query, {"_id": 1, "name": 1, "breed": 1, "city": 1, "dep_name": 1, "reg_name": 1, "prices": 1, "photos": 1}).skip((page - 1) * limit).limit(limit)
    except Exception as exc:
        logger.error(f'failed to read db: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail='failed to read db') from exc

    mp_l = []
    for document in cursor:
        mp_l.append(schemas.MosaicProfileInfo(
            id=str(document["_id"]),
            name=document["name"],
            breed=document["breed"],
            city=document["city"],
            dep_name=document["dep_name"],
            reg_name=document["reg_name"],
            price=utils.get_displayed_price(document, min_price, max_price),
            photo_id=str(document["photos"][0])
        ))

    return schemas.SearchRM(content=mp_l)

@router.get('/stallion-photo')
async def get_stallion_photo(photo_id: str, db = Depends(get_db)):
    try:
        photo = db.stallions_photos.find_one({"_id": ObjectId(photo_id)})
    except Exception as exc:
        logger.error(f'failed to read db: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail='failed to read db') from exc

    if photo is None:
        raise HTTPException(status_code=404, detail="image not found")

    image_data = photo["data"]
    image_content_type = photo["content_type"]
    return Response(content=image_data, media_type=image_content_type)

@router.get('/stallion-profile-information', response_model=schemas.GetStallionProfileInformationRM)
async def get_stallion_profile(stallion_id: str, current_user = Depends(get_current_user), db = Depends(get_db)):
    try:
        stallion_in_db = db.stallions.find_one(
            {"_id": ObjectId(stallion_id)},
            {
                "_id": 0,
                "c_saillies": 0
            }
        )
    except Exception as exc:
        logger.error(f'failed to read db: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail='failed to read db') from exc
    
    if stallion_in_db is None:
        raise HTTPException(status_code=404, detail="stallion not found")
    
    if not stallion_in_db["searchable"]:
        raise HTTPException(status_code=403, detail="stallion profile information cant be fetched yet")

    kwargs = {}
    for field in [
        'name',
        'breed',
        'n_sire',
        'main_desc',
        'color',
        'height',
        'offspring',
        'performance',
        'pedigree',
        'pedigree_po',
        'stallion_additional_info',
        'prices',
        'production_breeds',
        'cover_additional_info',
        'location',
        'city',
        'postal_code',
        'dep_name',
        'reg_name'
    ]:
        kwargs[field] = stallion_in_db[field]

    stallion = schemas.StallionProfileInformation(
        owner=str(stallion_in_db['owner']),
        photos=[str(oid) for oid in stallion_in_db["photos"]],
        age=utils.calculate_age(stallion_in_db["birthdate"]),
        **kwargs
    )

    return {"stallionProfile": stallion}

@router.get('/my-stallions', response_model=schemas.GetMyStallionsRM)
async def get_my_stallions(current_user = Depends(get_current_user), db = Depends(get_db)):
    query = {"owner": current_user['_id']}

    try:
        cursor = db.stallions.find(query, {"_id": 1, "name": 1, "breed": 1, "photos": 1, "searchable": 1})
    except Exception as exc:
        logger.error(f'failed to read db: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail='failed to read db') from exc

    content = []
    for document in cursor:
        content.append(schemas.DashboardStallionBox(
            id=str(document["_id"]),
            name=document["name"],
            breed=document["breed"],
            photoId=str(document["photos"][0]),
            searchable=document["searchable"]
        ))
    
    return schemas.GetMyStallionsRM(content=content)

@router.post('/register-new-stallion')
async def register_new_stallion(
    name: Annotated[str, Form()],
    breed: Annotated[str, Form()],
    n_sire: Annotated[str, Form()],
    c_saillies: Annotated[UploadFile, File()],
    photos: Annotated[list[UploadFile], File()],
    main_desc: Annotated[str, Form()],
    color: Annotated[str, Form()],
    height: Annotated[float, Form()],
    birthdate: Annotated[str, Form()],
    lat: Annotated[float, Form()],
    lng: Annotated[float, Form()],
    city: Annotated[str, Form()],
    postal_code: Annotated[str, Form()],
    production_breeds: Annotated[list[str], Form()],
    cover_types: Annotated[list[str], Form()],
    cover_places: Annotated[list[str], Form()],
    prices: Annotated[list[int], Form()],
    pedigree: Annotated[list[str], Form()] = None,
    cover_additional_info: Annotated[str, Form()] = "",
    performance: Annotated[str, Form()] = "",
    pedigree_po: Annotated[str, Form()] = "",
    stallion_additional_info: Annotated[str, Form()] = "",
    offspring: Annotated[str, Form()] = "",
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    # parameters parsing
    if breed not in config['breeds']:
        raise HTTPException(status_code=422, detail='breed is not available')

    if c_saillies.size > config['c_saillies_max_size']:
        raise HTTPException(status_code=422, detail="c_saillies is too large")

    c_saillies_f = {}
    c_saillies_f["content_type"] = c_saillies.content_type
    c_saillies_f["data"] = await c_saillies.read()

    photos_f = []
    for uploadfile_obj in photos:
        if uploadfile_obj.size > config['photo_max_size']:
            raise HTTPException(status_code=422, detail="one of the photos is too large")
        p = {
            "content_type": uploadfile_obj.content_type,
            "data": await uploadfile_obj.read()
        } 
        photos_f.append(p)
    
    if color not in config['colors']:
        raise HTTPException(status_code=422, detail='color is not available')

    try:
        birthdate_datetime = datetime.strptime(birthdate, "%d/%m/%Y")
    except Exception as exc:
        raise HTTPException(status_code=422, detail="incorrect birth_date date format") from exc

    location = {
        "type": "Point",
        "coordinates": [lng, lat]
    }

    try:
        result = geoloc_utils.find_dep_and_region(postal_code[:2])
        if not result:
            raise ValueError
    except Exception as exc:
        logger.error(f'failed to french deps csv: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail="failed to browse french deps csv") from exc
    
    dep_name = result["dep_name"]
    reg_name = result["reg_name"]

    for p_breed in production_breeds:
        if p_breed not in config["breeds"]:
            raise HTTPException(status_code=422, detail='a production breed is not available')
    if sorted(production_breeds) != sorted(list(set(production_breeds))):
        raise HTTPException(status_code=422, detail='atleast 1 production breed is duplicated')


    length = len(cover_types)
    for l in [cover_places, prices]:
        if len(l) != length:
            raise HTTPException(status_code=422, detail="cover places, types and prices lengths are not equal")

    if sorted(cover_types) != sorted(list(set(cover_types))):
        raise HTTPException(status_code=422, detail='atleast 1 cover type is duplicated')

    processed_prices = []
    for cover_type, cover_place, price in zip(cover_types, cover_places, prices):
        if cover_type in config["cover_types"]:
            processed_prices.append({"cover_type": cover_type, "cover_place": cover_place ,"price": price})
        else:
            raise HTTPException(status_code=422, detail="unknown cover type")

    if pedigree is None:
        pedigree = []

    if len(pedigree) > 14:
        raise HTTPException(status_code=422, detail="too many items in pedigree")

    if len(pedigree) <= 14:
        pedigree = pedigree + ["" for _ in range(14 - len(pedigree))]

    # add to db
    try:
        stallion_in_db = db.stallions.find_one({"n_sire": n_sire})
    except Exception as exc:
        logger.error(f'failed to read db: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail="failed to read db") from exc

    if stallion_in_db is not None:
        raise HTTPException(status_code=400, detail="a stallion already exists with this SIRE number")

    try:
        c_saillies_iores = db.c_saillies.insert_one(c_saillies_f)
        c_saillies_id = c_saillies_iores.inserted_id

        photos_ids = []
        for photo in photos_f:
            photos_ids.append(db.stallions_photos.insert_one(photo).inserted_id)
        db.stallions.insert_one({
            "owner": current_user["_id"],
            "name": name,
            "breed": breed,
            "n_sire": n_sire,
            "c_saillies": c_saillies_id,
            "photos": photos_ids,
            "main_desc": main_desc,
            "color": color,
            "birthdate": birthdate_datetime,
            "height": height,
            "offspring": offspring,
            "performance": performance,
            "pedigree": pedigree,
            "pedigree_po": pedigree_po,
            "stallion_additional_info": stallion_additional_info,
            "production_breeds": production_breeds,
            "prices": processed_prices,
            "cover_additional_info": cover_additional_info,
            "location": location,
            "city": city,
            "postal_code": postal_code,
            "dep_name": dep_name,
            "reg_name": reg_name,
            "searchable": False
        })
    except Exception as exc:
        logger.error(f'failed to read db: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail="failed to write db") from exc

    return {"message": "stallion registered successfully"}    