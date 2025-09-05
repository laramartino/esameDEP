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

    # verifica se una persona è associata al club
    @strawberry.field
    def check_member(self, cf: str) -> MemberType | None:
        with get_db() as db:
            member = db.query(Member).filter(Member.cf == cf.upper()).first()

        if member:
            return MemberType(
                    cf=member.cf,
                    name=member.name,
                    surname=member.surname,
                    registration_date=member.registration_date
                )
        return None

    # mostra tutti i membri presenti
    @strawberry.field
    def all_members(self) -> List[MemberType]:
        with get_db() as db:
            members = db.query(Member).all()

        if not members:
            return []
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

    # aggiunge un nuovo membro al club
    @strawberry.mutation
    def add_member(self, member: MemberInput) -> str:
        cf = member.cf.upper()

        # controlla se il cf è valido
        if len(cf) != 16:
            raise Exception("CF must be exactly 16 characters long")

        with get_db() as db:

            # controlla se il membro esiste già
            existing = db.query(Member).filter(Member.cf == cf).first()
            if existing:
                raise Exception("Member already exists")

            # aggiunge il membro
            new_member = Member(
                cf=cf,
                name=member.name,
                surname=member.surname,
                registration_date=datetime.utcnow().date()
            )
            db.add(new_member)
            db.commit()
        return "Member added"

    # rimuove un membro dal club
    @strawberry.mutation
    def delete_member(self, cf: str) -> str:
        with get_db() as db:
            member = db.query(Member).filter(Member.cf == cf.upper()).first()

            # verifica l'esistenza del membro
            if not member:
                raise Exception("Member not found")
            db.delete(member)
            db.commit()

        # elimina tutte le prenotazioni effettuate dal membro eliminato
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
