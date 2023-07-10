import traceback
import re

from fastapi import APIRouter, HTTPException

import src.api.geoloc.schemas as schemas
import src.api.geoloc.utils as utils

# routes
router = APIRouter(prefix='/geoloc')

@router.get('/get-city', response_model=schemas.GetCitiesRM)
async def get_city(user_input: str):
    # parse user_input
    user_input = user_input.replace("(", "")
    user_input = user_input.replace(")", "")

    matches = re.findall(r'\d+', user_input) # get chains of numeric characters
    input_includes_a_postal_code = False
    requested_postal_code = None
    if len(matches) == 1:
        requested_postal_code = matches[0]
        input_includes_a_postal_code = True
    elif len(matches) > 1:
        raise HTTPException(status_code=404, detail=f"city not found")

    # match user_input
    try:
        if input_includes_a_postal_code:
            user_input = user_input.replace(requested_postal_code, "")

        result = utils.find_city(user_input)
    except:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="failed to browse postal codes db")

    if result:
        cities_to_return = []
        for city in result:
            if input_includes_a_postal_code:
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
            raise HTTPException(status_code=422, detail={
                "message": "too many results",
                "value": len(cities_to_return)
            })
        else:
            return schemas.GetCitiesRM(content=cities_to_return)
    else:
        raise HTTPException(status_code=404, detail=f"city not found")