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

config = load_config()

def get_displayed_price(document: dict, min_price: float, max_price: float, cover_types: list[str]) -> float:
    count = 0
    if min_price is not None:
        count += 1
    if max_price is not None:
        count += 1

    if count == 0:
        value = min([value["price"] for key, value in document["cover_specs"].items() if key in cover_types])
    elif count == 1:
        if min_price is not None:
            value = min([value["price"] for key, value in document["cover_specs"].items() if value["price"] >= min_price and key in cover_types])
        else:
            value = min([value["price"] for key, value in document["cover_specs"].items() if value["price"] <= max_price and key in cover_types])
    else:
        value = min([value["price"] for key, value in document["cover_specs"].items() if value["price"] >= min_price and value["price"] <= max_price and key in cover_types])

    buyer_fees_ht = pricing_utils.calculate_fees_ht(value, pricing_config['buyer_fees_coeff'], pricing_config['buyer_fees_offset'])
    return pricing_utils.calculate_checkout(value, buyer_fees_ht, pricing_config['TVA_coeff_HT']).total

def calculate_age(birthdate: datetime) -> int:
    today = date.today()
    age = relativedelta(today, birthdate)
    return age.years