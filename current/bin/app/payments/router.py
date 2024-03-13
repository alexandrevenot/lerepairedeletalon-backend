import logging
import logging.handlers
import traceback

import stripe
from fastapi import APIRouter, HTTPException, Depends, Request
from pymongo.errors import PyMongoError

import app.payments.schemas as schemas
import app.payments.utils as utils

from app.dependencies import CurrentUserGetter, get_db

# configs
global_config = utils.load_global_config()
config = utils.load_config()

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

# stripe
stripe.api_key = config["api_key"]
endpoint_secret = config["endpoint_secret"]

# dependencies
get_current_user = CurrentUserGetter(logger)

# routes
router = APIRouter(prefix='/payments')

@router.post('/stripe-account')
async def create_stripe_account(
    query: schemas.CreateStripeAccountQuery,
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    try:
        current_level = current_user["legal_identity"]["level"]
    except KeyError:
        current_level = 0

    if current_level != 2:
        raise HTTPException(status_code=409, detail="legal identity level is too low")

    if "stripe_account" in current_user:
        raise HTTPException(status_code=409, detail="already has a stripe account")

    try:
        account_creation_response = stripe.Account.create(
            type="custom",
            country="FR",
            capabilities={
                "transfers": {"requested": True}
            },
                business_profile={
                    "mcc": "0742",
                    "product_description": "Vente de saillies dans la filière équine"
                },
            account_token=query.account_token
        )
        account_id = account_creation_response["id"]

        if query.business_type == "company":
            create_person_response = stripe.Account.create_person(
                account_id,
                person_token=query.person_token
            )
            person_id = create_person_response["id"]

            token_creation_response = stripe.Token.create(
                account={
                    "company": {
                        "directors_provided": True,
                        "owners_provided": True,
                        "executives_provided": True
                    }
                },
            )
            update_account_token = token_creation_response["id"]

            stripe.Account.modify(
                account_id,
                account_token=update_account_token
            )

        create_external_account_response = stripe.Account.create_external_account(
            account_id,
            external_account=query.bank_account_token
        )

    except stripe.error.StripeError as exc1:
        try:
            stripe.Account.delete(account_id)
            logger.error("failed to create stripe account: %s", traceback.format_exc())
        except stripe.error.StripeError:
            logger.error("failed to create stripe account, and also failed to delete account: %s", traceback.format_exc())
        finally:
            raise HTTPException(status_code=500, detail="failed to create stripe account") from exc1

    if query.business_type == "company":
        stripe_account = schemas.CompanyStripeAccountInDB(
            account={
                "id": account_id,
                "company": {
                    "verification": {
                        "document": {
                            "details_code": None
                        }
                    }
                },
                "requirements": {
                    "currently_due": []
                }
            },
            person={
                "id": person_id,
                "verification": {
                    "additional_document": {
                        "details_code": None
                    },
                    "document": {
                        "details_code": None
                    },
                    "status": "pending"
                }
            }
        ).model_dump()

    else:
        stripe_account = schemas.IndividualStripeAccountInDB(
            account={
                "id": account_id,
                "individual": {
                    "verification": {
                        "additional_document": {
                            "details_code": None
                        },
                        "document": {
                            "details_code": None
                        },
                        "status": "pending"
                    }
                },
                "requirements": {
                    "currently_due": []
                }
            }
        ).model_dump()

    update = {
        "$set": {
            "stripe_account": stripe_account
        }
    }

    update["$set"]["legal_identity.level"] = 3
    update["$set"]["legal_identity.iban_last4"] = create_external_account_response["last4"]

    try:
        db.users.update_one({"_id": current_user["_id"]}, update)
    except PyMongoError as exc:
        logger.error("failed to write db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail='failed to write db') from exc

    return {"message": "successfully created striped account"}

@router.get('/stripe-account', response_model=schemas.StripeAccount)
async def get_stripe_account(current_user = Depends(get_current_user)):
    try:
        stripe_account = current_user["stripe_account"]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="no stripe account found") from exc

    currently_due_is_empty = not stripe_account["account"]["requirements"]["currently_due"]

    if current_user["legal_identity"]["business_type"] == "company":
        identity_document_status = stripe_account["person"]["verification"]["status"]
        proof_of_residence_status = identity_document_status
        if stripe_account["account"]["company"]["verification"]["document"]["details_code"] is None:
            proof_of_company_status = "not_under_verification"
        else:
            proof_of_company_status = "unverified"
    else:
        identity_document_status = stripe_account["account"]["individual"]["verification"]["status"]
        proof_of_residence_status = identity_document_status
        proof_of_company_status = None

    return schemas.StripeAccount(
        currently_due_is_empty=currently_due_is_empty,
        identity_document_status=identity_document_status,
        proof_of_residence_status=proof_of_residence_status,
        proof_of_company_status=proof_of_company_status
    )

@router.put('/stripe-account')
async def update_stripe_account(
    query: schemas.UpdateStripeAccountQuery,
    current_user = Depends(get_current_user)
):
    if "stripe_account" not in current_user:
        raise HTTPException(status_code=404, detail="no stripe account found")

    if query.update_account_token is not None:
        try:
            stripe.Account.modify(current_user["stripe_account"]["account"]["id"], account_token=query.update_account_token)
        except stripe.error.StripeError as exc:
            logger.error("failed to update stripe account: %s", traceback.format_exc())
            raise HTTPException(status_code=500, detail="failed to update stripe account") from exc

    if query.update_person_token is not None:
        try:
            stripe.Account.modify_person(
                current_user["stripe_account"]["account"]["id"],
                current_user["stripe_account"]["person"]["id"],
                person_token=query.update_person_token
            )
        except stripe.error.StripeError as exc:
            logger.error("failed to update stripe account: %s", traceback.format_exc())
            raise HTTPException(status_code=500, detail="failed to update stripe account") from exc

    return {"message": "successfully updated stripe account"}

@router.post('/stripe-accounts-webhook')
async def handle_stripe_accounts_webhook(request: Request, db = Depends(get_db)):
    data = await request.body()
    stripe_signature = request.headers['stripe-signature']

    try:
        event = stripe.Webhook.construct_event(
            payload=data, sig_header=stripe_signature, secret=endpoint_secret
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail='invalid payload') from exc
    except stripe.error.SignatureVerificationError as exc:
        raise HTTPException(status_code=400, detail='invalid signature') from exc

    if event["type"] == "person.updated":
        person = schemas.Person(**event["data"]["object"]).model_dump()
        account_id = event["data"]["object"]["account"]
        update = {
            "$set": {
                "stripe_account.person": person
            }
        }

    elif event["type"] == "account.updated":
        if event["data"]["object"]["business_type"] == "company":
            account = schemas.CompanyAccount(**event["data"]["object"]).model_dump()
        else:
            account = schemas.IndividualAccount(**event["data"]["object"]).model_dump()
        account_id = event["data"]["object"]["id"]
        update = {
            "$set": {
                "stripe_account.account": account
            }
        }

    else:
        return {"message": "successfully received webhook"}

    try:
        db.users.update_one(
            {"stripe_account.account.id": account_id},
            update
        )
    except PyMongoError as exc:
        logger.error("failed to read db: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail='failed to read db') from exc

    return {"message": "successfully received webhook"}
