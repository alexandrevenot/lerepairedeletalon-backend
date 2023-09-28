import logging
import logging.handlers
import traceback
from bson.objectid import ObjectId
from fastapi import APIRouter, HTTPException, Depends

import src.api.pricing.schemas as schemas
import src.api.pricing.utils as utils

from src.api.auth.router import get_current_user
from src.database.db import get_db

# config
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

# routes
router = APIRouter(prefix='/pricing')

@router.get('/checkout-simulation', response_model=schemas.PriceWithFees)
async def get_checkout_simulation(subtotal: int):
    buyer_fees_ht = utils.calculate_fees_ht(subtotal, config['buyer_fees_coeff'], config['buyer_fees_offset'])
    TVA_coeff_HT = config["TVA_coeff_HT"]
    return utils.calculate_checkout(subtotal, buyer_fees_ht, TVA_coeff_HT)

# to be updated with mangopay
@router.get('/checkout', response_model=schemas.Checkout)
async def get_checkout(cover_id: str, current_user = Depends(get_current_user), db = Depends(get_db)):
    try:
        cover_id = ObjectId(cover_id)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="unprocessable cover_id") from exc

    try:
        cover_in_db = db.covers.find_one({"_id": cover_id})
    except Exception as exc:
        logger.error(f'failed to read db: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail="failed to read db") from exc

    if cover_in_db is None:
        raise HTTPException(status_code=404, detail="cover not found")
    
    if current_user["_id"] != cover_in_db["buyer_id"]:
        raise HTTPException(status_code=403, detail="only buyer can get checkout")
    
    if cover_in_db["status"] == "sellersigned":
        checkout = utils.calculate_checkout(cover_in_db["advance_subtotal"], cover_in_db["advance_buyer_fees_ht"], config["TVA_coeff_HT"])
    elif cover_in_db["status"] == "downpaid":
        checkout = utils.calculate_checkout(cover_in_db["balance_subtotal"], cover_in_db["balance_buyer_fees_ht"], config["TVA_coeff_HT"])
    else:
        raise HTTPException(status_code=403, detail="status does not allow payment")

    return schemas.Checkout(
        subtotal=checkout.subtotal,
        service_fees=checkout.service_fees,
        total=checkout.total,
        status=cover_in_db["status"]
    )
