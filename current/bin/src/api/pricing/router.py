import logging
import logging.handlers
from fastapi import APIRouter, HTTPException, Depends

import src.api.pricing.schemas as schemas
import src.api.pricing.utils as utils

from src.api.auth.router import get_current_user
from src.api.covers.router import get_cover_in_db

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
@router.get('/checkout/{cover_id}', response_model=schemas.Checkout)
async def get_checkout(cover_in_db = Depends(get_cover_in_db), current_user = Depends(get_current_user)):    
    if current_user["_id"] != cover_in_db["buyer_id"]:
        raise HTTPException(status_code=403, detail="only buyer can get checkout")

    if cover_in_db["status"] == "sellersigned":
        advance_subtotal = utils.calculate_advance(cover_in_db["subtotal"], cover_in_db["cover_specs"]["advance_percentage"], True)
        advance_buyer_fees_ht = utils.calculate_advance(cover_in_db["buyer_fees_ht"], cover_in_db["cover_specs"]["advance_percentage"], False)
        checkout = utils.calculate_checkout(advance_subtotal, advance_buyer_fees_ht, config["TVA_coeff_HT"])
    elif cover_in_db["status"] == "downpaid":
        balance_subtotal = utils.calculate_balance(cover_in_db["subtotal"], cover_in_db["cover_specs"]["advance_percentage"], True)
        balance_buyer_fees_ht = utils.calculate_balance(cover_in_db["buyer_fees_ht"], cover_in_db["cover_specs"]["advance_percentage"], False)
        checkout = utils.calculate_checkout(balance_subtotal, balance_buyer_fees_ht, config["TVA_coeff_HT"])
    else:
        raise HTTPException(status_code=403, detail="status does not allow payment")

    return schemas.Checkout(
        subtotal=checkout.subtotal,
        service_fees=checkout.service_fees,
        total=checkout.total,
        status=cover_in_db["status"]
    )
