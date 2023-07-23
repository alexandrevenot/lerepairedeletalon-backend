from pydantic import BaseModel

class PriceWithFees(BaseModel):
    subtotal: float
    service_fees: int
    total: float