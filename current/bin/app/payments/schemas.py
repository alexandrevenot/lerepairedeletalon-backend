from fastapi import HTTPException
from pydantic import BaseModel, field_validator, model_validator

class CreateStripeAccountQuery(BaseModel):
    business_type: str
    account_token: str
    person_token: str = None
    bank_account_token: str

    @field_validator('business_type')
    @classmethod
    def business_type_validator(cls, value):
        if value not in ["company", "individual"]:
            raise HTTPException(status_code=422, detail='business_type has to be "company" or "individual"')
        return value

class StripeAccount(BaseModel):
    currently_due_is_empty: bool
    identity_document_status: str
    proof_of_residence_status: str
    proof_of_company_status: str | None = None

class UpdateStripeAccountQuery(BaseModel):
    update_account_token: str = None
    update_person_token: str = None

    @model_validator(mode='before')
    @classmethod
    def validate_atts(cls, values):
        if values.get("update_account_token") is None and values.get("update_person_token") is None:
            raise HTTPException(status_code=422, detail="tokens cannot both be None")

        return values

class Document(BaseModel):
    details_code: str | None = None

class SingleDocumentVerification(BaseModel):
    document: Document

class Company(BaseModel):
    verification: SingleDocumentVerification

class Requirements(BaseModel):
    currently_due: list[str] = []

class CompanyAccount(BaseModel):
    id: str
    company: Company
    requirements: Requirements

class IdVerification(BaseModel):
    document: Document
    additional_document: Document
    status: str

class Person(BaseModel):
    id: str
    verification: IdVerification

class CompanyStripeAccountInDB(BaseModel):
    account: CompanyAccount
    person: Person

class Individual(BaseModel):
    verification: IdVerification

class IndividualAccount(BaseModel):
    id: str
    individual: Individual
    requirements: Requirements

class IndividualStripeAccountInDB(BaseModel):
    account: IndividualAccount

class PriceWithFees(BaseModel):
    subtotal: float
    service_fees: float
    total: float

class Checkout(BaseModel):
    client_secret: str

class CoverPaymentDetails(BaseModel):
    subtotal_ht: int
    fees_ht: float
