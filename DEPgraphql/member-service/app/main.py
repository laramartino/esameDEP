from fastapi import FastAPI
from db import engine, get_db
from model import Base, Member
import strawberry
from strawberry.fastapi import GraphQLRouter
import uvicorn
from typing import List
from schema import *
from datetime import datetime
import requests


@strawberry.type
class Query:
    @strawberry.field
    def check_member(self, cf: str) -> MemberType | None:
        db = next(get_db())
        member = db.query(Member).filter(Member.cf == cf.upper()).first()
        db.close()
        if member:
            return MemberType(
                cf=member.cf,
                name=member.name,
                surname=member.surname,
                registration_date=member.registration_date
            )
        return None

    @strawberry.field
    def all_members(self) -> List[MemberType]:
        db = next(get_db())
        members = db.query(Member).all()
        db.close()
        return [
            MemberType(
                cf=m.cf,
                name=m.name,
                surname=m.surname,
                registration_date=m.registration_date
            )
            for m in members
        ]


@strawberry.type
class Mutation:
    @strawberry.mutation
    def add_member(self, member: MemberInput) -> str:
        db = next(get_db())
        cf = member.cf.upper()
        if len(cf) != 16:
            raise Exception("CF must be exactly 16 characters long")

        existing = db.query(Member).filter(Member.cf == cf).first()
        if existing:
            db.close()
            raise Exception("Member already exists")

        new_member = Member(
            cf=cf,
            name=member.name,
            surname=member.surname,
            registration_date=datetime.utcnow().date()
        )
        db.add(new_member)
        db.commit()
        db.close()
        return "Member added"

    @strawberry.mutation
    def delete_member(self, cf: str) -> str:
        db = next(get_db())
        member = db.query(Member).filter(Member.cf == cf.upper()).first()
        if not member:
            db.close()
            raise Exception("Member not found")
        db.delete(member)
        db.commit()
        db.close()

        graphql_url = "http://resource-service:5000/graphql"
        mutation = """
            mutation ($cf: String!) {
              deletePrenotazioni(cf: $cf) 
            }
            """
        variables = {"cf": cf.upper()}
        try:
            resp = requests.post(graphql_url, json={"query": mutation, "variables": variables})
            resp.raise_for_status()
            data = resp.json()
            if "errors" in data:
                raise Exception(f"Warning: impossibile eliminare prenotazioni: {data['errors']}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Warning: resource-service non raggiungibile: {e}")

        return "Member deleted"


schema = strawberry.Schema(query=Query, mutation=Mutation)
app = FastAPI(title="Member Service - GraphQL")
graphql_app = GraphQLRouter(schema)
app.include_router(graphql_app, prefix="/graphql")


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    uvicorn.run(app, host="0.0.0.0", port=5000)
