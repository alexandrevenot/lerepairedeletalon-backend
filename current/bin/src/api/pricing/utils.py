import yaml
import math
import src.api.pricing.schemas as schemas

def load_global_config() -> dict:
    with open('/lerepairedeletalon/server/current/etc/config.yaml', 'r') as f:
        return yaml.load(f, Loader=yaml.FullLoader)

def load_config() -> dict:
    with open('/lerepairedeletalon/server/current/etc/pricing/config.yaml', 'r') as f:
        return yaml.load(f, Loader=yaml.FullLoader)

def calculate_checkout(subtotal: int, buyer_fees: float, TVA_coeff_HT: float) -> schemas.PriceWithFees:
    service_fees = math.ceil(subtotal * buyer_fees * (1 + TVA_coeff_HT))
    total = subtotal + service_fees

    return schemas.PriceWithFees(
        subtotal=subtotal,
        service_fees=service_fees,
        total=total
    )

def calculate_income(subtotal: int, seller_fees: float, TVA_coeff_HT: float) -> schemas.PriceWithFees:
    service_fees = math.ceil(subtotal * seller_fees * (1 + TVA_coeff_HT))
    total = subtotal - service_fees

    return schemas.PriceWithFees(
        subtotal=subtotal,
        service_fees=service_fees,
        total=total
    )

def calculate_advance(subtotal: int, advance_coeff: float) -> int: 
    return math.ceil(subtotal * advance_coeff)

def calculate_balance(subtotal: int, advance_coeff: float) -> int:
    return math.floor(subtotal * (1 - advance_coeff))

def calculate_real_max_price(required_max_price: float, buyer_fees: float, TVA_coeff_HT: float) -> float:
    d = 1 + buyer_fees * (1 + TVA_coeff_HT)
    return required_max_price/d

def calculate_real_min_price(required_min_price: float, buyer_fees: float, TVA_coeff_HT: float) -> float:
    d = 1 + buyer_fees * (1 + TVA_coeff_HT)
    return (required_min_price - 1)/d