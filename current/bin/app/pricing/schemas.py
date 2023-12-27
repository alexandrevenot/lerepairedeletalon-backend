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

class CoverPaymentDetails(BaseModel):
    subtotal_ht: int
    buyer_fees_ht: float
    seller_fees_ht: float
