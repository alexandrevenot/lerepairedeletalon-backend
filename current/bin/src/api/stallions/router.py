import logging
import logging.handlers
import traceback
from bson.objectid import ObjectId
from typing import Annotated
from datetime import datetime

from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, Query, Path
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
    min_price: int = None,
    max_price: int = None,
    min_height: int = None,
    max_height: int = None,
    lat: float = None,
    lng: float = None,
    distance: float = None, # km
    breeds: Annotated[list[str] | None, Query()] = None,
    production_breeds: Annotated[list[str] | None, Query()] = None,
    cover_types: Annotated[list[str] | None, Query()] = None,
    db = Depends(get_db)
):
    if page <= 0:
        raise HTTPException(status_code=422, detail="page can't be <= 0")

    if limit >= 50:
        raise HTTPException(status_code=422, detail="limit can't be >= 50")

    if limit <= 0:
        raise HTTPException(status_code=422, detail="limit can't be <= 0")

    if cover_types is not None:
        for cover_type in cover_types:
            if cover_type not in config["cover_types"]:
                raise HTTPException(status_code=422, detail="a cover type is not allowed")

    query = {}

    # price
    price_query = {}
    if min_price is not None:
        min_price = pricing_utils.calculate_corresponding_subtotal(min_price, pricing_config['buyer_fees_coeff'], pricing_config['buyer_fees_offset'], pricing_config['TVA_coeff_HT'])
        price_query["$gte"] = min_price

    if max_price is not None:
        max_price = pricing_utils.calculate_corresponding_subtotal(max_price, pricing_config['buyer_fees_coeff'], pricing_config['buyer_fees_offset'], pricing_config['TVA_coeff_HT'])
        price_query["$lte"] = max_price

    if price_query:
        query["$or"] = [{f'cover_specs.{cover_type}.price': price_query} for cover_type in config["cover_types"]]

    # breed
    if breeds is not None:
        query["breed"] = {"$in": breeds}

    # production breed
    if production_breeds is not None:
        query["production_breeds"] = {"$in": production_breeds}

    # height
    height_query = {}
    if min_height is not None:
        height_query["$gte"] = min_height

    if max_height is not None:
        height_query["$lte"] = max_height

    if height_query:
        query["height"] = height_query

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
            for cover_type in [elt for elt in config["cover_types"] if elt not in cover_types]:
                query["$or"].remove({f'cover_specs.{cover_type}.price': price_query})
        else:
            query["$or"] = [{f'cover_specs.{cover_type}': {"$exists": True}} for cover_type in cover_types]

    # searchability
    query["profile_status"] = "visible"

    try:
        cursor = db.stallions.find(query, {"_id": 1, "name": 1, "breed": 1, "city": 1, "dep_name": 1, "reg_name": 1, "cover_specs": 1, "thumbnail_photo": 1, "height": 1}).skip((page - 1) * limit).limit(limit)
    except Exception as exc:
        logger.error("failed to read db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail='failed to read db') from exc

    mp_l = []
    for document in cursor:
        mp_l.append(schemas.MosaicProfileInfo(
            id=str(document["_id"]),
            name=document["name"],
            breed=document["breed"],
            height=document["height"],
            cover_types=list(document["cover_specs"].keys()),
            city=document["city"],
            dep_name=document["dep_name"],
            reg_name=document["reg_name"],
            price=utils.get_displayed_price(document, min_price, max_price, config["cover_types"]) if cover_types is None \
                else utils.get_displayed_price(document, min_price, max_price, cover_types),
            photo_id=str(document["thumbnail_photo"])
        ))
    return schemas.SearchRM(content=mp_l)

async def get_stallion_in_db(stallion_id: str = Path(...), db = Depends(get_db)):
    try:
        stallion_id = ObjectId(stallion_id)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="stallion_id not readable") from exc

    try:
        stallion_in_db = db.stallions.find_one({"_id": stallion_id})
    except Exception as exc:
        logger.error("failed to read db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to read db") from exc

    if stallion_in_db is None:
        raise HTTPException(status_code=404, detail="stallion not found")

    return stallion_in_db

@router.get('/stallion-photo/{photo_id}')
async def get_stallion_photo(photo_id, db = Depends(get_db)):
    try:
        photo = db.stallion_photos.find_one({"_id": ObjectId(photo_id)})
    except Exception as exc:
        logger.error("failed to read db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail='failed to read db') from exc

    if photo is None:
        raise HTTPException(status_code=404, detail="image not found")

    image_data = photo["data"]
    image_content_type = photo["content_type"]
    return Response(content=image_data, media_type=image_content_type)

@router.get('/stallion/{stallion_id}', response_model=schemas.StallionProfileInformation | schemas.StallionCompleteProfileInformation)
async def get_stallion_profile(mode: str, stallion_in_db = Depends(get_stallion_in_db), current_user = Depends(get_current_user)):
    if mode not in ['partial', 'complete']:
        raise HTTPException(status_code=422, detail="mode has to be either 'partial' or 'complete'")

    if mode == 'partial' and stallion_in_db["profile_status"] != "visible":
        raise HTTPException(status_code=403, detail="stallion profile information cant be fetched yet")

    if mode == 'complete' and current_user["_id"] != stallion_in_db["owner"]:
        raise HTTPException(status_code=403, detail="only owner can get stallion complete information")

    kwargs = {}
    fields = [
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
        'cover_specs',
        'production_breeds',
        'cover_additional_info',
        'city',
        'stallion_std_negative_tests',
        'stallion_vaccines',
        'crossbreeding_advice'
    ]

    if mode == 'partial':
        fields += [
            'dep_name',
            'reg_name'
        ]
        kwargs['owner'] = str(stallion_in_db['owner'])
        kwargs['age'] = utils.calculate_age(stallion_in_db['birthdate'])
    else:
        fields += [
            'postal_code'
        ]
        kwargs['birthdate'] = stallion_in_db['birthdate'].strftime('%d/%m/%Y')
        kwargs['lng'] = stallion_in_db['location']['coordinates'][0]
        kwargs['lat'] = stallion_in_db['location']['coordinates'][1]

    for field in fields:
        kwargs[field] = stallion_in_db[field]

    return {
        "photos": [str(oid) for oid in stallion_in_db["photos"]],
        **kwargs
    }

@router.get('/my-stallions', response_model=schemas.GetMyStallionsRM)
async def get_my_stallions(current_user = Depends(get_current_user), db = Depends(get_db)):
    query = {"owner": current_user['_id']}

    try:
        cursor = db.stallions.find(query, {"_id": 1, "name": 1, "breed": 1, "thumbnail_photo": 1, "profile_status": 1, "last_update_timestamp":1})
    except Exception as exc:
        logger.error("failed to read db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail='failed to read db') from exc

    content = []
    for document in cursor:
        content.append(schemas.DashboardStallionBox(
            id=str(document["_id"]),
            name=document["name"],
            breed=document["breed"],
            photo_id=str(document["thumbnail_photo"]),
            profile_status=document["profile_status"],
            last_update_timestamp=document["last_update_timestamp"].strftime("le %d/%m/%Y à %H:%M")
        ))

    return schemas.GetMyStallionsRM(content=content)

@router.post('/stallion')
async def register_new_stallion(
    final_fields_body: schemas.FinalStallionFields,
    editable_fields_body: schemas.EditableStallionFields,
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    # fields parsing
    try:
        birthdate_datetime = datetime.strptime(final_fields_body.birthdate, "%d/%m/%Y")
    except Exception as exc:
        raise HTTPException(status_code=422, detail="incorrect birth_date date format") from exc

    location = {
        "type": "Point",
        "coordinates": [editable_fields_body.lng, editable_fields_body.lat]
    }

    try:
        result = geoloc_utils.find_dep_and_region(editable_fields_body.postal_code[:2])
        if not result:
            raise ValueError
    except Exception as exc:
        logger.error('failed to french deps csv: %s', traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to browse french deps csv") from exc

    dep_name = result["dep_name"]
    reg_name = result["reg_name"]

    # add to db
    try:
        stallion_in_db = db.stallions.find_one({"n_sire": final_fields_body.n_sire})
    except Exception as exc:
        logger.error("failed to read db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to read db") from exc

    if stallion_in_db is not None:
        raise HTTPException(status_code=400, detail="a stallion already exists with this SIRE number")

    try:
        insert_one_result = db.stallions.insert_one({
            "owner": current_user["_id"],
            "name": final_fields_body.name,
            "breed": final_fields_body.breed,
            "n_sire": final_fields_body.n_sire,
            "main_desc": editable_fields_body.main_desc,
            "color": editable_fields_body.color,
            "birthdate": birthdate_datetime,
            "height": editable_fields_body.height,
            "offspring": editable_fields_body.offspring,
            "performance": editable_fields_body.performance,
            "pedigree": editable_fields_body.pedigree,
            "pedigree_po": editable_fields_body.pedigree_po,
            "stallion_additional_info": editable_fields_body.stallion_additional_info,
            "stallion_std_negative_tests": editable_fields_body.stallion_std_negative_tests.model_dump(exclude_none=True),
            "stallion_vaccines": editable_fields_body.stallion_vaccines,
            "production_breeds": editable_fields_body.production_breeds,
            "cover_specs": editable_fields_body.cover_specs.model_dump(exclude_none=True),
            "cover_additional_info": editable_fields_body.cover_additional_info,
            "crossbreeding_advice": editable_fields_body.crossbreeding_advice,
            "location": location,
            "city": editable_fields_body.city,
            "postal_code": editable_fields_body.postal_code,
            "dep_name": dep_name,
            "reg_name": reg_name,
            "profile_status": "to_be_validated",
            "last_update_timestamp": datetime.now()
        })
    except Exception as exc:
        logger.error("failed to write db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to write db") from exc

    return {
        "message": "stallion registered successfully",
        "stallion_id": str(insert_one_result.inserted_id)
        }

@router.post('/stallion-files/{stallion_id}')
async def register_new_stallion_files(
    verification_file: Annotated[UploadFile, File()],
    photos: Annotated[list[UploadFile], File()],
    stallion_in_db = Depends(get_stallion_in_db),
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    if current_user["_id"] != stallion_in_db["owner"]:
        raise HTTPException(status_code=403, detail="only owner can post stallion files")

    if "photos" in stallion_in_db or "verification_file" in stallion_in_db:
        raise HTTPException(status_code=403, detail="can post only once on this route")

    if not 1 <= len(photos) <= 5:
        raise HTTPException(status_code=422, detail="there must be between 1 and 5 photos")

    if verification_file.size > config['verification_file_max_size']:
        raise HTTPException(status_code=422, detail="verification_file is too large")

    verification_file_obj = {}
    verification_file_obj["content_type"] = verification_file.content_type
    verification_file_obj["data"] = await verification_file.read()

    for photo_f in photos:
        if photo_f.size > config['photo_max_size']:
            raise HTTPException(status_code=422, detail="one of the photos is too large")

    photo_obj_list = []
    data = await photos[0].read()
    content_type = photos[0].content_type
    photo_obj_list.append({
        "content_type": content_type,
        "data": data
    })

    try:
        thumbnail_photo = {
            "content_type": content_type,
            "data": utils.get_thumbnail_photo_data(data, content_type, config['photo_low_res_width'])
        }
    except Exception as exc:
        logger.error("failed to process photos: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to process photos") from exc

    for photo_f in photos[1:]:
        p = {
            "content_type": photo_f.content_type,
            "data": await photo_f.read()
        }
        photo_obj_list.append(p)

    try:
        db.stallions.update_one({
            "_id": stallion_in_db["_id"]
        },
        {
            "$set": {
                "verification_file": db.verification_files.insert_one(verification_file_obj).inserted_id,
                "thumbnail_photo": db.stallion_photos.insert_one(thumbnail_photo).inserted_id,
                "photos": [db.stallion_photos.insert_one(photo).inserted_id for photo in photo_obj_list],
                "last_update_timestamp": datetime.now()
            }
        })
    except Exception as exc:
        logger.error("failed to write db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to write db") from exc

    return {"message": "successfully added stallion files"}

@router.put('/stallion/{stallion_id}')
async def edit_stallion_profile(
    editable_fields_body: schemas.EditableStallionFields,
    stallion_in_db = Depends(get_stallion_in_db),
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):

    if current_user["_id"] != stallion_in_db["owner"]:
        raise HTTPException(status_code=403, detail="only owner can edit stallion")

    location = {
        "type": "Point",
        "coordinates": [editable_fields_body.lng, editable_fields_body.lat]
    }

    try:
        result = geoloc_utils.find_dep_and_region(editable_fields_body.postal_code[:2])
        if not result:
            raise ValueError
    except Exception as exc:
        logger.error('failed to french deps csv: %s', traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to browse french deps csv") from exc

    dep_name = result["dep_name"]
    reg_name = result["reg_name"]

    try:
        db.stallions.update_one({
            "_id": stallion_in_db["_id"]
        },
        {
            "$set": {
                "main_desc": editable_fields_body.main_desc,
                "color": editable_fields_body.color,
                "height": editable_fields_body.height,
                "offspring": editable_fields_body.offspring,
                "performance": editable_fields_body.performance,
                "pedigree": editable_fields_body.pedigree,
                "pedigree_po": editable_fields_body.pedigree_po,
                "stallion_additional_info": editable_fields_body.stallion_additional_info,
                "stallion_std_negative_tests": editable_fields_body.stallion_std_negative_tests.model_dump(exclude_none=True),
                "stallion_vaccines": editable_fields_body.stallion_vaccines,
                "production_breeds": editable_fields_body.production_breeds,
                "cover_specs": editable_fields_body.cover_specs.model_dump(exclude_none=True),
                "cover_additional_info": editable_fields_body.cover_additional_info,
                "crossbreeding_advice": editable_fields_body.crossbreeding_advice,
                "location": location,
                "city": editable_fields_body.city,
                "postal_code": editable_fields_body.postal_code,
                "dep_name": dep_name,
                "reg_name": reg_name,
                "last_update_timestamp": datetime.now()
            }
        })
    except Exception as exc:
        logger.error("failed to write db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to write db") from exc

    return {"message": "updated stallion successfully"}

@router.put('/stallion-files/{stallion_id}')
async def update_stallion_photos(
    photos: Annotated[list[UploadFile], File()],
    stallion_in_db = Depends(get_stallion_in_db),
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    if current_user["_id"] != stallion_in_db["owner"]:
        raise HTTPException(status_code=403, detail="only owner can update stallion photos")

    for photo_f in photos:
        if photo_f.size > config['photo_max_size']:
            raise HTTPException(status_code=422, detail="one of the photos is too large")

    photo_obj_list = []
    data = await photos[0].read()
    content_type = photos[0].content_type
    photo_obj_list.append({
        "content_type": content_type,
        "data": data
    })

    try:
        thumbnail_photo = {
            "content_type": content_type,
            "data": utils.get_thumbnail_photo_data(data, content_type, config['photo_low_res_width'])
        }
    except Exception as exc:
        logger.error("failed to process photos: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to process photos") from exc

    for photo_f in photos[1:]:
        p = {
            "content_type": photo_f.content_type,
            "data": await photo_f.read()
        }
        photo_obj_list.append(p)

    try:
        db.stallion_photos.delete_many({
            "_id": {
                "$in": stallion_in_db["photos"] + [stallion_in_db["thumbnail_photo"]]
            }
        })
    except Exception as exc:
        logger.error("failed to write db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to write db") from exc

    try:
        db.stallions.update_one({
            "_id": stallion_in_db["_id"]
        },
        {
            "$set": {
                "thumbnail_photo": db.stallion_photos.insert_one(thumbnail_photo).inserted_id,
                "photos": [db.stallion_photos.insert_one(photo).inserted_id for photo in photo_obj_list],
                "last_update_timestamp": datetime.now()
            }
        })
    except Exception as exc:
        logger.error("failed to write db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to write db") from exc

    return {"message": "successfully updated stallion photos"}


@router.delete('/stallion/{stallion_id}')
async def delete_stallion(stallion_in_db = Depends(get_stallion_in_db), current_user = Depends(get_current_user), db = Depends(get_db)):
    if current_user["_id"] != stallion_in_db["owner"]:
        raise HTTPException(status_code=403, detail="only owner can delete stallion")

    if "photos" in stallion_in_db:
        try:
            db.stallion_photos.delete_many({
                "_id": {
                    "$in": stallion_in_db["photos"] + [stallion_in_db["thumbnail_photo"]]
                }
            })
        except Exception as exc:
            logger.error("failed to write db: %s", traceback.format_exc())
            raise HTTPException(status_code=500, detail="failed to write db") from exc

    if "verification_file" in stallion_in_db:
        try:
            db.verification_files.delete_one({"_id": stallion_in_db["verification_file"]})
        except Exception as exc:
            logger.error("failed to write db: %s", traceback.format_exc())
            raise HTTPException(status_code=500, detail="failed to write db") from exc

    try:
        db.stallions.delete_one({"_id": stallion_in_db["_id"]})
    except Exception as exc:
        logger.error("failed to write db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to write db") from exc

    return {"message": "successfully deleted stallion"}

@router.put('/stallion-profile-status/{stallion_id}')
async def update_stallion_profile_status(
    new_status: str,
    stallion_in_db = Depends(get_stallion_in_db),
    current_user = Depends(get_current_user),
    db = Depends(get_db)
    ):
    if current_user["_id"] != stallion_in_db["owner"]:
        raise HTTPException(status_code=403, detail="only owner can change stallion profile status")

    if new_status == "visible":
        if stallion_in_db["profile_status"] != "hidden":
            raise HTTPException(status_code=403, detail="cannot change to that profile status")
    elif new_status == "hidden":
        if stallion_in_db["profile_status"] != "visible":
            raise HTTPException(status_code=403, detail="cannot change to that profile status")
    else:
        raise HTTPException(status_code=403, detail="cannot change to that profile status")

    try:
        db.stallions.update_one(
            {"_id": stallion_in_db["_id"]},
            {
                "$set": {
                    "profile_status": new_status
                }
            })
    except Exception as exc:
        logger.error("failed to write db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to write db") from exc

    return {"message": "successfully updated stallion profile status"}
