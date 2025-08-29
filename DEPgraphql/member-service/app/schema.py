import strawberry
from datetime import date


@strawberry.type
class MemberType:
    cf: str
    name: str
    surname: str
    registration_date: date


@strawberry.input
class MemberInput:
    cf: str
    name: str
    surname: str





