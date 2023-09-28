from datetime import datetime, date

import yaml
from dateutil.relativedelta import relativedelta

import src.api.pricing.utils as pricing_utils

pricing_config = pricing_utils.load_config()

def load_global_config() -> dict:
    with open('/lerepairedeletalon/server/current/etc/config.yaml', 'r') as f:
        return yaml.load(f, Loader=yaml.FullLoader)

def load_config() -> dict:
    with open('/lerepairedeletalon/server/current/etc/stallions/config.yaml', 'r') as f:
        return yaml.load(f, Loader=yaml.FullLoader)

def get_displayed_price(document: dict, min_price: float, max_price: float) -> float:
    count = 0
    if min_price is not None:
        count += 1
    if max_price is not None:
        count += 1

    if count == 0:
        value = min([elt["price"] for elt in document["prices"]])
    elif count == 1:
        if min_price is not None:
            value = min([elt["price"] for elt in document["prices"] if elt["price"] >= min_price])
        else:
            value = min([elt["price"] for elt in document["prices"] if elt["price"] <= max_price])
    else:
        value = min([elt["price"] for elt in document["prices"] if elt["price"] >= min_price and elt["price"] <= max_price])

    buyer_fees_ht = pricing_utils.calculate_fees_ht(value, pricing_config['buyer_fees_coeff'], pricing_config['buyer_fees_offset'])
    return pricing_utils.calculate_checkout(value, buyer_fees_ht, pricing_config['TVA_coeff_HT']).total

def calculate_age(birthdate: datetime) -> int:
    today = date.today()
    age = relativedelta(today, birthdate)
    return age.years