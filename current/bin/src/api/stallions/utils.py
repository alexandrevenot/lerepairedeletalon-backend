from datetime import datetime, date
from io import BytesIO

import yaml
from dateutil.relativedelta import relativedelta
from PIL import Image

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

def get_thumbnail_photo_data(data: bytes, content_type: str, wished_new_width: int) -> bytes:
    image = Image.open(BytesIO(data))
    width, height = image.size
    new_width = min(width, wished_new_width)
    lowering_factor = new_width / width
    image_thumbnail = image.resize((int(new_width), int(lowering_factor*height)), Image.LANCZOS)
    new_data = BytesIO()
    image_thumbnail.save(new_data, format=content_type.split('/')[1].upper())
    return new_data.getvalue()
