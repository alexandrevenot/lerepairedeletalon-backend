from bson.objectid import ObjectId

from pydantic import BaseModel, validator
from fastapi import HTTPException

import src.api.covers.utils as utils

# config
config = utils.load_config()

class CoverQuery(BaseModel):
    seller_id: str
    stallion_nsire: str
    mare_nsire: str
    mare_name: str
    mare_breed: str
    message: str
    cover_type: str
    status: str

    @validator('status')
    def status_validator(cls, v):
        first_value = config["status"][0]
        if v != first_value:
            raise HTTPException(status_code=422, detail=f"status has to be {first_value}")
        return v

    @validator('seller_id')
    def seller_id_validator(cls, v):
        try:
            return ObjectId(v)
        except:
            raise HTTPException(status_code=422, detail=f"seller_id is not readable")

class StepForwardCoverQuery(BaseModel):
    cover_id: str
    refuse: bool = False

    @validator('cover_id')
    def cover_id_validator(cls, v):
        try:
            return ObjectId(v)
        except:
            raise HTTPException(status_code=422, detail=f"cover_id is not readable")

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
    mare_name: str
    mare_breed: str
    mare_nsire: str
    contact_name: str
    contact_phone_number: str
    contact_email: str
    cover_type: str
    price: float
    buyer_message: str
    timestamps: dict
    notes: str
    status: str
    pov: str

class UpdateNotesQuery(BaseModel):
    cover_id: str
    notes: str

    @validator('cover_id')
    def cover_id_validator(cls, v):
        try:
            return ObjectId(v)
        except:
            raise HTTPException(status_code=422, detail=f"cover_id is not readable")