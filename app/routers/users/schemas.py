from datetime import datetime
from typing import Annotated

from fastapi import HTTPException
from pydantic import BaseModel, Field, model_validator


class GetUserRM(BaseModel):
    firstname: str
    lastname: str

class PutLegalIdentityResponse(BaseModel):
    message: str
    new_level: int

class PutLegalIdentityQuery(BaseModel):
    business_type: str
    company_structure: str = None
    company_name: str = None
    capital: str = None
    rcs: str = None
    siren: str = None
    head_office_address_line1: str = None
    head_office_address_line2: str = None
    head_office_address_postal_code: str = None
    head_office_address_city: str = None
    gender: str = None
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

class LegalIdentity(BaseModel):
    level: int
    business_type: str
    gender: str = None
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
    iban_last4: str = None

class GetAccountInformation(BaseModel):
    user_id: str
    firstname: str
    lastname: str
    email: str
    phone_number: str
    legal_identity: LegalIdentity = None

class Review(BaseModel):
    stallion_name: str
    stallion_nsire: str
    reviewer_firstname: str
    reviewer_lastname: str
    reviewed_firstname: str
    reviewed_lastname: str
    writing_date: str
    content: str
    score: Annotated[int, Field(get=1, le=5)]

class Reviews(BaseModel):
    reviews: list[Review]

class ReviewQuery(BaseModel):
    cover_id: str
    score: Annotated[int, Field(get=1, le=5)]
    content: str

class UserScore(BaseModel):
    firstname: str
    lastname: str
    score: float | None = None
    nb_reviews: int | None = None
    owner_has_other_reviews: bool = False

class BuyerNotifications(BaseModel):
    denied: list[str] | None = None
    pendingApproval: list[str] | None = None
    pendingSignature: list[str] | None = None

    @model_validator(mode='before')
    @classmethod
    def calculate_sums(cls, values):
        return {key: [str(elt) for elt in lst] for key, lst in values.items()}

class SellerNotifications(BaseModel):
    pendingApproval: list[str] | None = None
    pendingSignature: list[str] | None = None
    onGoing: list[str] | None = None
    done: list[str] | None = None

    @model_validator(mode='before')
    @classmethod
    def calculate_sums(cls, values):
        return {key: [str(elt) for elt in lst] for key, lst in values.items()}

class CoverNotifications(BaseModel):
    buyer: BuyerNotifications | None = None
    seller: SellerNotifications | None = None

class AcknowledgedCoverNotifications(BaseModel):
    cover_ids: Annotated[list[str], Field(min_items=1)]
    pov: str
    group: str

    @model_validator(mode='before')
    @classmethod
    def validate_atts(cls, values):
        if values.get("pov") == "seller":
            if values.get("group") not in [
                "pendingApproval",
                "pendingSignature",
                "onGoing",
                "done"
            ]:
                raise HTTPException(status_code=422, detail="group not allowed for this pov")
        elif values.get("pov") == "buyer":
            if values.get("group") not in [
                "pendingApproval",
                "pendingSignature",
                "denied"
            ]:
                raise HTTPException(status_code=422, detail="group not allowed for this pov")
        else:
            raise HTTPException(status_code=422, detail="group not allowed for this pov")

        return values

class DeleteAccountQuery(BaseModel):
    passphrase: Annotated[str, Field(pattern="Supprimer mon compte")]
