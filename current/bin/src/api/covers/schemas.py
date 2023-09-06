from bson.objectid import ObjectId

from pydantic import BaseModel, validator
from fastapi import HTTPException

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
    cover_place_is_offered: bool
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