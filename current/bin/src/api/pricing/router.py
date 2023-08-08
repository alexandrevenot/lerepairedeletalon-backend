import traceback

from fastapi import APIRouter, HTTPException

import src.api.pricing.schemas as schemas
import src.api.pricing.utils as utils

# global config
global_config = utils.load_global_config()

# config
config = utils.load_config()

# routes
router = APIRouter(prefix='/pricing')

@router.get('/get-checkout-simulation', response_model=schemas.PriceWithFees)
async def get_checkout(subtotal: float):
    buyer_fees = config['buyer_fees']
    TVA_coeff_HT = config["TVA_coeff_HT"]

    return utils.calculate_checkout(subtotal, buyer_fees, TVA_coeff_HT)