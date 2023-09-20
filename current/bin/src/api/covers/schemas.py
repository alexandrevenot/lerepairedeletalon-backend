from bson.objectid import ObjectId

from pydantic import BaseModel, validator
from fastapi import HTTPException

import src.api.stallions.utils as stallions_utils

stallions_config = stallions_utils.load_config()

class CoverQuery(BaseModel):
    seller_id: str
    stallion_nsire: str
    mare_nsire: str
    mare_name: str
    mare_breed: str
    message: str
    cover_type: str
    offered_cover_place: str = ""

    @validator('seller_id')
    def seller_id_validator(cls, v):
        try:
            return ObjectId(v)
        except Exception as exc:
            raise HTTPException(status_code=422, detail="seller_id is not readable") from exc
    
    @validator('cover_type')
    def cover_type_validator(cls, v):
        if v not in stallions_config["cover_types"]:
            raise HTTPException(status_code=422, detail="cover type not allowed")
        return v

class StepForwardCoverQuery(BaseModel):
    cover_id: str

    @validator('cover_id')
    def cover_id_validator(cls, v):
        try:
            return ObjectId(v)
        except Exception as exc:
            raise HTTPException(status_code=422, detail="cover_id is not readable") from exc

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
    mare_name: str
    mare_breed: str
    mare_nsire: str
    contact_name: str
    contact_phone_number: str
    contact_email: str
    cover_type: str
    cover_place: str
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
        except Exception as exc:
            raise HTTPException(status_code=422, detail="cover_id is not readable") from exc

class StepForwardSignatureQuery(BaseModel):
    contract_id: str

class StepForwardPaymentQuery(BaseModel):
    cover_id: str

    @validator('cover_id')
    def cover_id_validator(cls, v):
        try:
            return ObjectId(v)
        except Exception as exc:
            raise HTTPException(status_code=422, detail="cover_id is not readable") from exc