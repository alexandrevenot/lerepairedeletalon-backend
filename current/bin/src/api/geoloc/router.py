import traceback

from fastapi import APIRouter, HTTPException

import src.api.geoloc.schemas as schemas
import src.api.geoloc.utils as utils

# routes
router = APIRouter(prefix='/geoloc')

@router.get('/get-city', response_model=schemas.GetCitiesRM)
async def get_city(city: str, requested_postal_code: str = None):

    request_includes_a_postal_code = requested_postal_code is not None

    # match user_input
    try:
        result = utils.find_city(city)
    except:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to browse postal codes db")

    if not result:
        raise HTTPException(status_code=404, detail=f"city not found")

    cities_to_return = []
    for city in result:
        if request_includes_a_postal_code:
            postal_code=str(city['postal_code'])
            if requested_postal_code in postal_code:
                cities_to_return.append(schemas.CityRM(
                    city_name=city["city"],
                    postal_code=postal_code,
                    lat=city['lat'],
                    lng=city['long']
                ))
        else:
            cities_to_return.append(schemas.CityRM(
            city_name=city["city"],
            postal_code=str(city['postal_code']),
            lat=city['lat'],
            lng=city['long']
            ))

    if len(cities_to_return) == 0:
        raise HTTPException(status_code=404, detail=f"city not found")
    elif len(cities_to_return) > 10:
        index_min = min(range(len([elt.postal_code for elt in cities_to_return])), key=[elt.postal_code for elt in cities_to_return].__getitem__)
        cities_to_return = [cities_to_return[index_min]]
    return schemas.GetCitiesRM(content=cities_to_return)