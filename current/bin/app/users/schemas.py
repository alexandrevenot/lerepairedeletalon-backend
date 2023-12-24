from datetime import datetime

from fastapi import HTTPException
from pydantic import BaseModel, model_validator, conint

class GetUserRM(BaseModel):
    firstname: str
    lastname: str

class ContractualIdentity(BaseModel):
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

class GetAccountInformation(BaseModel):
    user_id: str
    firstname: str
    lastname: str
    email: str
    phone_number: str
    contractual_identity: ContractualIdentity = None

class PutContractualIdentityQuery(BaseModel):
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

class Review(BaseModel):
    stallion_name: str
    stallion_nsire: str
    reviewer_firstname: str
    reviewer_lastname: str
    reviewed_firstname: str
    reviewed_lastname: str
    writing_date: str
    content: str
    score: conint(ge=1, le=5)

class Reviews(BaseModel):
    reviews: list[Review]

class ReviewQuery(BaseModel):
    cover_id: str
    score: conint(ge=1, le=5)
    content: str

class UserScore(BaseModel):
    firstname: str
    lastname: str
    score: float | None = None
    nb_reviews: int | None = None
    owner_has_other_reviews: bool = False
