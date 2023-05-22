import re

from fastapi import HTTPException
from pydantic import BaseModel, validator

email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
name_pattern = r'^[A-Za-z\s\-\']+$'

class RegisterQuery(BaseModel):
    firstname: str
    lastname: str
    email: str
    password: str

    @validator('email')
    def email_validator(cls, v):
        if re.match(email_pattern, v) is None:
            raise HTTPException(status_code=422, detail="bad email format")
        return v

    @validator('firstname')
    def firstname_validator(cls, v):
        if re.match(name_pattern, v) is None:
            raise HTTPException(status_code=422, detail="bad first name format")
        return v

    @validator('lastname')
    def lastname_validator(cls, v):
        if re.match(name_pattern, v) is None:
            raise HTTPException(status_code=422, detail="bad last name format")
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
    hashedpassword: str