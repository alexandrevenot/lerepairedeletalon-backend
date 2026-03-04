import logging
import logging.handlers
import traceback

import stripe
from fastapi import APIRouter, HTTPException, Depends, Request, BackgroundTasks
from pymongo.errors import PyMongoError

from . import utils
from . import schemas
from ..covers import utils as covers_utils
from ..users import utils as users_utils
from ...monitoring import tools as monitoring_tools

from ...dependencies import CurrentUserGetter, get_db, CoverInDBGetter, \
    get_user_from_object_id, get_db_client

# configs
global_config = utils.load_global_config()
config = utils.load_config()
monitoring_config = monitoring_tools.load_config()

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

# stripe
stripe.api_key = config["api_key"]
accounts_endpoint_secret = config["accounts_endpoint_secret"]
checkout_endpoint_secret = config["checkout_endpoint_secret"]

# dependencies
get_current_user = CurrentUserGetter(logger)
get_cover_in_db = CoverInDBGetter(logger)

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
        raise HTTPException(status_code=409, detail="legal identity level has to be 2")

    try:
        account_creation_response = stripe.Account.create(
            type="custom",
            country="FR",
            capabilities={
                "transfers": {"requested": True},
                "card_payments": {"requested": True}
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

            stripe.Account.modify(
                account_id,
                account_token=query.additional_account_token
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
            payload=data, sig_header=stripe_signature, secret=accounts_endpoint_secret
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

@router.get('/checkout-simulation', response_model=schemas.PriceWithFees)
async def get_checkout_simulation(subtotal: int):
    return utils.calculate_checkout(subtotal, config['fees_coeff'])

@router.get('/get-checkout-session/{cover_id}', response_model=schemas.Checkout)
async def get_checkout(
    payment_part: str,
    current_user = Depends(get_current_user),
    cover_in_db = Depends(get_cover_in_db),
    db = Depends(get_db)
):
    if payment_part not in ["advance", "balance"]:
        raise HTTPException(status_code=422, detail='payment_part has to be either "advance" or "balance"')

    if current_user["_id"] != cover_in_db["buyer_id"]:
        raise HTTPException(status_code=403, detail="only buyer can get checkout")

    if payment_part == "advance" and cover_in_db["status"] == "sellersigned":
        subtotal = utils.calculate_advance(
            cover_in_db["subtotal"],
            cover_in_db["cover_specs"]["advance_percentage"]
        )
        fees = utils.calculate_advance(
            cover_in_db["fees"],
            cover_in_db["cover_specs"]["advance_percentage"]
        )
        product_name = f"Acompte pour la saillie de {cover_in_db['stallion_name']}"
    elif payment_part == "balance" and cover_in_db["status"] == "downpaid":
        subtotal = utils.calculate_balance(
            cover_in_db["subtotal"],
            cover_in_db["cover_specs"]["advance_percentage"]
        )
        fees = utils.calculate_balance(
            cover_in_db["fees"],
            cover_in_db["cover_specs"]["advance_percentage"]
        )
        product_name = f"Solde pour la saillie de {cover_in_db['stallion_name']}"
    else:
        raise HTTPException(status_code=403, detail="status does not allow this payment")

    session = None
    # check for existing session
    if cover_in_db["status"] == "sellersigned" and "advance_session_id" in cover_in_db:
        try:
            previous_session = stripe.checkout.Session.retrieve(cover_in_db["advance_session_id"])
        except stripe.error.StripeError:
            previous_session = None

        if previous_session is not None:
            if previous_session["status"] == "open":
                session = previous_session
            elif previous_session["status"] == "complete":
                raise HTTPException(status_code=409, detail="payment is completing")

    elif cover_in_db["status"] == "downpaid" and "balance_session_id" in cover_in_db:
        try:
            previous_session = stripe.checkout.Session.retrieve(cover_in_db["balance_session_id"])
        except stripe.error.StripeError:
            previous_session = None

        if previous_session is not None:
            if previous_session["status"] == "open":
                session = previous_session
            elif previous_session["status"] == "complete":
                raise HTTPException(status_code=409, detail="payment is completing")

    # build new session if needed
    if session is None:
        seller_in_db = await get_user_from_object_id(cover_in_db["seller_id"], db, logger)

        try:
            session = stripe.checkout.Session.create(
                customer_email=current_user["email"],
                line_items=[
                    {
                        "price_data": {
                            "currency": "eur",
                            "product_data": {"name": product_name},
                            "unit_amount": int(subtotal * 100),
                            "tax_behavior": "inclusive"
                        },
                        "quantity": 1
                    },
                    {
                        "price_data": {
                            "currency": "eur",
                            "product_data": {"name": "Frais de service"},
                            "unit_amount": int(fees * 100),
                            "tax_behavior": "inclusive"
                        },
                        "quantity": 1
                    }
                ],
                payment_intent_data={
                    "application_fee_amount": int(fees * 100),
                    "transfer_data": {"destination": seller_in_db["stripe_account"]["account"]["id"]}
                },
                payment_method_options={
                    "link": {
                        "setup_future_usage": "none"
                    }
                },
                mode="payment",
                ui_mode="embedded",
                custom_text={
                    "submit": {
                        "message": "Vous acceptez nos [Conditions Générales de Vente](https://lerepairedeletalon.alexandrevenot.ovh/conditions-generales-de-vente)."
                    }
                },
                return_url=f"{global_config['frontend_url']}/tableau-de-bord?coverId={str(cover_in_db['_id'])}&pollCoverStatus={'downpaid' if payment_part == 'advance' else 'fullypaid'}"
            )
        except (KeyError, stripe.error.StripeError) as exc:
            logger.error("failed to create checkout session: %s", traceback.format_exc())
            raise HTTPException(status_code=500, detail="failed to create checkout session") from exc

        if session.client_secret is None:
            logger.error("failed to create checkout session: %s", traceback.format_exc())
            raise HTTPException(status_code=500, detail="failed to create checkout session") from exc

        try:
            db.covers.update_one(
                {"_id": cover_in_db["_id"]},
                {
                    "$set": {
                        f"{'balance' if cover_in_db['status'] == 'downpaid' else 'advance'}_session_id": session.id
                    }
                }
            )
        except PyMongoError as exc:
            logger.error("failed to write db: %s", traceback.format_exc())
            raise HTTPException(status_code=500, detail='failed to write db') from exc

    return schemas.Checkout(client_secret=session.client_secret)

@router.post('/stripe-checkout-webhook')
async def handle_stripe_checkout_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db = Depends(get_db),
    db_client = Depends(get_db_client)
):
    data = await request.body()
    try:
        stripe_signature = request.headers['stripe-signature']
    except KeyError as exc:
        raise HTTPException(status_code=401, detail="header not found") from exc

    try:
        event = stripe.Webhook.construct_event(
            payload=data, sig_header=stripe_signature, secret=checkout_endpoint_secret
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail='invalid payload') from exc
    except stripe.error.SignatureVerificationError as exc:
        raise HTTPException(status_code=400, detail='invalid signature') from exc

    if event["type"] == "checkout.session.completed":
        session_id = event['data']['object']['id']

        try:
            cover_in_db = db.covers.find_one({
                "$or": [
                    {"advance_session_id": session_id},
                    {"balance_session_id": session_id}
                ]
            })
        except PyMongoError as exc:
            logger.error("failed to read db: %s", traceback.format_exc())
            raise HTTPException(status_code=500, detail='failed to read db') from exc

        if cover_in_db is None:
            raise HTTPException(status_code=404, detail='cover not found')

        if "advance_session_id" in cover_in_db and cover_in_db["advance_session_id"] == session_id and cover_in_db["status"] == "sellersigned":
            new_status = "downpaid"
        elif "balance_session_id" in cover_in_db and cover_in_db["balance_session_id"] == session_id and cover_in_db["status"] == "downpaid":
            new_status = "fullypaid"
        else:
            return {"message": "successfully received webhook"}

        with db_client.start_session() as session:
            session.start_transaction()
            try:
                await covers_utils.step_forward_cover(cover_in_db, new_status, db, logger, session)

                seller_in_db = await get_user_from_object_id(cover_in_db["seller_id"], db, logger)
                buyer_in_db = await get_user_from_object_id(cover_in_db["buyer_id"], db, logger)
            except HTTPException as exc:
                session.abort_transaction()
                raise exc

            try:
                first_cover_sold_id = seller_in_db["first_cover_sold_id"]
            except KeyError:
                first_cover_sold_id = None

            if first_cover_sold_id is None or first_cover_sold_id == cover_in_db["_id"]:
                message = "Promotion première saillie sans frais pour les vendeurs: "
                message += f"il faudra rembourser les frais à {seller_in_db['firstname']} {seller_in_db['lastname']} "
                message += f"pour la saillie {cover_in_db['_id']}"
                background_tasks.add_task(
                    monitoring_tools.send_telegram_message,
                    message,
                    monitoring_config["telegram_api_key"],
                    logger
                )
                if first_cover_sold_id is None:
                    try:
                        db.users.update_one(
                            {"_id": seller_in_db["_id"]},
                            {
                                "$set": {
                                    "first_cover_sold_id": cover_in_db["_id"]
                                }
                            },
                            session=session
                        )
                    except PyMongoError as exc:
                        session.abort_transaction()
                        logger.error("failed to write db: %s", traceback.format_exc())
                        raise HTTPException(status_code=500, detail='failed to write db') from exc

            elif "harasdebellaly@gmail.com" in [seller_in_db["email"], buyer_in_db["email"]]:
                message = "Fanny acheteuse ou vendeuse dans une saillie: "
                message += f"il faudra lui rembourser les frais pour la saillie {cover_in_db['_id']}"
                background_tasks.add_task(
                    monitoring_tools.send_telegram_message,
                    message,
                    monitoring_config["telegram_api_key"],
                    logger
                )

            session.commit_transaction()

        message = f"Un {'acompte' if new_status == 'downpaid' else 'solde'} vient d'être payé"
        message += f"\n*Saillie*: {cover_in_db['_id']}"
        message += f"\n*Acheteur*: {buyer_in_db['firstname']} {buyer_in_db['lastname']}"
        message += f"\n*Vendeur*: {seller_in_db['firstname']} {seller_in_db['lastname']}"
        background_tasks.add_task(
            monitoring_tools.send_telegram_message,
            message,
            monitoring_config["telegram_api_key"],
            logger
        )
        users_utils.notify_user(new_status, cover_in_db["_id"], "seller", seller_in_db, buyer_in_db, db, logger)

    return {"message": "successfully received webhook"}
