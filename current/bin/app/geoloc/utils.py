import pandas as pd
import bisect
import unicodedata

NORMALIZED_DF = pd.read_csv(
    '/lerepairedeletalon/server/current/etc/geoloc/geoloc_normalized.csv',
    sep=",",
    dtype={"city": str}
)
COMPLETE_DF = pd.read_csv(
    '/lerepairedeletalon/server/current/etc/geoloc/geoloc_not_normalized.csv',
    sep=",",
    dtype={
        "postal_code": str,
        "city": str,
        "lat": float,
        "lng": float
    }
)
FRENCH_DEPS_DF = pd.read_csv(
    '/lerepairedeletalon/server/current/etc/geoloc/french_deps.csv',
    sep=",",
    dtype={
        "code": str,
        "dep": str,
        "reg": str
    }
)

def find_city_not_normalized(city: str) -> list[pd.core.series.Series]:
    characters_nb = len(city)
    unfiltered_cities = []
    index = bisect.bisect_left(NORMALIZED_DF.loc[:,'city'], city, key=lambda x: x[:characters_nb])

    if not NORMALIZED_DF.loc[index, 'city'][:characters_nb] == city:
        return []

    unfiltered_cities.append(COMPLETE_DF.loc[index,:])
    index += 1

    while NORMALIZED_DF.loc[index, 'city'][:characters_nb] == city:
        unfiltered_cities.append(COMPLETE_DF.loc[index,:])
        index += 1

    cities_with_common_coordinates = {}
    for found_city in unfiltered_cities:
        key = f"{found_city['lat']} {found_city['lng']}"
        if key in cities_with_common_coordinates:
            cities_with_common_coordinates[key].append(found_city)
        else:
            cities_with_common_coordinates[key] = [found_city]

    cities_to_return = []
    for cities in cities_with_common_coordinates.values():
        cities_to_return.append(cities[0].to_dict())

    return cities_to_return[:5]

def normalize(city_input: str) -> str:
    res = city_input.replace("-", "")
    res = unicodedata.normalize('NFKD', res).encode('ASCII', 'ignore').decode('utf-8')
    res = res.lower()
    res = res.replace(" ", "")
    return res.replace("'", "")

def find_city(city_input) -> list[pd.core.series.Series] :
    return find_city_not_normalized(normalize(city_input))

def find_dep_and_region(code: str) -> dict:
    index = bisect.bisect_left(FRENCH_DEPS_DF.loc[:,'code'], code)

    if not FRENCH_DEPS_DF.loc[index, 'code'] == code:
        return False

    return {
        "dep_name": FRENCH_DEPS_DF.loc[index,'dep'],
        "reg_name": FRENCH_DEPS_DF.loc[index,'reg']
    }
