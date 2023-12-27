import yaml
import math
import app.pricing.schemas as schemas

def load_global_config() -> dict:
    with open('/lerepairedeletalon/server/current/etc/config.yaml', 'r') as f:
        return yaml.load(f, Loader=yaml.FullLoader)

def load_config() -> dict:
    with open('/lerepairedeletalon/server/current/etc/pricing/config.yaml', 'r') as f:
        return yaml.load(f, Loader=yaml.FullLoader)

def calculate_fees_ht(subtotal_ht: int, fees_coeff: float, fees_offset: float) -> float:
    return subtotal_ht * fees_coeff + fees_offset

def calculate_checkout(subtotal_ht: int, buyer_fees_ht: float, TVA_coeff_HT: float, TVA_cover_coeff_HT: float) -> schemas.PriceWithFees:
    subtotal = math.ceil(subtotal_ht * (1 + TVA_cover_coeff_HT))
    service_fees = math.ceil(buyer_fees_ht * (1 + TVA_coeff_HT))
    total = subtotal + service_fees

    return schemas.PriceWithFees(
        subtotal=subtotal,
        service_fees=service_fees,
        total=total
    )

def calculate_income(subtotal_ht: int, seller_fees_ht: float, TVA_coeff_HT: float, TVA_cover_coeff_HT: float) -> schemas.PriceWithFees:
    subtotal = math.ceil(subtotal_ht * (1 + TVA_cover_coeff_HT))
    service_fees = math.ceil(seller_fees_ht * (1 + TVA_coeff_HT))
    total = subtotal - service_fees

    return schemas.PriceWithFees(
        subtotal=subtotal,
        service_fees=service_fees,
        total=total
    )

def calculate_advance(value: int, advance_coeff: int, should_return_round_number: bool) -> int | float:
    return_value = value * advance_coeff / 100
    return math.ceil(return_value) if should_return_round_number else return_value

def calculate_balance(value: int, advance_coeff: int, should_return_round_number: bool) -> int | float:
    return_value = value * (100 - advance_coeff) / 100
    return math.floor(return_value) if should_return_round_number else return_value

def calculate_corresponding_subtotal(
        required_price: float,
        buyer_fees_coeff: float,
        buyer_fees_offset: float,
        TVA_coeff_HT: float,
        TVA_cover_coeff_HT: float,
        result_type: str
    ) -> float:
    n = required_price - buyer_fees_offset * (1 + TVA_coeff_HT)
    if result_type == "max":
        n -= 2
    d = 1 + TVA_cover_coeff_HT + buyer_fees_coeff * (1 + TVA_coeff_HT)
    return n/d

def get_cover_payment_details(
        subtotal_ht: int,
        buyer_fees_coeff: float,
        buyer_fees_offset: float,
        seller_fees_coeff: float,
        seller_fees_offset: float,
    ) -> schemas.CoverPaymentDetails:
    buyer_fees_ht = calculate_fees_ht(subtotal_ht, buyer_fees_coeff, buyer_fees_offset)
    seller_fees_ht = calculate_fees_ht(subtotal_ht, seller_fees_coeff, seller_fees_offset)

    return schemas.CoverPaymentDetails(
        subtotal_ht=subtotal_ht,
        buyer_fees_ht=buyer_fees_ht,
        seller_fees_ht=seller_fees_ht
    )
