import pandas as pd
import bisect
import unicodedata

NORMALIZED_DF = pd.read_csv('/lerepairedeletalon/server/current/etc/geoloc/geoloc_normalized.csv', sep=",")
COMPLETE_DF = pd.read_csv('/lerepairedeletalon/server/current/etc/geoloc/geoloc_not_normalized.csv', sep=",")

def find_city_not_normalized(city) -> list:
    cities = []
    index = bisect.bisect_left(NORMALIZED_DF.loc[:,'city'], city)
    if index and NORMALIZED_DF.loc[index, 'city'] == city:
        cities.append(COMPLETE_DF.loc[index,:])
        index += 1

        while NORMALIZED_DF.loc[index, 'city'] == city:
            cities.append(COMPLETE_DF.loc[index,:])
            index += 1

        return cities
    else:
        return False

def normalize(city_input) -> str:
    res = city_input.replace("-", "")
    res = unicodedata.normalize('NFKD', res).encode('ASCII', 'ignore').decode('utf-8')
    res = res.lower()
    res = res.replace(" ", "")
    return res.replace("'", "")

def find_city(city_input) -> list[pd.core.series.Series] | bool :
    return find_city_not_normalized(normalize(city_input))

FRENCH_DEPS_DF = pd.read_csv('/lerepairedeletalon/server/current/etc/geoloc/french_deps.csv', sep=",")

def find_dep_and_region(code):
    index = bisect.bisect_left(FRENCH_DEPS_DF.loc[:,'code'], code)
    if index and FRENCH_DEPS_DF.loc[index, 'code'] == code:
        return {
            "dep_name": FRENCH_DEPS_DF.loc[index,'dep'],
            "reg_name": FRENCH_DEPS_DF.loc[index,'reg']
        }
    else:
        return False