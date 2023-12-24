from pydantic import BaseModel

class GetSignPageUrl(BaseModel):
    url: str

class ContractWebhookBody(BaseModel):
    status: str
    data: dict