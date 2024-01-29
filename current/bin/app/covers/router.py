import logging
import logging.handlers
import traceback
from bson.objectid import ObjectId
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pymongo.errors import PyMongoError

import app.covers.utils as utils
import app.covers.schemas as schemas
import app.pricing.utils as pricing_utils
import app.contracts.utils as contracts_utils
import app.stallions.utils as stallions_utils
import app.users.utils as users_utils

from app.dependencies import get_db, get_user_from_object_id, CurrentUserGetter, CoverInDBGetter, get_current_user_id

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

# dependencies
get_current_user = CurrentUserGetter(logger)
get_cover_in_db = CoverInDBGetter(logger)

# routes
router = APIRouter(prefix='/covers')

@router.post('/cover')
async def create_cover(
    cover: schemas.CoverQuery,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    if not ObjectId.is_valid(cover.seller_id):
        raise HTTPException(status_code=422, detail="seller_id is not readable")

    seller_id = ObjectId(cover.seller_id)

    # user cant buy a cover to himself
    if seller_id == current_user["_id"]:
        raise HTTPException(status_code=400, detail="seller_id is equal to buyer_id")

    # check that seller exists
    try:
        seller_in_db = db.users.find_one({"_id": seller_id})
    except PyMongoError as exc:
        logger.error("failed to read db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to read db") from exc

    if seller_in_db is None:
        raise HTTPException(status_code=404, detail="seller not found")

    # check that all existing covers with this stallion/mare couple are over
    try:
        cover_in_db_cursor = db.covers.find({
            "stallion_nsire": cover.stallion_nsire,
            "mare_nsire": cover.mare_nsire
        },
        {
            "status": 1
        })
    except PyMongoError as exc:
        logger.error("failed to read db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to read db") from exc

    for cover_in_db in cover_in_db_cursor:
        if cover_in_db["status"] not in ["denied", "downpaid", "fullypaid"]:
            raise HTTPException(status_code=400, detail="cover already exists")

    # fetching price
    try:
        stallion_in_db = db.stallions.find_one(
            {
                "n_sire": cover.stallion_nsire,
                "owner": seller_id
            },{
                "cover_specs": 1,
                "name": 1,
                "breed": 1,
                "production_breeds": 1,
                "stallion_std_negative_tests": 1,
                "stallion_vaccines": 1,
                "profile_status": 1
            }
        )
    except PyMongoError as exc:
        logger.error("failed to read db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to read db") from exc

    if stallion_in_db is None:
        raise HTTPException(status_code=404, detail="stallion not found")

    if stallion_in_db["profile_status"] != "visible":
        raise HTTPException(status_code=403, detail="stallion not available for cover")

    # building document
    if cover.cover_type not in stallion_in_db["cover_specs"]:
        raise HTTPException(status_code=404, detail="cover type does not exist on stallion")

    new_document = cover.model_dump(exclude=["seller_id"])
    new_document["seller_id"] = seller_id

    timestamps = {
        "cursor_index": 1,
        "timestamps_list": [{"status": step, "timestamp": datetime.now() if step == config["status"][0] else None} for step in config["status"][:-1]]
    }

    cover_payment_details = pricing_utils.get_cover_payment_details(
        stallion_in_db["cover_specs"][cover.cover_type]["price"],
        pricing_config["buyer_fees_coeff"],
        pricing_config["buyer_fees_offset"],
        pricing_config["seller_fees_coeff"],
        pricing_config["seller_fees_offset"]
    )

    ## insert payment details
    del stallion_in_db["cover_specs"][cover.cover_type]["price"]
    new_document.update(cover_payment_details.model_dump())

    ## insert stallion vaccines and std tests
    new_document["stallion_vaccines"] = stallion_in_db["stallion_vaccines"]
    new_document["stallion_std_negative_tests"] = stallion_in_db["stallion_std_negative_tests"]

    ## insert cover type details
    new_document["cover_specs"] = stallion_in_db["cover_specs"][cover.cover_type]

    ## insert information left
    new_document.update({
        "status": config["status"][0],
        "buyer_id": current_user["_id"],
        "stallion_name": stallion_in_db["name"],
        "stallion_breed": stallion_in_db["breed"],
        "stallion_production_breeds": stallion_in_db["production_breeds"],
        "stallion_vaccines": stallion_in_db["stallion_vaccines"],
        "stallion_std_negative_tests": stallion_in_db["stallion_std_negative_tests"],
        "timestamps": timestamps,
        "notes" : {
            "seller": "",
            "buyer": ""
        },
        "reviewed_by_buyer": False,
        "reviewed_by_seller": False
    })

    try:
        result = db.covers.insert_one(new_document)
    except PyMongoError as exc:
        logger.error("failed to write db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to write db") from exc

    background_tasks.add_task(users_utils.notify_user, 'requested', result.inserted_id, 'seller', seller_in_db, current_user, db, logger)

    return {"message": "cover registered successfully"}

async def step_forward_cover(cover_in_db: dict, next_status: str, db = Depends(get_db)):
    cursor_index = cover_in_db["timestamps"]["cursor_index"]
    timestamps_list = cover_in_db["timestamps"]["timestamps_list"]

    if timestamps_list[cursor_index]["status"] != next_status:
        timestamps_list.insert(cursor_index, {"status": next_status, "timestamp": datetime.now()})
    else:
        timestamps_list[cursor_index]["timestamp"] = datetime.now()

    try:
        update = {
            '$set': {
                'status': next_status,
                'timestamps' + '.' + 'cursor_index': cursor_index + 1,
                'timestamps' + '.' + 'timestamps_list': timestamps_list
                }
            }
        db.covers.update_one({"_id": cover_in_db["_id"]}, update)
    except PyMongoError as exc:
        logger.error("failed to write db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to write db") from exc

@router.post('/step-forward-cover/{cover_id}')
async def manually_step_forward_cover(
    query: schemas.ManuallyStepForwardCoverQuery,
    background_tasks: BackgroundTasks,
    cover_in_db = Depends(get_cover_in_db),
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    if current_user["_id"] == cover_in_db["buyer_id"]:
        pov = "buyer"
    elif current_user["_id"] == cover_in_db["seller_id"]:
        pov = "seller"
    else:
        raise HTTPException(status_code=403, detail="no permissions to step this cover forward")

    if not utils.check_status_graph(cover_in_db["status"], query.next_status, pov):
        raise HTTPException(status_code=403, detail="no permissions to step this cover forward")

    if query.next_status == "approved" \
    and cover_in_db["cover_type"] in stallions_config["onsite_cover_types"] \
    and "arrival_date" not in cover_in_db:
        raise HTTPException(status_code=409, detail="an arrival date has to be provided")

    await step_forward_cover(cover_in_db, query.next_status, db)

    destination_pov = "seller" if pov == "buyer" else "buyer"
    background_tasks.add_task(
        users_utils.notify_user,
        query.next_status,
        cover_in_db["_id"],
        destination_pov,
        await get_user_from_object_id(cover_in_db[f"{destination_pov}_id"], db, logger),
        current_user,
        db,
        logger
    )

    return {"message": "successfully step-forwarded cover"}

@router.put('/cover/{cover_id}')
async def edit_cover(
    query: schemas.EditCoverQuery,
    cover_in_db = Depends(get_cover_in_db),
    user_id = Depends(get_current_user_id),
    db = Depends(get_db)
):
    if user_id != cover_in_db["seller_id"]:
        raise HTTPException(status_code=403, detail="only seller can edit cover")

    if cover_in_db["status"] != "requested":
        raise HTTPException(status_code=403, detail="status has to be 'requested'")

    updated_fields = {}

    if query.arrival_date != "":
        if cover_in_db["cover_type"] in stallions_config["remote_cover_types"]:
            raise HTTPException(status_code=403, detail="arrival date cannot be set on this cover type")

        try:
            arrival_date = datetime.strptime(query.arrival_date, "%d/%m/%Y")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="incorrect arrival date format") from exc

        updated_fields["arrival_date"] = arrival_date

    if query.new_subtotal is not None:
        cover_payment_details = pricing_utils.get_cover_payment_details(
            query.new_subtotal,
            pricing_config["buyer_fees_coeff"],
            pricing_config["buyer_fees_offset"],
            pricing_config["seller_fees_coeff"],
            pricing_config["seller_fees_offset"]
        )

        updated_fields.update(cover_payment_details.model_dump())

    try:
        db.covers.update_one(
            {
                "_id": cover_in_db["_id"]},
            {
                "$set":updated_fields
            }
        )
    except PyMongoError as exc:
        logger.error("failed to write db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to write db") from exc

    return {"message": "updated cover successfully"}

@router.get('/cover-group', response_model=schemas.GetCoverGroupRM)
async def get_cover_group(group: str, point_of_view: str, user_id = Depends(get_current_user_id), db = Depends(get_db)):
    # data validation
    if group not in config["groups"].keys():
        raise HTTPException(status_code=422, detail="invalid group")

    if point_of_view not in ["seller", "buyer"]:
        raise HTTPException(status_code=422, detail="invalid point of view")

    # db querying
    status_l = config["groups"][group]
    pattern = {
        'status': {'$in': status_l},
        point_of_view + '_id': user_id
    }

    try:
        pipeline = [
            {
                "$match": pattern
            },
            {
                "$project": {
                    "timestamps": 1,
                    "subtotal_ht": 1,
                    "buyer_fees_ht": 1,
                    "seller_fees_ht": 1,
                    "_id": 1,
                    "stallion_name": 1,
                    "mare_name": 1,
                    "status": 1,
                }
            },
            {
                "$unwind": "$timestamps.timestamps_list"
            },
            {
                "$group": {
                    "_id": "$_id",
                    "most_recent_timestamp": {
                        "$max": "$timestamps.timestamps_list.timestamp"
                    },
                    "subtotal_ht": {"$first": "$subtotal_ht"},
                    "buyer_fees_ht": {"$first": "$buyer_fees_ht"},
                    "seller_fees_ht": {"$first": "$seller_fees_ht"},
                    "stallion_name": {"$first": "$stallion_name"},
                    "mare_name": {"$first": "$mare_name"},
                    "status": {"$first": "$status"},
                }
            },
            {
                "$sort": {
                    "most_recent_timestamp": -1
                }
            }
        ]

        cursor = db.covers.aggregate(pipeline)
    except PyMongoError as exc:
        logger.error("failed to read db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to read db") from exc

    cover_items = []
    for document in cursor:
        if point_of_view == "seller":
            price = pricing_utils.calculate_income(
                document["subtotal_ht"],
                document["seller_fees_ht"],
                pricing_config["TVA_coeff_HT"],
                pricing_config["TVA_cover_coeff_HT"]
                ).total
        else:
            price = pricing_utils.calculate_checkout(
                document["subtotal_ht"],
                document["buyer_fees_ht"],
                pricing_config["TVA_coeff_HT"],
                pricing_config["TVA_cover_coeff_HT"]
                ).total

        cover_items.append({
            "id": str(document["_id"]),
            "stallion_name": document["stallion_name"],
            "mare_name": document["mare_name"],
            "status": document["status"],
            "price": price
        })

    return schemas.GetCoverGroupRM(items=cover_items)

@router.get('/cover/{cover_id}', response_model=schemas.GetCoverInformation)
async def get_cover_information(cover_in_db = Depends(get_cover_in_db), user_id = Depends(get_current_user_id), db = Depends(get_db)):
    if user_id == cover_in_db["seller_id"]:
        pov = "seller"
    elif user_id == cover_in_db["buyer_id"]:
        pov = "buyer"
    else:
        raise HTTPException(status_code=403, detail="only seller and buyer can get cover information")

    contact_in_db = await get_user_from_object_id(cover_in_db[("seller" if pov == "buyer" else "buyer") + "_id"], db, logger)

    contact_id = str(contact_in_db["_id"])
    if pov == "buyer" and cover_in_db["status"] in ["requested", "denied"]:
        contact_phone_number = ""
        contact_email = ""
    else:
        contact_phone_number = contact_in_db["phone_number"]
        contact_email = contact_in_db["email"]

    # price
    if pov == "seller":
        price = pricing_utils.calculate_income(
            cover_in_db["subtotal_ht"],
            cover_in_db["seller_fees_ht"],
            pricing_config["TVA_coeff_HT"],
            pricing_config["TVA_cover_coeff_HT"]
            ).total
    else:
        price = pricing_utils.calculate_checkout(
            cover_in_db["subtotal_ht"],
            cover_in_db["buyer_fees_ht"],
            pricing_config["TVA_coeff_HT"],
            pricing_config["TVA_cover_coeff_HT"]
            ).total

    # timestamps
    timestamps_list = cover_in_db["timestamps"]["timestamps_list"]

    for timestamp_dict in timestamps_list:
        if timestamp_dict["timestamp"] is None:
            timestamp_dict["timestamp"] = "-"
        else:
            timestamp_dict["timestamp"] = timestamp_dict["timestamp"].strftime("Le %d/%m/%Y à %H:%M:%S")

    return schemas.GetCoverInformation(
        stallion_name=cover_in_db["stallion_name"],
        stallion_breed=cover_in_db["stallion_breed"],
        stallion_nsire=cover_in_db["stallion_nsire"],
        stallion_production_breeds=cover_in_db["stallion_production_breeds"],
        stallion_vaccines=cover_in_db["stallion_vaccines"],
        stallion_std_negative_tests=cover_in_db["stallion_std_negative_tests"],
        mare_name=cover_in_db["mare_name"],
        mare_breed=cover_in_db["mare_breed"],
        mare_nsire=cover_in_db["mare_nsire"],
        contact_id=contact_id,
        contact_firstname=contact_in_db["firstname"],
        contact_lastname=contact_in_db["lastname"],
        contact_phone_number=contact_phone_number,
        contact_email=contact_email,
        cover_type=cover_in_db["cover_type"],
        cover_specs=cover_in_db["cover_specs"],
        arrival_date=str(cover_in_db["arrival_date"].strftime("%d/%m/%Y")) if "arrival_date" in cover_in_db else "",
        status=cover_in_db["status"],
        price=price,
        base_price=cover_in_db["subtotal_ht"],
        buyer_message=cover_in_db["message"],
        timestamps=timestamps_list,
        notes=cover_in_db["notes"][pov],
        reviewed_by_buyer=cover_in_db["reviewed_by_buyer"],
        reviewed_by_seller=cover_in_db["reviewed_by_seller"],
        pov=pov
    )

@router.put('/cover-notes/{cover_id}')
async def update_cover_notes(query: schemas.UpdateNotesQuery, cover_in_db = Depends(get_cover_in_db), user_id = Depends(get_current_user_id), db = Depends(get_db)):
    if user_id == cover_in_db["seller_id"]:
        pov = "seller"
    elif user_id == cover_in_db["buyer_id"]:
        pov = "buyer"
    else:
        raise HTTPException(status_code=403, detail="only seller and buyer can edit notes")

    try:
        db.covers.update_one(
            {"_id": cover_in_db["_id"]},
            {
                "$set": {
                    f"notes.{pov}": query.notes
                }
            }
        )
    except PyMongoError as exc:
        logger.error("failed to write db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to write db") from exc

    return {"message": "updated notes successfully"}

@router.post("/step-forward-payment/{cover_id}")
async def step_forward_payment(cover_in_db = Depends(get_cover_in_db), db = Depends(get_db)):
    if cover_in_db["status"] == "sellersigned":
        await step_forward_cover(cover_in_db, "downpaid", db)
    elif cover_in_db["status"] == "downpaid":
        await step_forward_cover(cover_in_db, "fullypaid", db)
    else:
        raise HTTPException(status_code=403)
    return {"message": "successfully step-forwarded payment"}
