import yaml
import stripe

import routers.payments.schemas as schemas

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

def calculate_income(subtotal_ht: int, TVA_cover_coeff_HT: float) -> int:
    return round(subtotal_ht * (1 + TVA_cover_coeff_HT), 2)

def calculate_advance(value: int, advance_coeff: int) -> float:
    return round(value * advance_coeff / 100, 2)

def calculate_balance(value: int, advance_coeff: int) -> float:
    return round(value - calculate_advance(value, advance_coeff), 2)

def get_cover_payment_details(
        subtotal_ht: int,
        fees_coeff: float,
        fees_offset: float
    ) -> schemas.CoverPaymentDetails:
    fees_ht = round(subtotal_ht * fees_coeff + fees_offset, 2)

    return schemas.CoverPaymentDetails(
        subtotal_ht=subtotal_ht,
        fees_ht=fees_ht
    )

def calculate_checkout(subtotal_ht: int, fees_ht: float, TVA_coeff_HT: float, TVA_cover_coeff_HT: float) -> schemas.PriceWithFees:
    subtotal = round(subtotal_ht * (1 + TVA_cover_coeff_HT), 2)
    service_fees = round(fees_ht * (1 + TVA_coeff_HT), 2)
    total = round(subtotal + service_fees, 2)

    return schemas.PriceWithFees(
        subtotal=subtotal,
        service_fees=service_fees,
        total=total
    )

def calculate_corresponding_subtotal(
        required_price: float,
        fees_coeff: float,
        fees_offset: float,
        TVA_coeff_HT: float,
        TVA_cover_coeff_HT: float
    ) -> float:
    n = required_price - fees_offset * (1 + TVA_coeff_HT)
    d = 1 + TVA_cover_coeff_HT + fees_coeff * (1 + TVA_coeff_HT)
    return n/d
