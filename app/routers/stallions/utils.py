from datetime import datetime, date
from io import BytesIO

import yaml
from dateutil.relativedelta import relativedelta
from PIL import Image

import routers.payments.utils as payments_utils

payments_config = payments_utils.load_config()

def load_global_config() -> dict:
    with open('etc/config.yaml', 'r', encoding="utf-8") as f:
        return yaml.load(f, Loader=yaml.FullLoader)

def load_config() -> dict:
    with open('etc/stallions/config.yaml', 'r', encoding="utf-8") as f:
        return yaml.load(f, Loader=yaml.FullLoader)

config = load_config()

def get_displayed_price(document: dict, min_price: float, max_price: float, cover_types: list[str]) -> float:
    count = 0
    if min_price is not None:
        count += 1
    if max_price is not None:
        count += 1

    if count == 0:
        value = min(value["price"] for key, value in document["cover_specs"].items() if key in cover_types)
    elif count == 1:
        if min_price is not None:
            value = min(value["price"] for key, value in document["cover_specs"].items() if value["price"] >= min_price and key in cover_types)
        else:
            value = min(value["price"] for key, value in document["cover_specs"].items() if value["price"] <= max_price and key in cover_types)
    else:
        value = min(value["price"] for key, value in document["cover_specs"].items() if value["price"] >= min_price and value["price"] <= max_price and key in cover_types)

    return payments_utils.calculate_checkout(value, payments_config['fees_coeff']).total

def calculate_age(birthdate: datetime) -> int:
    today = date.today()
    age = relativedelta(today, birthdate)
    return age.years

def get_thumbnail_photo_data(data: bytes, content_type: str, wished_new_width: int):
    image = Image.open(BytesIO(data))
    width, height = image.size
    new_width = min(width, wished_new_width)
    lowering_factor = new_width / width
    image_thumbnail = image.resize((int(new_width), int(lowering_factor*height)), Image.LANCZOS)
    new_data = BytesIO()
    image_format = content_type.split('/')[1].upper()
    if image_format == "JPG":
        image_format = "JPEG"
    image_thumbnail.save(new_data, format=image_format)
    new_data.seek(0)
    return new_data, image_format.lower()
