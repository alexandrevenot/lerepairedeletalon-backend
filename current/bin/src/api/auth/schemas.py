import re
from datetime import datetime

from fastapi import HTTPException
from pydantic import BaseModel, field_validator, model_validator

EMAIL_PATTERN = r'^[\w\.-]+@[\w\.-]+\.\w+$'
PHONE_NUMBER_PATTERN = r'^\+33\d{9}$'

class RegisterQuery(BaseModel):
    firstname: str
    lastname: str
    email: str
    phone_number: str
    password: str

    @field_validator('email')
    @classmethod
    def email_validator(cls, v):
        if re.match(EMAIL_PATTERN, v) is None:
            raise HTTPException(status_code=422, detail="bad email format")
        return v

    @field_validator('phone_number')
    @classmethod
    def phone_number_validator(cls, v):
        if re.match(PHONE_NUMBER_PATTERN, v) is None:
            raise HTTPException(status_code=422, detail="bad phone number format")
        return v

class LoginQuery(BaseModel):
    email: str
    password: str

class RefreshTokenQuery(BaseModel):
    token: str

    @field_validator('token')
    @classmethod
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
    email_is_verified: bool

class GetUserRM(BaseModel):
    firstname: str
    lastname: str

class GetContractsIdentity(BaseModel):
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

class PutContractsIdentityQuery(BaseModel):
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

    @model_validator(mode='before')
    @classmethod
    def validate_atts(cls, values):
        # fields presence
        if values.get("type") == "company":
            for field in ["company_name", "company_status", "capital", "head_office_address", "siret"]:
                if values.get(field) is None:
                    raise HTTPException(status_code=422, detail="missing mandatory fields")
        
        elif values.get("type") != "individual":
            raise HTTPException(status_code=422, detail="type has to be either 'individual' or 'company'")
        
        # fields content
        try:
            datetime.strptime(values.get("birthdate"), "%d/%m/%Y")
        except Exception as exc:
            raise HTTPException(status_code=422, detail="incorrect birth_date date format") from exc

        return values