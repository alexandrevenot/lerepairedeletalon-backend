from typing import Any

from pydantic import BaseModel, field_validator
from fastapi import HTTPException

import src.api.stallions.utils as stallions_utils
import src.api.stallions.schemas as stallions_schemas
import src.api.covers.utils as utils

config = utils.load_config()

stallions_config = stallions_utils.load_config()

class CoverQuery(BaseModel):
    seller_id: str
    stallion_nsire: str
    mare_nsire: str
    mare_name: str
    mare_breed: str
    message: str
    cover_type: str
    provided_cover_place: str
    
    @field_validator('cover_type')
    @classmethod
    def cover_type_validator(cls, v):
        if v not in stallions_config["cover_types"]:
            raise HTTPException(status_code=422, detail="cover type not allowed")
        return v

    @field_validator('provided_cover_place')
    @classmethod
    def provided_cover_place_validator(cls, v, info):
        if v == "" and info.data["cover_type"] not in stallions_config["onsite_cover_types"]:
            raise HTTPException(status_code=422, detail="a cover place has to be provided")
        if v != "" and info.data["cover_type"] not in stallions_config["remote_cover_types"]:
            raise HTTPException(status_code=422, detail="cannot provide cover place on this cover type")
        return v

class ManuallyStepForwardCoverQuery(BaseModel):
    next_status: str

    @field_validator('next_status')
    @classmethod
    def next_status_validator(cls, v):
        if v not in config["status"]:
            raise HTTPException(status_code=422, detail="status not allowed")
        return v

class GetCoverGroupItem(BaseModel):
    id: str
    stallion_name: str
    mare_name: str
    status: str
    price: float

class GetCoverGroupRM(BaseModel):
    items: list[GetCoverGroupItem]

class GetCoverInformation(BaseModel):
    stallion_name: str
    stallion_breed: str
    stallion_nsire: str
    stallion_production_breeds: list[str]
    stallion_vaccines: list[str] = []
    stallion_std_negative_tests: stallions_schemas.StallionSTDSpecs
    mare_name: str
    mare_breed: str
    mare_nsire: str
    contact_name: str
    contact_phone_number: str
    contact_email: str
    cover_type: str
    cover_specs: Any
    provided_cover_place: str
    arrival_date: str
    status: str
    price: int
    base_price: int
    buyer_message: str
    timestamps: list[dict]
    notes: str
    pov: str

    @field_validator('stallion_vaccines')
    @classmethod
    def stallion_vaccines_validator(cls, value):
        return stallions_schemas.check_vaccines(value)

class UpdateNotesQuery(BaseModel):
    notes: str

class StepForwardSignatureQuery(BaseModel):
    contract_id: str

class EditCoverQuery(BaseModel):
    arrival_date: str = ""
    new_subtotal: int = None
