from datetime import datetime

from pydantic import BaseModel, model_validator
from fastapi import HTTPException

class StallionOwnerQuery(BaseModel):
    business_type: str
    firstname: str
    lastname: str
    gender: str
    company_structure: str = None
    company_name: str = None
    capital: str = None
    rcs: str = None
    siren: str = None
    head_office_address_line1: str = None
    head_office_address_line2: str = None
    head_office_address_postal_code: str = None
    head_office_address_city: str = None
    role_in_company: str = None
    birthdate: str = None
    birthplace: str = None
    citizenship: str = None
    address_line1: str = None
    address_line2: str = None
    address_postal_code: str = None
    address_city: str = None

    @model_validator(mode='before')
    @classmethod
    def validate_atts(cls, values):
        if values.get("business_type") not in ["individual", "company"]:
            raise HTTPException(status_code=422, detail='business_type has to be either "individual" or "company"')

        if values.get("gender") is not None and values.get("gender") not in ["Monsieur", "Madame"]:
            raise HTTPException(status_code=422, detail='gender has to be either "Monsieur" or "Madame"')

        if values.get("birthdate") is not None:
            try:
                datetime.strptime(values.get("birthdate"), "%d/%m/%Y")
            except Exception as exc:
                raise HTTPException(status_code=422, detail="incorrect birthdate date format") from exc

        return values

class StallionOwnerPostResponse(BaseModel):
    message: str
    id: str

class StallionOwner(BaseModel):
    business_type: str
    firstname: str
    lastname: str
    gender: str
    company_structure: str = None
    company_name: str = None
    capital: str = None
    rcs: str = None
    siren: str = None
    head_office_address_line1: str = None
    head_office_address_line2: str = None
    head_office_address_postal_code: str = None
    head_office_address_city: str = None
    role_in_company: str = None
    birthdate: str = None
    birthplace: str = None
    citizenship: str = None
    address_line1: str = None
    address_line2: str = None
    address_postal_code: str = None
    address_city: str = None

class StallionOwnerInDB(BaseModel):
    id: str
    business_type: str
    firstname: str
    lastname: str
    gender: str
    company_structure: str = None
    company_name: str = None
    capital: str = None
    rcs: str = None
    siren: str = None
    head_office_address_line1: str = None
    head_office_address_line2: str = None
    head_office_address_postal_code: str = None
    head_office_address_city: str = None
    role_in_company: str = None
    birthdate: str = None
    birthplace: str = None
    citizenship: str = None
    address_line1: str = None
    address_line2: str = None
    address_postal_code: str = None
    address_city: str = None

class StallionOwnerNames(BaseModel):
    stallion_owners: list[StallionOwnerInDB]
