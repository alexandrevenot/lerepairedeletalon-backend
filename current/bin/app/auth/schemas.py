import re

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
