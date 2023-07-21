from pydantic import BaseModel

class Checkout(BaseModel):
    subtotal: float
    service_fees_ht: float
    service_fees_taxes: float
    total: float

class Income(BaseModel):
    income: float