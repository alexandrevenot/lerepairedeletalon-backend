from pydantic import BaseModel

class PriceWithFees(BaseModel):
    subtotal: int
    service_fees: int
    total: int

class Checkout(BaseModel):
    subtotal: int
    service_fees: int
    total: int
    status: str