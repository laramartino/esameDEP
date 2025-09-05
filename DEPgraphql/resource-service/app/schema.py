import strawberry
import enum
from datetime import date


@strawberry.enum
class TipologiaCampo(enum.Enum):
    beach = "beach"
    calcio = "calcio"
    tennis = "tennis"


@strawberry.input
class CampoBookingInput:
    cf: str
    data: date
    ora: int
    tipologia: TipologiaCampo


@strawberry.input
class PiscinaBookingInput:
    cf: str
    data: date
    lettini: int
    ombrelloni: int


@strawberry.type
class PiscinaLibera:
    lettini_liberi: int
    ombrelloni_liberi: int

