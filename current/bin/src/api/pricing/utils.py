import yaml
import math
import src.api.pricing.schemas as schemas

def load_global_config() -> dict:
    with open('/lerepairedeletalon/server/current/etc/config.yaml', 'r') as f:
        return yaml.load(f, Loader=yaml.FullLoader)

def load_config() -> dict:
    with open('/lerepairedeletalon/server/current/etc/pricing/config.yaml', 'r') as f:
        return yaml.load(f, Loader=yaml.FullLoader)

def calculate_checkout(subtotal: float, buyer_fees: float, TVA_coeff_HT: float) -> schemas.Checkout:
    service_fees_ht = math.ceil(subtotal * buyer_fees)
    service_fees_taxes = math.ceil(service_fees_ht * TVA_coeff_HT * 100) / 100
    total = subtotal + service_fees_ht + service_fees_taxes

    return schemas.Checkout(
        subtotal=subtotal,
        service_fees_ht=service_fees_ht,
        service_fees_taxes=service_fees_taxes,
        total=total
    )

def calculate_income(subtotal: float, seller_fees: float) -> schemas.Income:
    return schemas.Income(income=math.floor(subtotal * (1-seller_fees)))