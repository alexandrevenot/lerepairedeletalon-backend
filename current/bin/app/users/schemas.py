from datetime import datetime
from typing import Annotated

from fastapi import HTTPException
from pydantic import BaseModel, model_validator, Field, model_validator

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

class BankIdentity(BaseModel):
    bank_identity_file_status: str
    bank_identity_file: str
    bank_domiciliation_country: str = ""
    account_holder: str = ""
    bank: str = ""
    iban: str = ""
    bic_or_swift: str = ""

class GetAccountInformation(BaseModel):
    user_id: str
    firstname: str
    lastname: str
    email: str
    phone_number: str
    contractual_identity: ContractualIdentity = None
    bank_identity: BankIdentity = None

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
        return {key: [str(elt) for elt in l] for key, l in values.items()}

class SellerNotifications(BaseModel):
    pendingApproval: list[str] | None = None
    pendingSignature: list[str] | None = None
    onGoing: list[str] | None = None
    done: list[str] | None = None

    @model_validator(mode='before')
    @classmethod
    def calculate_sums(cls, values):
        return {key: [str(elt) for elt in l] for key, l in values.items()}

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
