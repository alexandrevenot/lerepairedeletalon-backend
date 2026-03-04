import yaml

import stripe

from . import schemas

def load_config() -> dict:
    with open('etc/payments/config.yaml', 'r', encoding="utf-8") as f:
        return yaml.load(f, Loader=yaml.FullLoader)

def load_global_config() -> dict:
    with open('etc/config.yaml', 'r', encoding="utf-8") as f:
        return yaml.load(f, Loader=yaml.FullLoader)

config = load_config()

stripe.api_key = config["api_key"]

def delete_stripe_account(account_id):
    stripe.Account.delete(account_id)

def calculate_advance(value: int, advance_coeff: int) -> float:
    return round(value * advance_coeff / 100, 2)

def calculate_balance(value: int, advance_coeff: int) -> float:
    return round(value - calculate_advance(value, advance_coeff), 2)

def calculate_checkout(subtotal: float, fees_coeff: float) -> schemas.PriceWithFees:
    fees = round(subtotal * fees_coeff, 2)
    return schemas.PriceWithFees(
        subtotal=subtotal,
        fees=fees,
        total=subtotal + fees
    )

def calculate_corresponding_subtotal(required_price: float, fees_coeff: float) -> float:
    return required_price/(1 + fees_coeff)
