from pydantic import BaseModel

class GetCheckoutRM(BaseModel):
    subtotal: float
    service_fees_ht: float
    service_fees_taxes: float
    total: float