from pydantic import BaseModel, constr
from datetime import date


# Schemi Pydantic
class MemberCreate(BaseModel):
    cf: constr(strip_whitespace=True, min_length=16, max_length=16)
    name: constr(strip_whitespace=True, min_length=1)
    surname: constr(strip_whitespace=True, min_length=1)


class MemberOut(BaseModel):
    cf: str
    name: str
    surname: str
    registration_date: date
