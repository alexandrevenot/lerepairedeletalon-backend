from app.routers.geoloc.utils import find_city_not_normalized, normalize, find_dep_and_region

def test(geoloc_client):
    result = find_city_not_normalized('abancourt')
    assert len(result) == 2
    assert result[0]["lat"] == 50.2347
    assert result[0]["lng"] == 3.2127
    assert result[1]["lat"] == 49.6961
    assert result[1]["lng"] == 1.7651

    result = find_city_not_normalized('toulouse')
    assert len(result) == 2
    assert result[0]["lat"] == 43.6043
    assert result[0]["lng"] == 1.4437
    assert result[0]["postal_code"] == "31000"
    assert result[1]["lat"] == 46.8222
    assert result[1]["lng"] == 5.5868
    assert result[1]["postal_code"] == "39230"

    result = find_city_not_normalized('saunieres')
    assert len(result) == 1
    assert result[0]["lat"] == 46.9015
    assert result[0]["lng"] == 5.0796
    assert result[0]["postal_code"] == "71350"

    result = find_city_not_normalized('gormekzjlnbgjrekyuhbx')
    assert len(result) == 0

    result = normalize("This-Is-an-Étrange'Name")
    assert result == "thisisanetrangename"

    response = geoloc_client.get('/geoloc/city?city=Toulouse')
    assert response.status_code == 200
    result = response.json()["content"]
    assert len(result) == 2
    assert result[0]["lat"] == 43.6043
    assert result[0]["lng"] == 1.4437
    assert result[0]["postal_code"] == "31000"
    assert result[1]["lat"] == 46.8222
    assert result[1]["lng"] == 5.5868
    assert result[1]["postal_code"] == "39230"

    response = geoloc_client.get('/geoloc/city?city=abbevilleLaRiviere')
    assert response.status_code == 200
    result = response.json()["content"]
    assert len(result) == 1
    assert result[0]["lat"] == 48.3468
    assert result[0]["lng"] == 2.1659
    assert result[0]["postal_code"] == "91150"
    assert result[0]["city"] == "Abbéville-la-Rivière"

    result = find_dep_and_region("83")
    assert result["dep_name"] == "Var"
    assert result["reg_name"] == "Provence-Alpes-Côte d'Azur"