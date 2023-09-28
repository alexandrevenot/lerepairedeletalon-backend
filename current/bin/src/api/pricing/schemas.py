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
    advance_subtotal: int
    advance_buyer_fees_ht: float
    advance_seller_fees_ht: float
    balance_subtotal: int
    balance_buyer_fees_ht: float
    balance_seller_fees_ht: float