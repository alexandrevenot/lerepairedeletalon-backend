from pydantic import BaseModel

class MosaicProfileInfo(BaseModel):
    id: str
    name: str
    breed: str
    city: str
    dep_name: str
    reg_name: str
    price: int
    photo_id: str

class SearchRM(BaseModel):
    content: list[MosaicProfileInfo]

class DashboardStallionBox(BaseModel):
    id: str
    name: str
    breed: str
    photoId: str
    searchable: bool

class GetMyStallionsRM(BaseModel):
    content: list[DashboardStallionBox]

class CoverSpecs(BaseModel):
    cover_type: str
    cover_place: str
    price: int
    advance_percentage: int
    balance_payment_condition: str
    left_straws_owner: str

class Location(BaseModel):
    type: str
    coordinates: list[float]

class StallionProfileInformation(BaseModel):
    owner: str
    name: str
    breed: str
    n_sire: str
    photos: list[str]
    main_desc: str
    color: str
    age: int
    height: float
    offspring: str
    performance: str
    pedigree: list[str]
    pedigree_po: str
    stallion_additional_info: str
    prices: list[CoverSpecs]
    production_breeds: list[str]
    cover_additional_info: str
    location: Location
    city: str
    postal_code: str
    dep_name: str
    reg_name: str

class GetStallionProfileInformationRM(BaseModel):
    stallionProfile: StallionProfileInformation