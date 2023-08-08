from bson.objectid import ObjectId

from pydantic import BaseModel, validator
from fastapi import HTTPException

class SignContract(BaseModel):
    cover_id: str

    @validator('cover_id')
    def cover_id_validator(cls, v):
        try:
            return ObjectId(v)
        except:
            raise HTTPException(status_code=422, detail=f"cover_id is not readable")

class GetSignPageUrl(BaseModel):
    url: str