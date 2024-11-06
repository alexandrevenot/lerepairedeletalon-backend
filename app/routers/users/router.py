import logging
import logging.handlers
import traceback
import math
from datetime import datetime

from bson.objectid import ObjectId

from fastapi import APIRouter, Depends, HTTPException
from pymongo.errors import PyMongoError

import routers.users.utils as utils
import routers.users.schemas as schemas
import routers.payments.utils as payments_utils

from dependencies import get_db, UserInDBGetter, CurrentUserGetter, CoverInDBGetter, get_db_client, BucketGetter

# configs
global_config = utils.load_global_config()
config = utils.load_config()

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
get_user_in_db = UserInDBGetter(logger)
get_current_user = CurrentUserGetter(logger)
get_cover_in_db = CoverInDBGetter(logger)
get_stalllion_photos_bucket = BucketGetter(global_config['stallion_photos_bucket_name'])

# routes
router = APIRouter(prefix='/users')

@router.get('/user-name')
async def get_user(current_user = Depends(get_current_user)):
    return schemas.GetUserRM(
        firstname=current_user['firstname'],
        lastname=current_user['lastname']
    )

@router.get('/account-information', response_model=schemas.GetAccountInformation)
async def get_account_information(current_user = Depends(get_current_user)):
    try:
        legal_identity = schemas.LegalIdentity(**current_user['legal_identity'])
    except KeyError:
        legal_identity = None

    kwargs = {}
    for field in ["firstname", "lastname", "email", "phone_number"]:
        kwargs[field] = current_user[field]

    kwargs["user_id"] = str(current_user["_id"])

    if legal_identity is not None:
        kwargs["legal_identity"] = legal_identity

    return schemas.GetAccountInformation(**kwargs)

@router.put('/legal-identity', response_model=schemas.PutLegalIdentityResponse)
async def put_legal_identity(query: schemas.PutLegalIdentityQuery, current_user = Depends(get_current_user), db = Depends(get_db)):
    try:
        current_level = current_user["legal_identity"]["level"]
    except KeyError:
        current_level = 0

    try:
        legal_identity = current_user["legal_identity"]
    except KeyError:
        legal_identity = {}

    if current_level >= 3 and "business_type" in legal_identity \
    and legal_identity["business_type"] != query.business_type:
        raise HTTPException(status_code=403, detail="cannot change business type once level 3 is reached")

    legal_identity_new_fields = {}
    new_level = 0
    if query.business_type == "company":
        for field in ["company_structure", "company_name", "capital", "rcs",
                      "siren", "head_office_address_line1", "head_office_address_line2",
                      "head_office_address_postal_code", "head_office_address_city",
                      "gender", "role_in_company", "birthdate", "address_line1",
                      "address_line2", "address_postal_code", "address_city"]:
            value = getattr(query, field)
            if value is not None:
                legal_identity_new_fields[field] = value

        legal_identity.update(legal_identity_new_fields)

        if all(legal_identity.get(field, None) is not None for field in ["company_structure", "company_name", "capital", "siren",
                                                              "head_office_address_line1", "head_office_address_postal_code",
                                                              "head_office_address_city", "gender", "role_in_company"]):
            new_level = 1
            if all(legal_identity.get(field, None) is not None for field in ["birthdate", "address_line1", "address_city",
                                                                             "address_postal_code"]):
                new_level = 2
                if "stripe_account" in current_user:
                    new_level = 3

    elif query.business_type == "individual":
        for field in ["gender", "birthdate", "birthplace", "citizenship", "address_line1",
                      "address_line2", "address_postal_code", "address_city"]:
            value = getattr(query, field)
            if value is not None:
                legal_identity_new_fields[field] = value

        legal_identity.update(legal_identity_new_fields)

        if all(legal_identity.get(field, None) is not None for field in ["gender", "birthdate", "birthplace", "citizenship",
                                                                         "address_line1", "address_postal_code", "address_city"]):
            new_level = 2
            if "stripe_account" in current_user:
                new_level = 3

    update = {
        '$set': {
            'legal_identity.business_type': query.business_type,
            'legal_identity.level': new_level
        }
    }

    for field, value in legal_identity_new_fields.items():
        update["$set"][f"legal_identity.{field}"] = value

    try:
        db.users.update_one({'_id': current_user['_id']}, update)
    except PyMongoError as exc:
        logger.error("failed to write db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail='failed to write db') from exc

    return schemas.PutLegalIdentityResponse(
        message='successfully put legal identity',
        new_level=new_level
    )

@router.get('/reviews/{user_id}', response_model=schemas.Reviews)
async def get_user_reviews(
    review_pov: str, # given or received
    cover_pov: str, # as buyer or as seller
    _ = Depends(get_current_user),
    user_in_db = Depends(get_user_in_db),
    db = Depends(get_db)
):
    if review_pov not in ["given", "received"]:
        raise HTTPException(status_code=422, detail='review_pov has to be either "given" or "received"')

    if cover_pov not in ["buyer", "seller"]:
        raise HTTPException(status_code=422, detail='cover_pov has to be either "buyer" or "seller"')

    if "reviews" in user_in_db and review_pov in user_in_db["reviews"] and cover_pov in user_in_db["reviews"][review_pov]:
        review_ids = user_in_db["reviews"][review_pov][cover_pov]
    else:
        return schemas.Reviews(reviews=[])

    try:
        review_cursor = db.reviews.find({"_id": {"$in": [ObjectId(review_id) for review_id in review_ids]}}).sort("writing_date", -1)
    except PyMongoError as exc:
        logger.error("failed to read db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to read db") from exc

    return schemas.Reviews(
        reviews=[
            schemas.Review(
                stallion_name=review["stallion_name"],
                stallion_nsire=review["stallion_nsire"],
                reviewed_firstname=review["reviewed_firstname"],
                reviewed_lastname=review["reviewed_lastname"],
                reviewer_firstname=review["reviewer_firstname"],
                reviewer_lastname=review["reviewer_lastname"],
                writing_date=review["writing_date"].strftime("le %d/%m/%Y"),
                content=review["content"],
                score=review["score"]
            ) for review in review_cursor
        ]
    )

@router.post('/reviews/{user_id}')
async def post_user_review(
    query: schemas.ReviewQuery,
    current_user = Depends(get_current_user),
    user_in_db = Depends(UserInDBGetter(logger)),
    db = Depends(get_db),
    db_client = Depends(get_db_client)
):
    cover_in_db = await get_cover_in_db(query.cover_id, db)

    # reviewer is in cover check
    if current_user["_id"] not in [cover_in_db["buyer_id"], cover_in_db["seller_id"]]:
        raise HTTPException(status_code=403, detail="no permissions to write a review")

    # reviewed is in cover check
    if user_in_db["_id"] not in [cover_in_db["buyer_id"], cover_in_db["seller_id"]]:
        raise HTTPException(status_code=403, detail="no permissions to write a review")

    # check that user is not reviewing himself
    if current_user["_id"] == user_in_db["_id"]:
        raise HTTPException(status_code=403, detail="user cannot review itself")

    reviewer_is_buyer = current_user["_id"] == cover_in_db["buyer_id"]

    # status check
    if cover_in_db["status"] not in ["downpaid", "fullypaid"]:
        raise HTTPException(status_code=403, detail="cover status does not allow review writing")

    if reviewer_is_buyer and cover_in_db["reviewed_by_buyer"] \
    or not reviewer_is_buyer and cover_in_db["reviewed_by_seller"]:
        raise HTTPException(status_code=403, detail="cover has already been reviewed")

    review = {
        "reviewer_id": current_user["_id"],
        "reviewed_id": user_in_db["_id"],
        "cover_id": cover_in_db["_id"],
        "stallion_name": cover_in_db["stallion_name"],
        "stallion_nsire": cover_in_db["stallion_nsire"],
        "reviewer_firstname": current_user["firstname"],
        "reviewer_lastname": current_user["lastname"],
        "reviewed_firstname": user_in_db["firstname"],
        "reviewed_lastname": user_in_db["lastname"],
        "reviewer_is_buyer": reviewer_is_buyer,
        "writing_date": datetime.now(),
        "content": query.content,
        "score": query.score
    }

    with db_client.start_session() as session:
        session.start_transaction()
        try:
            insert_one_result = db.reviews.insert_one(review, session=session)
            inserted_id = insert_one_result.inserted_id

            db.users.update_one(
                {"_id": current_user["_id"]},
                {
                    "$push": {
                        f"reviews.given.{'buyer' if reviewer_is_buyer else 'seller'}": inserted_id
                    }
                },
                session=session
            )

            db.users.update_one(
                {"_id": user_in_db["_id"]},
                {
                    "$push": {
                        f"reviews.received.{'seller' if reviewer_is_buyer else 'buyer'}": inserted_id
                    }
                },
                session=session
            )

            reviewed_pov = 'seller' if reviewer_is_buyer else 'buyer'
            if reviewed_pov == 'buyer':
                try:
                    len_old_reviews_list = len(user_in_db["reviews"]["received"]["buyer"])
                except KeyError:
                    len_old_reviews_list = 0

                try:
                    old_buyer_score = user_in_db["buyer_score"]
                except KeyError:
                    old_buyer_score = 0

                new_average_score = ((old_buyer_score * len_old_reviews_list) + query.score)/(len_old_reviews_list + 1)

                db.users.update_one(
                    {"_id": user_in_db["_id"]},
                    {
                        "$set": {
                            "buyer_score": new_average_score
                        }
                    },
                    session=session
                )
            else:
                try:
                    len_old_reviews_list = user_in_db["seller_score"][cover_in_db["stallion_nsire"]]["nb"]
                except KeyError:
                    len_old_reviews_list = 0

                try:
                    old_buyer_score = user_in_db["seller_score"][cover_in_db["stallion_nsire"]]["avg_score"]
                except KeyError:
                    old_buyer_score = 0

                new_average_score = ((old_buyer_score * len_old_reviews_list) + query.score)/(len_old_reviews_list + 1)

                db.users.update_one(
                    {"_id": user_in_db["_id"]},
                    {
                        "$set": {
                            f"seller_score.{cover_in_db['stallion_nsire']}.avg_score": new_average_score,
                            f"seller_score.{cover_in_db['stallion_nsire']}.nb": len_old_reviews_list + 1
                        }
                    },
                    session=session
                )

            db.covers.update_one(
                {"_id": cover_in_db["_id"]},
                {
                    "$set": {
                        f"reviewed_by_{'buyer' if reviewer_is_buyer else 'seller'}": True
                    }
                },
                session=session
            )
            session.commit_transaction()

        except PyMongoError as exc:
            session.abort_transaction()
            logger.error("failed to write db: %s", traceback.format_exc())
            raise HTTPException(status_code=500, detail="failed to write db") from exc

    return {"message": "reviewed cover successfully"}

@router.get('/user-score/{user_id}', response_model=schemas.UserScore)
async def get_user_score(
    cover_pov: str, # as buyer or as seller
    stallion_nsire: str = None,
    _ = Depends(get_current_user),
    user_in_db = Depends(get_user_in_db)
):
    if cover_pov not in ["seller", "buyer"]:
        raise HTTPException(status_code=422, detail='cover_pov has to be either "buyer" or "seller"')

    if cover_pov == "buyer":
        if "buyer_score" in user_in_db:
            score = math.floor(user_in_db["buyer_score"] * 10)/10
        else:
            score = None

        try:
            nb_reviews = len(user_in_db["reviews"]["received"]["buyer"])
        except KeyError:
            nb_reviews = None

        return schemas.UserScore(
            firstname=user_in_db['firstname'],
            lastname=user_in_db['lastname'],
            score=score,
            nb_reviews=nb_reviews
        )

    # cover_pov == "seller"
    if stallion_nsire is not None:
        try:
            score = math.floor(user_in_db["seller_score"][stallion_nsire]["avg_score"] * 10)/10
        except KeyError:
            score = None
        try:
            nb_reviews = user_in_db["seller_score"][stallion_nsire]["nb"]
        except KeyError:
            nb_reviews = None

        owner_has_other_reviews = False
        try:
            other_stallion_nsires_for_which_there_are_reviews = list(user_in_db["seller_score"].keys())
            if stallion_nsire in other_stallion_nsires_for_which_there_are_reviews:
                other_stallion_nsires_for_which_there_are_reviews.remove(stallion_nsire)
            if len(other_stallion_nsires_for_which_there_are_reviews) > 0:
                owner_has_other_reviews = True
        except KeyError:
            pass

        return schemas.UserScore(
            firstname=user_in_db['firstname'],
            lastname=user_in_db['lastname'],
            score=score,
            nb_reviews=nb_reviews,
            owner_has_other_reviews=owner_has_other_reviews
        )

    # cover_pov == "seller" and stallion_nsire is None
    if "seller_score" in user_in_db:
        nb_reviews = 0
        score_sum = 0
        for value in user_in_db["seller_score"].values():
            score_sum += value["avg_score"] * value["nb"]
            nb_reviews += value["nb"]

        if nb_reviews > 0:
            score = math.floor(score_sum * 10 / nb_reviews) / 10
        else:
            score = None
            nb_reviews = None
    else:
        score = None
        nb_reviews = None

    return schemas.UserScore(
        firstname=user_in_db['firstname'],
        lastname=user_in_db['lastname'],
        score=score,
        nb_reviews=nb_reviews
    )

@router.get('/cover-notifications')
async def get_cover_notifications(current_user = Depends(get_current_user)):
    try:
        return schemas.CoverNotifications(**current_user["notifications"]["covers"])
    except (TypeError, KeyError):
        return schemas.CoverNotifications()

@router.post('/cover-notifications')
async def post_cover_notifications(
    query: schemas.AcknowledgedCoverNotifications,
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    try:
        db.users.update_one(
            {
                "_id": current_user["_id"]
            },
            {
                "$pull": {
                    f"notifications.covers.{query.pov}.{query.group}": {
                        "$in": [ObjectId(cover_id) for cover_id in query.cover_ids]
                    }
                }
            }
        )

    except PyMongoError as exc:
        logger.error("failed to write db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to write db") from exc

    except Exception as exc:
        logger.error("failed to write object storage: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to write object storage") from exc

@router.put('/delete-account')
async def delete_account(
    _: schemas.DeleteAccountQuery,
    current_user = Depends(get_current_user),
    db = Depends(get_db),
    db_client = Depends(get_db_client),
    stallion_photos_bucket = Depends(get_stalllion_photos_bucket)
):
    with db_client.start_session() as session:
        session.start_transaction()
        try:
            try:
                stripe_accound_id = current_user["stripe_account"]["account"]["id"]
            except KeyError:
                stripe_accound_id = None

            if stripe_accound_id is not None:
                payments_utils.delete_stripe_account(stripe_accound_id)

            db.stallion_owners.delete_many({
                "handler_id": current_user["_id"]
            }, session=session)

            db.password_update_codes.delete_many({
                "email": current_user["email"]
            }, session=session)

            db.email_verification_codes.delete_many({
                "email": current_user["email"]
            }, session=session)

            for stallion_in_db in db.stallions.find({"owner": current_user["_id"]}):
                db.stallions.delete_one({"_id": stallion_in_db["_id"]}, session=session)

                db.users.update_many(
                    {"favorite_stallions": {"$exists": True, "$in": [stallion_in_db["_id"]]}},
                    {
                        "$pull": {
                            "favorite_stallions": stallion_in_db["_id"]
                        }
                    },
                    session=session
                )

                if "photos" in stallion_in_db:
                    old_tp_blob = stallion_photos_bucket.blob(stallion_in_db["thumbnail_photo"])
                    old_photo_blobs = [stallion_photos_bucket.blob(photo_blob_name) for photo_blob_name in stallion_in_db["photos"]]

                    old_tp_blob.delete()
                    for blob in old_photo_blobs:
                        blob.delete()

            db.users.delete_one({"_id": current_user["_id"]}, session=session)
            session.commit_transaction()

        except PyMongoError as exc:
            session.abort_transaction()
            logger.error("failed to write db: %s", traceback.format_exc())
            raise HTTPException(status_code=500, detail="failed to write db") from exc

        except Exception as exc:
            session.abort_transaction()
            logger.error("failed to write object storage: %s", traceback.format_exc())
            raise HTTPException(status_code=500, detail="failed to write object storage") from exc

    return {"message": "successfully deleted account"}

@router.get('/test-date-format')
async def test_date_format(date: str):
    try:
        datetime.strptime(date, "%d/%m/%Y")
    except Exception as exc:
        raise HTTPException(status_code=422) from exc
