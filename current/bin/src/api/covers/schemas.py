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
    status: str
    message: str

    @validator('status')
    def status_validator(cls, v):
        possible_values = config["status"]
        if v not in possible_values:
            raise HTTPException(status_code=422, detail=f"status has to be in {possible_values}")
        return v

    @validator('seller_id')
    def seller_id_validator(cls, v):
        try:
            return ObjectId(v)
        except:
            raise HTTPException(status_code=422, detail=f"seller_id is not readable")

class StepForwardCoverQuery(BaseModel):
    cover_id: str

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

class GetCoverGroupRM(BaseModel):
    items: list[GetCoverGroupItem]