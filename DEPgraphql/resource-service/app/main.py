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


# Funzione di supporto per verificare se un membro esiste e quindi può effettuare prenotazioni
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

    # mostra gli orari liberi di uno specifico campo in una certa data
    @strawberry.field
    def get_campiliberi(self, data: date, tipologia: TipologiaCampo) -> list[int]:
        with get_db() as db:
            prenotazioni = db.query(PrenotazioniCampi.ora).filter(
                                PrenotazioniCampi.data == data,
                                PrenotazioniCampi.tipologia == tipologia.value).all()
            occupate = {p.ora for p in prenotazioni}

        return [ora for ora in range(10, 22) if ora not in occupate]

    # mostra il numero di lettini e ombrelloni liberi in una certa data
    @strawberry.field
    def get_piscinalibera(self, data: date) -> PiscinaLibera:

        # verifica che la richiesta non sia per il periodo di chiusura
        mese, giorno = data.month, data.day
        inizio = (5, 20)  # 20 maggio
        fine = (9, 15)  # 15 settembre
        if not (inizio <= (mese, giorno) <= fine):
            return PiscinaLibera(lettini_liberi=0, ombrelloni_liberi=0)

        with get_db() as db:
            prenotazioni = db.query(PrenotazioniPiscina).filter(PrenotazioniPiscina.data == data).all()
            lettini_prenotati = sum(p.lettini for p in prenotazioni)
            ombrelloni_prenotati = sum(p.ombrelloni for p in prenotazioni)

        return PiscinaLibera(lettini_liberi=max(0, 80 - lettini_prenotati),
                             ombrelloni_liberi=max(0, 20 - ombrelloni_prenotati))


@strawberry.type
class Mutation:

    # aggiunge la prenotazione di un campo
    @strawberry.mutation
    def add_campo(self, booking: CampoBookingInput) -> str:
        cf = booking.cf.upper()

        # verifica l'esistenza del membro
        if not check_member(cf):
            raise Exception("Member doesn't exist")

        # verifica che la data sia successiva a oggi
        if booking.data <= date.today():
            raise Exception("La data deve essere successiva ad oggi")

        # verifica che lo slot richiesto sia valido
        if booking.ora < 10 or booking.ora > 21:
            raise Exception("I campi possono essere prenotati dalle 10 alle 21")

        with get_db() as db:
            # verifica se lo slot è impegnato
            existing = db.query(PrenotazioniCampi).filter_by(
                data=booking.data,
                ora=booking.ora,
                tipologia=booking.tipologia.value).first()
            if existing:
                raise Exception("Slot già prenotato")

            # aggiunge la prenotazione
            new = PrenotazioniCampi(
                cf=cf,
                data=booking.data,
                ora=booking.ora,
                tipologia=booking.tipologia.value
            )
            db.add(new)
            db.commit()
            return "Booking added"

    # rimuove la prenotazione di un campo
    @strawberry.mutation
    def delete_campo(self, booking: CampoBookingInput) -> str:
        with get_db() as db:
            prenotazione = db.query(PrenotazioniCampi).filter_by(
                cf=booking.cf.upper(),
                data=booking.data,
                ora=booking.ora,
                tipologia=booking.tipologia.value
            ).first()

            # verifica l'esistenza della prenotazione
            if prenotazione:
                db.delete(prenotazione)
                db.commit()
                return "Booking deleted"

            raise Exception("Booking not found")

    # aggiunge una prenotazione in piscina
    @strawberry.mutation
    def add_piscina(self, booking: PiscinaBookingInput) -> str:
        cf = booking.cf.upper()

        # verifica l'esistenza di un membro
        if not check_member(cf):
            raise Exception("Member doesn't exist")

        # verifica che la data sia successiva a oggi
        if booking.data <= date.today():
            raise Exception("La data deve essere successiva ad oggi")

        # verifica che la prenotazione avvenga durante il periodo estivo
        mese, giorno = booking.data.month, booking.data.day
        inizio = (5, 20)  # 20 maggio
        fine = (9, 15)  # 15 settembre
        if not (inizio <= (mese, giorno) <= fine):
            raise Exception("La data deve essere compresa tra il 20 maggio e il 15 settembre")

        with get_db() as db:
            # verifica che il membro non abbia già una prenotazione in quella data
            existing = db.query(PrenotazioniPiscina).filter_by(
                data=booking.data,
                cf=cf).first()
            if existing:
                raise Exception(f"{cf} has already a reservation")

            # verifica che ci siano abbastanza lettini disponibili
            lettini_prenotati = db.query(func.sum(PrenotazioniPiscina.lettini)).filter(
                                                PrenotazioniPiscina.data == booking.data).scalar() or 0
            if lettini_prenotati + booking.lettini > 80:
                lettini_disponibili = 80 - lettini_prenotati
                raise Exception(f"Only {lettini_disponibili} lettini available on {booking.data}")

            # verifica che ci siano abbastanza ombrelloni disponibili
            ombrelloni_prenotati = db.query(func.sum(PrenotazioniPiscina.ombrelloni)).filter(
                                                    PrenotazioniPiscina.data == booking.data).scalar() or 0
            if ombrelloni_prenotati + booking.ombrelloni > 20:
                ombrelloni_disponibili = 20 - ombrelloni_prenotati
                raise Exception(f"Only {ombrelloni_disponibili} ombrelloni available on {booking.data}")

            # aggiunta della prenotazione
            new = PrenotazioniPiscina(
                    cf=cf,
                    data=booking.data,
                    lettini=booking.lettini,
                    ombrelloni=booking.ombrelloni)
            db.add(new)
            db.commit()

        return "Booking added"

    # rimuove la prenotazione della piscina di un membro in una certa data
    @strawberry.mutation
    def delete_piscina(self, cf: str, data: date) -> str:
        with get_db() as db:
            prenotazione = db.query(PrenotazioniPiscina).filter_by(
                    cf=cf.upper(),
                    data=data).first()

            # verifica la prenotazione
            if prenotazione:
                db.delete(prenotazione)
                db.commit()
                return "Booking deleted"

        raise Exception("Booking not found")

    # rimuove tutte le prenotazioni di un membro dalla data corrente in poi
    @strawberry.mutation
    def delete_prenotazioni(self, cf: str) -> None:
        with get_db() as db:
            db.query(PrenotazioniCampi).filter(PrenotazioniCampi.cf == cf,
                                                PrenotazioniCampi.data >= date.today()).delete(synchronize_session=False)
            db.query(PrenotazioniPiscina).filter(PrenotazioniPiscina.cf == cf,
                                                PrenotazioniPiscina.data >= date.today()).delete(synchronize_session=False)
            db.commit()
        return


app = FastAPI(title="Resource Service - GraphQL")
schema = strawberry.Schema(query=Query, mutation=Mutation)
graphql_app = GraphQLRouter(schema)
app.include_router(graphql_app, prefix="/graphql")

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)