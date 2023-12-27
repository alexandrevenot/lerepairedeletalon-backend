from pydantic import BaseModel

class StallionsToBeValidated(BaseModel):
    nsire_list: list[str]
