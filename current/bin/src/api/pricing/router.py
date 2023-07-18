import traceback
import math

from fastapi import APIRouter, HTTPException

import src.api.pricing.schemas as schemas
import src.api.pricing.utils as utils

# global config
global_config = utils.load_global_config()

# config
config = utils.load_config()

# routes
router = APIRouter(prefix='/pricing')

@router.get('/get-checkout', response_model=schemas.GetCheckoutRM)
async def get_checkout(subtotal: float):
    service_fees_ht = math.ceil(subtotal * config['commission_coeff'] / 2)
    service_fees_taxes = math.ceil(service_fees_ht * config['TVA_coeff_HT'] * 100) / 100
    total = subtotal + service_fees_ht + service_fees_taxes

    return schemas.GetCheckoutRM(
        subtotal=subtotal,
        service_fees_ht=service_fees_ht,
        service_fees_taxes=service_fees_taxes,
        total=total
    )