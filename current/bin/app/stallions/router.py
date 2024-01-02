import uuid
import logging
import logging.handlers
import traceback
from typing import Annotated
from datetime import datetime

from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, Query
from pymongo.errors import PyMongoError

import app.stallions.utils as utils
import app.stallions.schemas as schemas
import app.geoloc.utils as geoloc_utils
import app.pricing.utils as pricing_utils

from app.dependencies import get_db, CurrentUserGetter, StallionInDBGetter, get_db_client, BucketGetter

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

# dependencies
get_current_user = CurrentUserGetter(logger)
get_stallion_in_db = StallionInDBGetter(logger)
get_stalllion_photos_bucket = BucketGetter(global_config['stallion_photos_bucket_name'])
get_admin_files_bucket = BucketGetter(global_config['admin_files_bucket_name'])

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
        min_price = pricing_utils.calculate_corresponding_subtotal(
            min_price,
            pricing_config['buyer_fees_coeff'],
            pricing_config['buyer_fees_offset'],
            pricing_config['TVA_coeff_HT'],
            pricing_config['TVA_cover_coeff_HT'],
            "min")
        price_query["$gte"] = min_price

    if max_price is not None:
        max_price = pricing_utils.calculate_corresponding_subtotal(
            max_price,
            pricing_config['buyer_fees_coeff'],
            pricing_config['buyer_fees_offset'],
            pricing_config['TVA_coeff_HT'],
            pricing_config['TVA_cover_coeff_HT'],
            "max")
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
    except PyMongoError as exc:
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
            photo_url=document["thumbnail_photo"]
        ))
    return schemas.SearchRM(content=mp_l)

@router.get('/stallion/{stallion_id}', response_model=schemas.StallionProfileInformationForFavorite | schemas.StallionProfileInformation | schemas.StallionProfileInformationForEdition)
async def get_stallion_profile(mode: str, stallion_in_db = Depends(get_stallion_in_db), current_user = Depends(get_current_user)):
    if mode not in ['for_favorite', 'profile', 'for_edition']:
        raise HTTPException(status_code=422, detail="mode has to be either 'for_favorite', 'profile' or 'for_edition'")

    if mode == 'profile' and stallion_in_db["profile_status"] != "visible":
        raise HTTPException(status_code=403, detail="stallion profile information cant be fetched")

    if mode == 'for_edition' and current_user["_id"] != stallion_in_db["owner"]:
        raise HTTPException(status_code=403, detail="only owner can get stallion information for edition")

    if mode == 'for_favorite':
        return schemas.StallionProfileInformationForFavorite(
            name=stallion_in_db["name"],
            breed=stallion_in_db["breed"],
            thumbnail_photo=stallion_in_db["thumbnail_photo"],
            profile_status=stallion_in_db["profile_status"]
        )

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
        'crossbreeding_advice',
        'photos'
    ]

    if mode == 'profile':
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

    return kwargs

@router.get('/my-stallions', response_model=schemas.GetMyStallionsRM)
async def get_my_stallions(current_user = Depends(get_current_user), db = Depends(get_db)):
    query = {"owner": current_user['_id']}

    try:
        cursor = db.stallions.find(query, {"_id": 1, "name": 1, "breed": 1, "thumbnail_photo": 1, "profile_status": 1, "last_update_timestamp":1})
    except PyMongoError as exc:
        logger.error("failed to read db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail='failed to read db') from exc

    content = []
    for document in cursor:
        content.append(schemas.DashboardStallionBox(
            id=str(document["_id"]),
            name=document["name"],
            breed=document["breed"],
            photo_url=document["thumbnail_photo"],
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
    except ValueError as exc:
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
    except PyMongoError as exc:
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
    except PyMongoError as exc:
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
    db = Depends(get_db),
    stallion_photos_bucket = Depends(get_stalllion_photos_bucket),
    admin_files_bucket = Depends(get_admin_files_bucket),
    db_client = Depends(get_db_client)
):
    if current_user["_id"] != stallion_in_db["owner"]:
        raise HTTPException(status_code=403, detail="only owner can post stallion files")

    if "photos" in stallion_in_db or "verification_file" in stallion_in_db:
        raise HTTPException(status_code=403, detail="can post only once on this route")

    if not 1 <= len(photos) <= 5:
        raise HTTPException(status_code=422, detail="there must be between 1 and 5 photos")

    if verification_file.content_type not in config['allowed_verification_file_content_types']:
        raise HTTPException(status_code=422, detail="verification file type not allowed")

    if verification_file.size > config['verification_file_max_size']:
        raise HTTPException(status_code=422, detail="verification_file is too large")

    for photo_f in photos:
        if photo_f.content_type not in config['allowed_photos_content_types']:
            raise HTTPException(status_code=422, detail="a photo content type is not allowed")
        if photo_f.size > config['photo_max_size']:
            raise HTTPException(status_code=422, detail="a photo is too large")

    data = await photos[0].read()
    content_type = photos[0].content_type

    try:
        thumbnail_photo, tp_content_type = utils.get_thumbnail_photo_data(data, content_type, config['photo_low_res_width'])
    except Exception as exc:
        logger.error("failed to process photos: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to process photos") from exc

    vf_blob_name = str(uuid.uuid4()) + '.' + verification_file.content_type.split('/')[1]
    vf_blob = admin_files_bucket.blob(vf_blob_name)
    vf_blob.content_type = verification_file.content_type

    tp_blob_name = str(uuid.uuid4()) + '.' + tp_content_type
    tp_blob = stallion_photos_bucket.blob(tp_blob_name)
    tp_blob.content_type = 'image/' + tp_content_type

    photos_blob_names = []
    photo_blobs = []
    for photo_f in photos:
        blob_name = str(uuid.uuid4()) + '.' + photo_f.content_type.split('/')[1]
        photos_blob_names.append(blob_name)
        blob = stallion_photos_bucket.blob(blob_name)
        blob.content_type = photo_f.content_type
        photo_blobs.append(blob)

    with db_client.start_session() as session:
        with session.start_transaction():
            try:
                db.stallions.update_one({
                    "_id": stallion_in_db["_id"]
                },
                {
                    "$set": {
                        "verification_file": vf_blob_name,
                        "thumbnail_photo": tp_blob_name,
                        "photos": photos_blob_names,
                        "last_update_timestamp": datetime.now()
                    }
                })

                vf_blob.upload_from_file(verification_file.file, rewind=True)
                tp_blob.upload_from_file(thumbnail_photo, rewind=True)

                for photo_blob, photo_f in zip(photo_blobs, photos):
                    photo_blob.upload_from_file(photo_f.file, rewind=True)

            except PyMongoError as exc:
                logger.error("failed to write db: %s", traceback.format_exc())
                raise HTTPException(status_code=500, detail="failed to write db") from exc

            except Exception as exc:
                logger.error("failed to write object storage: %s", traceback.format_exc())
                raise HTTPException(status_code=500, detail="failed to write object storage") from exc

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
    except PyMongoError as exc:
        logger.error("failed to write db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to write db") from exc

    return {"message": "updated stallion successfully"}

@router.put('/stallion-files/{stallion_id}')
async def update_stallion_photos(
    kept_photos: list[int] = None, # photos indexes to keep, ex: [0, 2, 3]
    new_photos: Annotated[list[UploadFile], File()] = None,
    stallion_in_db = Depends(get_stallion_in_db),
    current_user = Depends(get_current_user),
    db = Depends(get_db),
    db_client = Depends(get_db_client),
    stallion_photos_bucket = Depends(get_stalllion_photos_bucket)
):
    if kept_photos is None:
        kept_photos = []
    if new_photos is None:
        new_photos = []

    if current_user["_id"] != stallion_in_db["owner"]:
        raise HTTPException(status_code=403, detail="only owner can update stallion photos")

    if "photos" not in stallion_in_db or "thumbnail_photo" not in stallion_in_db:
        raise HTTPException(status_code=403, detail="cannot put stallion files yet")

    if kept_photos != sorted(kept_photos) \
    or kept_photos != list(set(kept_photos)) \
    or any(index >= len(stallion_in_db["photos"]) or index < 0 for index in kept_photos):
        raise HTTPException(status_code=422, detail="invalid kept_photos")

    if not 1 <= len(new_photos) + len(kept_photos) <= 5:
        raise HTTPException(status_code=422, detail="there must remain between 1 and 5 photos")

    for photo_f in new_photos:
        if photo_f.content_type not in config['allowed_photos_content_types']:
            raise HTTPException(status_code=422, detail="a photo content type is not allowed")
        if photo_f.size > config['photo_max_size']:
            raise HTTPException(status_code=422, detail="one of the photos is too large")

    # thumbnail
    if 0 not in kept_photos:
        # then the thumbnail photo will change
        if len(kept_photos) == 0:
            data = await new_photos[0].read()
            content_type = new_photos[0].content_type
        else:
            index_of_new_thumbnail_photo = kept_photos[0]
            new_thumbnail_photo_blob = stallion_photos_bucket.blob(stallion_in_db["photos"][index_of_new_thumbnail_photo])
            data = new_thumbnail_photo_blob.download_as_string()
            content_type = new_thumbnail_photo_blob.content_type

        try:
            new_thumbnail_photo, new_tp_content_type = utils.get_thumbnail_photo_data(data, content_type, config['photo_low_res_width'])
        except KeyError as exc:
            if str(exc) == "'OCTET-STREAM'":
                raise HTTPException(status_code=422, detail="issue on image format") from exc
            raise
        except Exception as exc:
            logger.error("failed to process photos: %s", traceback.format_exc())
            raise HTTPException(status_code=500, detail="failed to process photos") from exc

        new_tp_blob_name = str(uuid.uuid4()) + '.' + new_tp_content_type
        new_tp_blob = stallion_photos_bucket.blob(new_tp_blob_name)
        new_tp_blob.content_type = 'image/' + new_tp_content_type
        should_update_thumbnail = True
    else:
        should_update_thumbnail = False

    # kept and removed photos blob names
    kept_photos_blob_names = []
    removed_photos_blob_names = []
    for index in range(len(stallion_in_db["photos"])):
        if index in kept_photos:
            kept_photos_blob_names.append(stallion_in_db["photos"][index])
        else:
            removed_photos_blob_names.append(stallion_in_db["photos"][index])

    # new photos
    new_photos_blob_names = []
    new_photos_blobs = []
    for photo_f in new_photos:
        blob_name = str(uuid.uuid4()) + '.' + photo_f.content_type.split('/')[1]
        new_photos_blob_names.append(blob_name)
        blob = stallion_photos_bucket.blob(blob_name)
        blob.content_type = photo_f.content_type
        new_photos_blobs.append(blob)

    with db_client.start_session() as session:
        with session.start_transaction():
            try:
                kwargs = {}

                if should_update_thumbnail:
                    kwargs["thumbnail_photo"] = new_tp_blob_name

                kwargs["photos"] = kept_photos_blob_names + new_photos_blob_names


                db.stallions.update_one({
                    "_id": stallion_in_db["_id"]
                },
                {
                    "$set": {
                        **kwargs,
                        "last_update_timestamp": datetime.now()
                    }
                })

                # delete previous files from object storage
                if should_update_thumbnail:
                    old_tp_blob = stallion_photos_bucket.blob(stallion_in_db["thumbnail_photo"])
                    # thumbnail blob name is still the old one in stallion_in_db dictionnary variable value
                removed_photos_blobs = [stallion_photos_bucket.blob(photo_blob_name) for photo_blob_name in removed_photos_blob_names]

                if should_update_thumbnail:
                    old_tp_blob.delete()
                for blob in removed_photos_blobs:
                    blob.delete()

                # upload new photos
                if should_update_thumbnail:
                    new_tp_blob.upload_from_file(new_thumbnail_photo, rewind=True)
                for photo_blob, photo_f in zip(new_photos_blobs, new_photos):
                    photo_blob.upload_from_file(photo_f.file, rewind=True)

            except PyMongoError as exc:
                logger.error("failed to write db: %s", traceback.format_exc())
                raise HTTPException(status_code=500, detail="failed to write db") from exc

            except Exception as exc:
                logger.error("failed to write object storage: %s", traceback.format_exc())
                raise HTTPException(status_code=500, detail="failed to write object storage") from exc

    return {"message": "successfully updated stallion photos"}

@router.delete('/stallion/{stallion_id}')
async def delete_stallion(
    stallion_in_db = Depends(get_stallion_in_db),
    current_user = Depends(get_current_user),
    db = Depends(get_db),
    db_client = Depends(get_db_client),
    stallion_photos_bucket = Depends(get_stalllion_photos_bucket),
    admin_files_bucket = Depends(get_admin_files_bucket)
    ):
    if current_user["_id"] != stallion_in_db["owner"]:
        raise HTTPException(status_code=403, detail="only owner can delete stallion")

    with db_client.start_session() as session:
        with session.start_transaction():
            try:
                db.stallions.delete_one({"_id": stallion_in_db["_id"]})

                if "photos" in stallion_in_db:
                    old_tp_blob = stallion_photos_bucket.blob(stallion_in_db["thumbnail_photo"])
                    old_photo_blobs = [stallion_photos_bucket.blob(photo_blob_name) for photo_blob_name in stallion_in_db["photos"]]

                    old_tp_blob.delete()
                    for blob in old_photo_blobs:
                        blob.delete()

                if "verification_file" in stallion_in_db:
                    vf_blob = admin_files_bucket.blob(stallion_in_db["verification_file"])
                    vf_blob.delete()

            except PyMongoError as exc:
                logger.error("failed to write db: %s", traceback.format_exc())
                raise HTTPException(status_code=500, detail="failed to write db") from exc

            except Exception as exc:
                logger.error("failed to write object storage: %s", traceback.format_exc())
                raise HTTPException(status_code=500, detail="failed to write object storage") from exc

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
    except PyMongoError as exc:
        logger.error("failed to write db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to write db") from exc

    return {"message": "successfully updated stallion profile status"}

@router.get('/favorites', response_model=schemas.FavoriteStallions)
async def get_favorite_stallions(current_user = Depends(get_current_user)):
    if "favorite_stallions" in current_user:
        return schemas.FavoriteStallions(favorite_stallions=[str(sid) for sid in current_user["favorite_stallions"]])

    return schemas.FavoriteStallions(favorite_stallions=[])

@router.delete('/favorites/{stallion_id}')
async def delete_stallion_from_favorites(
    current_user = Depends(get_current_user),
    stallion_in_db = Depends(get_stallion_in_db),
    db = Depends(get_db)
):
    if "favorite_stallions" not in current_user or stallion_in_db["_id"] not in current_user["favorite_stallions"]:
        raise HTTPException(status_code=422, detail="stallion not in favorites or no favorite stallions")

    try:
        db.users.update_one(
            {"_id": current_user["_id"]},
            {"$pull": {
                "favorite_stallions": stallion_in_db["_id"]
            }}
        )
    except PyMongoError as exc:
        logger.error("failed to write db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to write db") from exc

    return {"message": "successfully deleted stallion from favorites"}

@router.post('/favorites/{stallion_id}')
async def add_a_favorite_stallion(
    current_user = Depends(get_current_user),
    stallion_in_db = Depends(get_stallion_in_db),
    db = Depends(get_db)
):
    if "favorite_stallions" in current_user:
        if stallion_in_db["_id"] in current_user["favorite_stallions"]:
            raise HTTPException(status_code=422, detail="stallion already in favorites")

        try:
            db.users.update_one(
                {"_id": current_user["_id"]},
                {"$push": {
                    "favorite_stallions": stallion_in_db["_id"]
                }}
            )
        except PyMongoError as exc:
            logger.error("failed to write db: %s", traceback.format_exc())
            raise HTTPException(status_code=500, detail="failed to write db") from exc

    else:
        try:
            db.users.update_one(
                {"_id": current_user["_id"]},
                {"$set": {
                    "favorite_stallions": [stallion_in_db["_id"]]
                }}
            )
        except PyMongoError as exc:
            logger.error("failed to write db: %s", traceback.format_exc())
            raise HTTPException(status_code=500, detail="failed to write db") from exc

    return {"message": "successfully added stallion to favorites"}
