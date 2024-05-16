from pydantic import BaseModel

class IdList(BaseModel):
    id_list: list[str]
