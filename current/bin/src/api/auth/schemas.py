import re

from fastapi import HTTPException
from pydantic import BaseModel, validator, root_validator

email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'

class RegisterQuery(BaseModel):
    firstname: str
    lastname: str
    email: str
    phone_number: str
    password: str

    @validator('email')
    def email_validator(cls, v):
        if re.match(email_pattern, v) is None:
            raise HTTPException(status_code=422, detail="bad email format")
        return v

class LoginQuery(BaseModel):
    email: str
    password: str

    @validator('email')
    def email_validator(cls, v):
        if re.match(email_pattern, v) is None:
            raise HTTPException(status_code=422, detail="bad email format")
        return v

class RefreshTokenQuery(BaseModel):
    token: str

    @validator('token')
    def token_validator(cls, v):
        fields = v.split(' ')
        if len(fields) != 2:
            raise HTTPException(status_code=422, detail="token not found in the request")
        
        return fields[1]

class UserInDB(BaseModel):
    firstname: str
    lastname: str
    email: str
    phone_number: str
    hashedpassword: str

class GetUserRM(BaseModel):
    firstname: str
    lastname: str

class GetProfileInformation(BaseModel):
    type: str
    gender: str
    postal_address: str
    birthdate: str
    birthplace: str
    citizenship: str
    company_name: str = None
    company_status: str = None
    capital: float = None
    head_office_address: str = None
    siret: str = None

class PutProfileInformationQuery(BaseModel):
    type: str
    company_name: str = None
    company_status: str = None
    capital: float = None
    head_office_address: str = None
    siret: str = None
    gender: str
    postal_address: str
    birthdate: str
    birthplace: str
    citizenship: str

    @root_validator()
    def validate_atts(cls, values):
        if values.get("type") == "company":
            for field in ["company_name", "company_status", "capital", "head_office_address", "siret"]:
                if values.get(field) is None:
                    raise HTTPException(status_code=422, detail="missing mandatory fields")
        
        elif values.get("type") != "individual":
            raise HTTPException(status_code=422, detail="type has to be either 'individual' or 'company'")
        
        return values