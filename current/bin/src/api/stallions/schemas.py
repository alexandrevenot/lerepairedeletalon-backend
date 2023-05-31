from pydantic import BaseModel, validator
from fastapi import HTTPException

class SearchQuery(BaseModel):
    nb: int
    num_page: int

    @validator('nb')
    def num_validator(cls, v):
        if v < 0:
            raise HTTPException(status_code=422, detail="nb can't be < 0")
        return v

    @validator('num_page')
    def offset_validator(cls, v):
        if v < 0:
            raise HTTPException(status_code=422, detail="num_page can't be < 0")
        return v

class MosaicProfileInfo(BaseModel):
    id: str
    name: str
    location: str
    price: int

class SearchRM(BaseModel):
    content: list[MosaicProfileInfo]