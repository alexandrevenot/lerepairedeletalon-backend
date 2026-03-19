from pydantic import BaseModel


class SendPasswordUpdateEmailQuery(BaseModel):
    email: str

class UpdatePasswordQuery(BaseModel):
    new_password: str
    code: str

class VerifyEmailQuery(BaseModel):
    code: str
