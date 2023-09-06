import logging
import logging.handlers
import traceback

from fastapi import APIRouter, HTTPException

import src.api.geoloc.schemas as schemas
import src.api.geoloc.utils as utils

# logging
logger = logging.getLogger(__name__)
logger.setLevel(20)
handler = logging.handlers.RotatingFileHandler(
    f'/lerepairedeletalon/server/import/var/log/API/{__name__}.log',
    maxBytes=1024 * 1025 * 50,
    backupCount=2,
    mode='a'
    )
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.info('Logger initialized')

# routes
router = APIRouter(prefix='/geoloc')

@router.get('/city', response_model=schemas.GetCitiesRM)
async def get_city(city: str, requested_postal_code: str = None):

    request_includes_a_postal_code = requested_postal_code is not None

    # match user_input
    try:
        result = utils.find_city(city)
    except Exception as exc:
        logger.error(f'failed to read db: {traceback.format_exc()}')
        raise HTTPException(status_code=500, detail='failed to read db') from exc

    if not result:
        raise HTTPException(status_code=404, detail="city not found")

    cities_to_return = []

    if request_includes_a_postal_code:
        for city_name in result:
            postal_code=str(city_name['postal_code'])
            if requested_postal_code in postal_code:
                cities_to_return.append(schemas.CityRM(
                    city_name=city_name["city"],
                    postal_code=postal_code,
                    lat=city_name['lat'],
                    lng=city_name['long']
                ))
    else:
        for city_name in result:
            cities_to_return.append(schemas.CityRM(
            city_name=city_name["city"],
            postal_code=str(city_name['postal_code']),
            lat=city_name['lat'],
            lng=city_name['long']
            ))

    if len(cities_to_return) == 0:
        raise HTTPException(status_code=404, detail="city not found")
    elif len(cities_to_return) > 10:
        index_min = min(range(len([elt.postal_code for elt in cities_to_return])), key=[elt.postal_code for elt in cities_to_return].__getitem__)
        cities_to_return = [cities_to_return[index_min]]
    return schemas.GetCitiesRM(content=cities_to_return)