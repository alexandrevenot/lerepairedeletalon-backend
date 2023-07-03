from pydantic import BaseModel

class CityRM(BaseModel):
    city_name: str
    postal_code: str
    lat: float
    lng: float

class GetCitiesRM(BaseModel):
    content: list[CityRM]