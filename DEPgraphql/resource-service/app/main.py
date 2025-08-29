import strawberry
from sqlalchemy import func
from sqlalchemy.orm import Session
from db import get_db, engine
from model import PrenotazioniCampi, PrenotazioniPiscina
import requests
import uvicorn
from model import Base
from schema import *
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter


# --- Funzione di supporto ---
def check_member(cf: str) -> bool:
    try:
        url = "http://member-service:5000/graphql"
        query = """
        query ($cf: String!) {
            checkMember(cf: $cf) {
                cf
                name
                surname
                registrationDate
            }
        }
        """
        variables = {"cf": cf}
        response = requests.post(url, json={"query": query, "variables": variables})
        response.raise_for_status()
        data = response.json()
        return data["data"]["checkMember"] is not None
    except requests.exceptions.RequestException as e:
        raise Exception(f"Cannot reach member service: {str(e)}")


@strawberry.type
class Query:

    @strawberry.field
    def get_campiliberi(self, data: date, tipologia: TipologiaCampo) -> list[CampoLibero]:

        db: Session = next(get_db())

        ore_disponibili = range(10, 22)
        liberi = []

        for ora in ore_disponibili:
            prenotazione = (
                db.query(PrenotazioniCampi)
                .filter(
                    PrenotazioniCampi.data == data,
                    PrenotazioniCampi.ora == ora,
                    PrenotazioniCampi.tipologia == tipologia.value,
                )
                .first()
            )
            if not prenotazione:
                liberi.append(CampoLibero(ora=ora))

        db.close()

        return liberi

    @strawberry.field
    def get_piscinalibera(self, data: date) -> PiscinaLibera:
        db: Session = next(get_db())

        prenotazioni = db.query(PrenotazioniPiscina).filter(PrenotazioniPiscina.data == data).all()

        lettini_prenotati = sum(p.lettini for p in prenotazioni)
        ombrelloni_prenotati = sum(p.ombrelloni for p in prenotazioni)

        db.close()

        lettini_liberi = max(0, 80 - lettini_prenotati)
        ombrelloni_liberi = max(0, 20 - ombrelloni_prenotati)

        return PiscinaLibera(
            lettini_liberi=lettini_liberi,
            ombrelloni_liberi=ombrelloni_liberi
        )


# --- Mutations ---
@strawberry.type
class Mutation:

    @strawberry.mutation
    def add_campo(self, booking: CampoBookingInput) -> BookingResponse:
        db: Session = next(get_db())

        try:
            cf = booking.cf.upper()
            if not check_member(cf):
                raise Exception("CF doesn't exist")

            if booking.data <= date.today():
                raise Exception("La data deve essere successiva ad oggi")

            if booking.ora < 10 or booking.ora > 21:
                raise Exception("I campi possono essere prenotati dalle 10 alle 21")

            existing = db.query(PrenotazioniCampi).filter_by(
                data=booking.data,
                ora=booking.ora,
                tipologia=booking.tipologia.value
            ).first()
            if existing:
                raise Exception("Slot già prenotato")

            new = PrenotazioniCampi(
                cf=cf,
                data=booking.data,
                ora=booking.ora,
                tipologia=booking.tipologia.value
            )
            db.add(new)
            db.commit()
            return BookingResponse(detail="Booking added")
        finally:
            db.close()

    @strawberry.mutation
    def delete_campo(self, booking: CampoBookingInput) -> BookingResponse:
        db: Session = next(get_db())

        try:
            prenotazione = db.query(PrenotazioniCampi).filter_by(
                cf=booking.cf.upper(),
                data=booking.data,
                ora=booking.ora,
                tipologia=booking.tipologia.value
            ).first()
            if prenotazione:
                db.delete(prenotazione)
                db.commit()
                return BookingResponse(detail="Booking deleted")
            raise Exception("Booking not found")
        finally:
            db.close()

    @strawberry.mutation
    def add_piscina(self, booking: PiscinaBookingInput) -> BookingResponse:
        db: Session = next(get_db())

        try:
            cf = booking.cf.upper()
            if not check_member(cf):
                raise Exception("CF doesn't exist")
            if booking.data <= date.today():
                raise Exception("La data deve essere successiva ad oggi")

            mese, giorno = booking.data.month, booking.data.day
            inizio = (5, 20)  # 20 maggio
            fine = (9, 15)  # 15 settembre
            if not (inizio <= (mese, giorno) <= fine):
                raise Exception("La data deve essere compresa tra il 20 maggio e il 15 settembre")

            lettini_prenotati = db.query(func.sum(PrenotazioniPiscina.lettini)).filter(
                PrenotazioniPiscina.data == booking.data
            ).scalar() or 0
            if lettini_prenotati + booking.lettini > 80:
                lettini_disponibili = 80 - lettini_prenotati
                raise Exception(f"Only {lettini_disponibili} lettini available on {booking.data}")

            ombrelloni_prenotati = db.query(func.sum(PrenotazioniPiscina.ombrelloni)).filter(
                PrenotazioniPiscina.data == booking.data
            ).scalar() or 0
            if ombrelloni_prenotati + booking.ombrelloni > 20:
                ombrelloni_disponibili = 20 - ombrelloni_prenotati
                raise Exception(f"Only {ombrelloni_disponibili} ombrelloni available on {booking.data}")

            existing = db.query(PrenotazioniPiscina).filter_by(
                data=booking.data,
                cf=cf
            ).first()
            if existing:
                raise Exception(f"{cf} has already a reservation")

            new = PrenotazioniPiscina(
                cf=cf,
                data=booking.data,
                lettini=booking.lettini,
                ombrelloni=booking.ombrelloni
            )
            db.add(new)
            db.commit()
            return BookingResponse(detail="Booking added")
        finally:
            db.close()

    @strawberry.mutation
    def delete_piscina(self, booking: PiscinaBookingInput) -> BookingResponse:
        db: Session = next(get_db())

        try:
            prenotazione = db.query(PrenotazioniPiscina).filter_by(
                cf=booking.cf.upper(),
                data=booking.data,
                lettini=booking.lettini,
                ombrelloni=booking.ombrelloni
            ).first()
            if prenotazione:
                db.delete(prenotazione)
                db.commit()
                return BookingResponse(detail="Booking deleted")
            raise Exception("Booking not found")
        finally:
            db.close()

    @strawberry.mutation
    def delete_prenotazioni(self, cf: str) -> None:
        db: Session = next(get_db())
        db.query(PrenotazioniCampi).filter(PrenotazioniCampi.cf == cf).delete(synchronize_session=False)
        db.query(PrenotazioniPiscina).filter(PrenotazioniPiscina.cf == cf).delete(synchronize_session=False)
        db.commit()
        db.close()
        return


app = FastAPI(title="Resource Service - GraphQL")
schema = strawberry.Schema(query=Query, mutation=Mutation)
graphql_app = GraphQLRouter(schema)
app.include_router(graphql_app, prefix="/graphql")

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)