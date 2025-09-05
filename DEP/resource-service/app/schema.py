from pydantic import BaseModel, constr, conint, validator
from datetime import date
from fastapi import HTTPException
from enum import Enum


class TipologiaEnum(str, Enum):
    tennis = "tennis"
    beach = "beach"
    calcio = "calcio"


class CampoBooking(BaseModel):
    cf: constr(strip_whitespace=True, min_length=16, max_length=16)
    data: date
    ora: conint(ge=10, le=21)
    tipologia: TipologiaEnum

    @validator("data")
    def date_must_be_future(cls, v):
        if v <= date.today():
            raise HTTPException(status_code=400, detail="La data deve essere successiva ad oggi")
        return v


class PiscinaBooking(BaseModel):
    cf: constr(strip_whitespace=True, min_length=16, max_length=16)
    data: date
    lettini: conint(ge=0)
    ombrelloni: conint(ge=0)

    @validator("data")
    def date_must_be_future(cls, v):
        if v <= date.today():
            raise HTTPException(status_code=400, detail="La data deve essere successiva ad oggi")

        mese, giorno = v.month, v.day
        inizio = (5, 20)  # 20 maggio
        fine = (9, 15)  # 15 settembre

        if not (inizio <= (mese, giorno) <= fine):
            raise HTTPException(
                status_code=400,
                detail="La data deve essere compresa tra il 20 maggio e il 15 settembre"
            )

        return v


class Message(BaseModel):
    detail: str
