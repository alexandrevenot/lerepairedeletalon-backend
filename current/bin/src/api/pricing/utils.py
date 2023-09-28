import yaml
import math
import src.api.pricing.schemas as schemas

def load_global_config() -> dict:
    with open('/lerepairedeletalon/server/current/etc/config.yaml', 'r') as f:
        return yaml.load(f, Loader=yaml.FullLoader)

def load_config() -> dict:
    with open('/lerepairedeletalon/server/current/etc/pricing/config.yaml', 'r') as f:
        return yaml.load(f, Loader=yaml.FullLoader)

def calculate_fees_ht(subtotal: int, fees_coeff: float, fees_offset: float) -> float:
    return subtotal * fees_coeff + fees_offset

def calculate_checkout(subtotal: int, buyer_fees_ht: float, TVA_coeff_HT: float) -> schemas.PriceWithFees:
    service_fees = math.ceil((buyer_fees_ht) * (1 + TVA_coeff_HT))
    total = subtotal + service_fees

    return schemas.PriceWithFees(
        subtotal=subtotal,
        service_fees=service_fees,
        total=total
    )

def calculate_income(subtotal: int, seller_fees_ht: float, TVA_coeff_HT: float) -> schemas.PriceWithFees:
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

def calculate_corresponding_subtotal(required_price: float, buyer_fees_coeff: float, buyer_fees_offset: float, TVA_coeff_HT: float) -> float:
    n = (required_price - buyer_fees_offset * (1 + TVA_coeff_HT))
    d = 1 + buyer_fees_coeff * (1 + TVA_coeff_HT)
    return n/d

def get_cover_payment_details(subtotal: int, buyer_fees_coeff: float, buyer_fees_offset: float, seller_fees_coeff: float, seller_fees_offset: float, advance_coeff: int) -> schemas.CoverPaymentDetails:
    buyer_fees_ht = calculate_fees_ht(subtotal, buyer_fees_coeff, buyer_fees_offset)
    seller_fees_ht = calculate_fees_ht(subtotal, seller_fees_coeff, seller_fees_offset)

    return schemas.CoverPaymentDetails(
        advance_subtotal=calculate_advance(subtotal, advance_coeff, True),
        advance_buyer_fees_ht=calculate_advance(buyer_fees_ht, advance_coeff, False),
        advance_seller_fees_ht=calculate_advance(seller_fees_ht, advance_coeff, False),
        balance_subtotal=calculate_balance(subtotal, advance_coeff, True),
        balance_buyer_fees_ht=calculate_balance(buyer_fees_ht, advance_coeff, False),
        balance_seller_fees_ht=calculate_balance(seller_fees_ht, advance_coeff, False)
    )