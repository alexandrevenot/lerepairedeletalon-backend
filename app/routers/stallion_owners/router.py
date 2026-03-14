import logging
import logging.handlers
import traceback
from bson.objectid import ObjectId

from fastapi import APIRouter, HTTPException, Depends
from pymongo.errors import PyMongoError

from . import schemas

from ...dependencies import get_db, CurrentUserGetter, StallionOwnerInDBGetter

# logging
logger = logging.getLogger(__name__)
logger.setLevel(20)
handler = logging.handlers.RotatingFileHandler(
    f'logs/{__name__}.log',
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
get_stallion_owner_in_db = StallionOwnerInDBGetter(logger)

# routes
router = APIRouter(prefix='/stallion-owners')

@router.post('/stallion-owner', response_model=schemas.StallionOwnerPostResponse)
async def create_stallion_owner(
    query: schemas.StallionOwnerQuery,
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    if query.business_type == "company":
        if any(getattr(query, field, "") == "" for field in ["company_structure", "company_name", "capital", "siren",
                                                            "head_office_address_line1", "head_office_address_postal_code",
                                                            "head_office_address_city", "gender", "role_in_company",
                                                            "firstname", "lastname"]):
            raise HTTPException(status_code=422, detail='missing fields')
    elif query.business_type == "individual":
        if any(getattr(query, field, "") == "" for field in ["gender", "birthdate", "birthplace", "citizenship", "firstname",
                                                            "lastname", "address_line1", "address_postal_code", "address_city"]):
            raise HTTPException(status_code=422, detail='missing fields')

    document = query.model_dump(exclude_none=True)
    document["handler_id"] = current_user["_id"]

    try:
        result = db.stallion_owners.insert_one(document)
    except PyMongoError as exc:
        logger.error("failed to write db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail='failed to write db') from exc

    return {
        "message": "successfully created stallion owner",
        "id": str(result.inserted_id)
    }

@router.get('/stallion-owner-names', response_model=schemas.StallionOwnerNames)
async def get_stallion_owner_names(current_user = Depends(get_current_user), db = Depends(get_db)):
    try:
        stallion_owners = db.stallion_owners.find({"handler_id": current_user["_id"]})
    except PyMongoError as exc:
        logger.error("failed to read db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail='failed to read db') from exc

    return schemas.StallionOwnerNames(stallion_owners=[{
        "id": str(stallion_owner["_id"]),
        **stallion_owner
    } for stallion_owner in stallion_owners])

@router.put('/stallion-owner/{stallion_owner_id}')
async def update_stallion_owner(
    query: schemas.StallionOwnerQuery,
    current_user = Depends(get_current_user),
    db = Depends(get_db),
    stallion_owner_in_db = Depends(get_stallion_owner_in_db)
):
    if current_user["_id"] != stallion_owner_in_db["handler_id"]:
        raise HTTPException(status_code=403, detail="cannot put this stallion owner")

    if query.business_type == "company":
        if any(getattr(query, field, "") == "" for field in ["company_structure", "company_name", "capital", "siren",
                                                            "head_office_address_line1", "head_office_address_postal_code",
                                                            "head_office_address_city", "gender", "role_in_company",
                                                            "firstname", "lastname"]):
            raise HTTPException(status_code=422, detail='missing fields')
    elif query.business_type == "individual":
        if any(getattr(query, field, "") == "" for field in ["gender", "birthdate", "birthplace", "citizenship", "firstname",
                                                            "lastname", "address_line1", "address_postal_code", "address_city"]):
            raise HTTPException(status_code=422, detail='missing fields')

    fields_and_values = query.model_dump(exclude_none=True)

    try:
        db.stallion_owners.update_one(
            {"_id": stallion_owner_in_db["_id"]},
            {
                "$set": fields_and_values
            }
        )
    except PyMongoError as exc:
        logger.error("failed to write db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail='failed to write db') from exc

    return {"message": "successfully updated stallion owner"}

@router.delete('/stallion-owner/{stallion_owner_id}')
async def delete_stallion_owner(
    stallion_id: str,
    current_user = Depends(get_current_user),
    db = Depends(get_db),
    stallion_owner_in_db = Depends(get_stallion_owner_in_db)
):
    if current_user["_id"] != stallion_owner_in_db["handler_id"]:
        raise HTTPException(status_code=403, detail="cannot delete this stallion owner")

    if stallion_id != "":
        if not ObjectId.is_valid(stallion_id):
            raise HTTPException(status_code=422, detail="stallion_id not readable")
        stallion_id = ObjectId(stallion_id)

    try:
        stallions = list(db.stallions.find({"stallion_owner_id": stallion_owner_in_db["_id"]}))
    except PyMongoError as exc:
        logger.error("failed to read db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail='failed to read db') from exc

    if len(stallions) > 0:
        if stallion_id != "" and stallion_id in [stallion["_id"] for stallion in stallions]:
            raise HTTPException(status_code=409, detail="this stallion is linked to this stallion owner")
        raise HTTPException(status_code=409, detail="a stallion is linked to this stallion owner")

    try:
        db.stallion_owners.delete_one({"_id": stallion_owner_in_db["_id"]})
    except PyMongoError as exc:
        logger.error("failed to write db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail='failed to write db') from exc

    return {"message": "successfully deleted stallion owner"}
