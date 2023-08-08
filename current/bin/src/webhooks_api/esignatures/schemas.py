from pydantic import BaseModel

class ContractWebhookBody(BaseModel):
    status: str
    data: dict