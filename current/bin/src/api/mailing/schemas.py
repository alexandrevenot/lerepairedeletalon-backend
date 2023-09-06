from pydantic import BaseModel

class SendPasswordRecoveryEmailQuery(BaseModel):
    email: str

class RecoverPasswordQuery(BaseModel):
    new_password: str
    code: str