from datetime import datetime

from fastapi import HTTPException
from pydantic import BaseModel, field_validator, model_validator, PositiveFloat, PositiveInt, NonNegativeInt, conint

import src.api.stallions.utils as utils

config = utils.load_config()

class MosaicProfileInfo(BaseModel):
    id: str
    name: str
    breed: str
    height: float
    cover_types: list[str]
    city: str
    dep_name: str
    reg_name: str
    price: int
    photo_id: str

    @field_validator('cover_types')
    @classmethod
    def cover_types_validator(cls, value):
        for cover_type in value:
            if cover_type not in config["cover_types"]:
                raise HTTPException(status_code=500, detail="failed to search stallions")
        return value

class SearchRM(BaseModel):
    content: list[MosaicProfileInfo]

class DashboardStallionBox(BaseModel):
    id: str
    name: str
    breed: str
    photo_id: str
    last_update_timestamp: str
    profile_status: str

    @field_validator('profile_status')
    @classmethod
    def profile_status_validator(cls, value):
        if value not in config["profile_statuses"]:
            raise HTTPException(status_code=500, detail="failed to get stallion boxes")
        return value

class GetMyStallionsRM(BaseModel):
    content: list[DashboardStallionBox]

class FinalStallionFields(BaseModel):
    name: str
    breed: str
    n_sire: str
    birthdate: str

def check_balance_payment_condition(value):
    if value not in config["balance_payment_conditions"]:
        raise HTTPException(status_code=422, detail="unallowed balance payment condition")
    return value

def check_hosting_specs(value):
    if not (value.private | value.collective | value.meadow):
        raise HTTPException(status_code=422, detail="no hosting specified")
    return value

def check_vaccines(value):
    for vaccine in value:
        if vaccine not in config["available_vaccines"]:
            raise HTTPException(status_code=422, detail="unallowed vaccines")
    return value

class SingularStallionSTDSpecs(BaseModel):
    test_date: str

    @field_validator('test_date')
    @classmethod
    def test_date_validator(cls, v):
        try:
            _ = datetime.strptime(v, "%d/%m/%Y")
            return v
        except Exception as exc:
            raise HTTPException(status_code=422, detail="incorrect test_date date format") from exc

class StallionSTDSpecs(BaseModel):
    metrite: SingularStallionSTDSpecs = None
    arterite: SingularStallionSTDSpecs = None
    anemie: SingularStallionSTDSpecs = None

class SingularMareSTDSpecs(BaseModel):
    test_oldness: conint(ge=config["minimum_std_test_oldness"], le=config["maximum_std_test_oldness"])

class MareSTDSpecs(BaseModel):
    metrite: SingularMareSTDSpecs = None
    arterite: SingularMareSTDSpecs = None
    anemie: SingularMareSTDSpecs = None

class SingularHostingSpecs(BaseModel):
    price: NonNegativeInt

class HostingSpecs(BaseModel):
    private: SingularHostingSpecs = None
    collective: SingularHostingSpecs = None
    meadow: SingularHostingSpecs = None

    @model_validator(mode='after')
    def check_that_atleast_one_hosting_type_is_provided(self):
        if self.private is None and self.collective is None and self.meadow is None:
            raise HTTPException(status_code=422, detail="atleast one hosting type has to be offered")
        return self

class LIBandHANDSpecs(BaseModel):
    price: int
    balance_payment_condition: str
    advance_percentage: conint(ge=config["advance_min_percentage_value"], le=config["advance_max_percentage_value"])
    cover_place: str
    maximum_nb_of_attempts: PositiveInt
    hosting_specs: HostingSpecs
    demanded_std_negative_tests: MareSTDSpecs
    demanded_vaccines: list[str] = []

    @field_validator('balance_payment_condition')
    @classmethod
    def balance_payment_condition_validator(cls, value):
        return check_balance_payment_condition(value)

    @field_validator('demanded_vaccines')
    @classmethod
    def demanded_vaccines_validator(cls, value):
        return check_vaccines(value)

class IAISpecs(BaseModel):
    price: int
    balance_payment_condition: str
    advance_percentage: conint(ge=config["advance_min_percentage_value"], le=config["advance_max_percentage_value"])
    cover_place: str
    maximum_nb_of_attempts: PositiveInt
    hosting_specs: HostingSpecs

    @field_validator('balance_payment_condition')
    @classmethod
    def balance_payment_condition_validator(cls, value):
        return check_balance_payment_condition(value)

class IARTSpecs(BaseModel):
    price: int
    balance_payment_condition: str
    advance_percentage: conint(ge=config["advance_min_percentage_value"], le=config["advance_max_percentage_value"])
    nb_provided_straws: PositiveInt

class IACSpecs(BaseModel):
    price: int
    balance_payment_condition: str
    advance_percentage: conint(ge=config["advance_min_percentage_value"], le=config["advance_max_percentage_value"])
    nb_provided_straws: PositiveInt
    left_straws_owner: str

    @field_validator('left_straws_owner')
    @classmethod
    def left_straws_owner_validator(cls, value):
        if value not in ["seller", "buyer"]:
            raise HTTPException(status_code=422, detail="left_straws_owner has to be either 'seller' or 'buyer'")
        return value

class CoverSpecs(BaseModel):
    lib: LIBandHANDSpecs = None
    hand: LIBandHANDSpecs = None
    iai: IAISpecs = None
    iart: IARTSpecs = None
    iac: IACSpecs = None

    @model_validator(mode='after')
    def check_that_atleast_one_cover_type_is_provided(self):
        if not (self.lib or self.hand or self.iai or self.iart or self.iac):
            raise HTTPException(status_code=422, detail="atleast one cover type has to be offered")

        return self

class EditableStallionFields(BaseModel):
    main_desc: str
    color: str
    height: PositiveFloat
    lat: float
    lng: float
    city: str
    postal_code: str
    production_breeds: list[str]
    cover_specs: CoverSpecs
    pedigree: list[str] = None
    pedigree_po: str = ""
    cover_additional_info: str = ""
    performance: str = ""
    stallion_additional_info: str = ""
    stallion_std_negative_tests: StallionSTDSpecs
    stallion_vaccines: list[str] = []
    offspring: str = ""
    crossbreeding_advice: str = ""

    @field_validator('production_breeds')
    @classmethod
    def production_breeds_validator(cls, value):
        if sorted(value) != sorted(list(set(value))):
            raise HTTPException(status_code=422, detail='atleast 1 production breed is duplicated')
        if len(value) == 0:
            raise HTTPException(status_code=422, detail='production breeds cannot be empty')
        return value

    @field_validator('pedigree')
    @classmethod
    def pedigree_validator(cls, value):
        if value is None:
            value = []

        if len(value) > 14:
            raise HTTPException(status_code=422, detail="too many items in pedigree")

        if len(value) <= 14:
            value = value + ["" for _ in range(14 - len(value))]

        return value

    @field_validator('stallion_vaccines')
    @classmethod
    def stallion_vaccines_validator(cls, value):
        return check_vaccines(value)

class StallionProfileInformation(BaseModel):
    owner: str
    name: str
    breed: str
    n_sire: str
    age: int
    main_desc: str
    color: str
    height: float
    city: str
    dep_name: str
    reg_name: str
    production_breeds: list[str]
    cover_specs: CoverSpecs
    pedigree: list[str]
    pedigree_po: str
    cover_additional_info: str
    performance: str
    stallion_additional_info: str
    stallion_std_negative_tests: StallionSTDSpecs
    stallion_vaccines: list[str]
    offspring: str
    crossbreeding_advice: str
    photos: list[str]

class StallionCompleteProfileInformation(BaseModel):
    name: str
    breed: str
    n_sire: str
    photos: list[str]
    main_desc: str
    color: str
    height: float
    birthdate: str
    city: str
    postal_code: str
    lat: float
    lng: float
    pedigree: list[str]
    crossbreeding_advice: str
    stallion_std_negative_tests: StallionSTDSpecs
    stallion_vaccines: list[str]
    offspring: str
    performance: str
    pedigree_po: str
    stallion_additional_info: str
    production_breeds: list[str]
    cover_specs: CoverSpecs
    cover_additional_info: str
