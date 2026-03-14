from typing import Any, Annotated

from pydantic import BaseModel, field_validator, Field
from fastapi import HTTPException

from ..stallions import schemas as stallions_schemas

from app.config import settings

class CoverQuery(BaseModel):
    seller_id: str
    stallion_id: str
    mare_nsire: str
    mare_name: str
    mare_breed: str
    mare_pregnancy_history: str
    message: str
    cover_type: str

    @field_validator('cover_type')
    @classmethod
    def cover_type_validator(cls, v):
        if v not in settings.cover_types:
            raise HTTPException(status_code=422, detail="cover type not allowed")
        return v

class ManuallyStepForwardCoverQuery(BaseModel):
    next_status: str

    @field_validator('next_status')
    @classmethod
    def next_status_validator(cls, v):
        if v not in settings.cover_status:
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
    stallion_color: str
    stallion_birthdate: str
    stallion_height: int
    stallion_offspring: str
    stallion_performance: str
    stallion_pedigree: list[str]
    stallion_pedigree_po: str
    stallion_std_negative_tests: stallions_schemas.StallionSTDSpecs
    stallion_vaccines: list[str] = []
    stallion_production_breeds: list[str]
    mare_name: str
    mare_breed: str
    mare_nsire: str
    mare_pregnancy_history: str
    contact_id: str
    contact_firstname: str
    contact_lastname: str
    contact_phone_number: str
    contact_email: str
    cover_type: str
    cover_specs: Any
    arrival_date: str
    status: str
    price: float
    base_price: int
    buyer_message: str
    timestamps: list[dict]
    notes: str
    reviewed_by_buyer: bool
    reviewed_by_seller: bool
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
    new_subtotal: Annotated[int, Field(
        strict=True,
        ge=settings.cover_minimum_price,
        default=None
    )]
