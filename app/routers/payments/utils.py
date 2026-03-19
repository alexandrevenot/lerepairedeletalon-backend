import stripe

from app.config import settings

from . import schemas

stripe.api_key = settings.stripe_api_key

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
