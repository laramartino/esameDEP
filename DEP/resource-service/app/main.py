from fastapi import FastAPI, APIRouter, HTTPException, Depends
from db import engine, get_db
import uvicorn
from sqlalchemy.orm import Session
from sqlalchemy import func
from model import *
import requests
from schema import *
from datetime import date


router = APIRouter(prefix="/resources", tags=["resources"])
app = FastAPI(title="Resource Service")


# Funzione di supporto per verificare se un membro esiste e quindi può effettuare prenotazioni
def check_member(cf: str) -> bool:
    member_service_url = f"http://member-service:5000/members/{cf}"

    try:
        response = requests.get(member_service_url)
        if response.status_code == 404:
            return False
        response.raise_for_status()  # solleva eccezione per altri errori
        return True
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Cannot reach member service: {str(e)}")


# mostra gli orari liberi di uno specifico campo in una certa data
@router.get("/campiliberi/{data}/{tipologia}")
def get_campo(data: date, tipologia: TipologiaEnum, db: Session = Depends(get_db)) -> Message:

    ore_disponibili = range(10, 22)
    liberi = []

    for ora in ore_disponibili:
        prenotazione = (
                db.query(PrenotazioniCampi).filter(
                    PrenotazioniCampi.data == data,
                    PrenotazioniCampi.ora == ora,
                    PrenotazioniCampi.tipologia == tipologia).first()
            )

        if not prenotazione:
            liberi.append(ora)

    liberi_str = ", ".join(str(ora) for ora in liberi)
    return Message(detail=liberi_str)


# aggiunge la prenotazione di un campo
@router.post("/campo")
def add_campo(booking: CampoBooking, db: Session = Depends(get_db)) -> Message:
    cf = booking.cf.upper()

    # verifica esistenza del membro
    if not check_member(cf):
        raise HTTPException(status_code=404, detail="Member doesn't exist")

    # verifica se lo slot orario è già prenotato
    existing = db.query(PrenotazioniCampi).filter_by(
        data=booking.data,
        ora=booking.ora,
        tipologia=booking.tipologia
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Slot già prenotato")

    # creazione prenotazione
    new = PrenotazioniCampi(
        cf=cf,
        data=booking.data,
        ora=booking.ora,
        tipologia=booking.tipologia
    )
    db.add(new)
    db.commit()
    return Message(detail="Booking added")


# rimuove la prenotazione di un campo
@router.delete("/campo/{cf}/{data}/{ora}/{tipologia}")
def delete_campo(cf: str, data: date, ora: int, tipologia: TipologiaEnum, db: Session = Depends(get_db)) -> Message:
    prenotazione = db.query(PrenotazioniCampi).filter_by(
        cf=cf,
        data=data,
        ora=ora,
        tipologia=tipologia).first()

    # verifica se la prenotazione esiste
    if prenotazione:
        db.delete(prenotazione)
        db.commit()
        return Message(detail="Booking deleted")

    raise HTTPException(status_code=404, detail="Booking not found")


# rimuove tutte le prenotazioni di un membro dalla data corrente in poi
@router.delete("/prenotazioni/{cf}", status_code=204)   # 204 ok, no content
def delete_prenotazioni(cf: str, db: Session = Depends(get_db)):
    db.query(PrenotazioniCampi).filter(PrenotazioniCampi.cf == cf,
                                       PrenotazioniCampi.data >= date.today()).delete(synchronize_session=False)
    db.query(PrenotazioniPiscina).filter(PrenotazioniPiscina.cf == cf,
                                         PrenotazioniPiscina.data >= date.today()).delete(synchronize_session=False)
    db.commit()
    return


# mostra il numero di lettini e ombrelloni liberi in una certa data
@router.get("/piscinalibera/{data}", response_model=Message)
def get_piscina(data: date, db: Session = Depends(get_db)) -> Message:

    # verifica che la richiesta non sia per il periodo di chiusura
    mese, giorno = data.month, data.day
    inizio = (5, 20)  # 20 maggio
    fine = (9, 15)  # 15 settembre
    if not (inizio <= (mese, giorno) <= fine):
        return Message(detail="Piscina chiusa. Apertura nel periodo estivo dal 20 maggio al 15 settembre.")

    # somma totale di lettini e ombrelloni prenotati nella data richiesta
    totale_prenotazioni = db.query(
        func.coalesce(func.sum(PrenotazioniPiscina.lettini), 0),
        func.coalesce(func.sum(PrenotazioniPiscina.ombrelloni), 0)
    ).filter(PrenotazioniPiscina.data == data).one()

    prenotati_lettini, prenotati_ombrelloni = totale_prenotazioni

    lettini_liberi = 80 - prenotati_lettini
    ombrelloni_liberi = 20 - prenotati_ombrelloni

    return Message(detail=f"{lettini_liberi} lettini e {ombrelloni_liberi} ombrelloni liberi")


# aggiunge una prenotazione in piscina
@router.post("/piscina")
def add_piscina(booking: PiscinaBooking, db: Session = Depends(get_db)) -> Message:
    cf = booking.cf.upper()

    # verifica l'esistenza di un membro
    if not check_member(cf):
        raise HTTPException(status_code=404, detail="Member doesn't exist")

    # verifica se il membro ha già una prenotazione per quella data
    existing = db.query(PrenotazioniPiscina).filter_by(
        data=booking.data,
        cf=cf).first()
    if existing:
        raise HTTPException(status_code=409, detail="Member has already a reservation")

    # verifica se ci sono abbastanza lettini
    lettini_prenotati = db.query(func.sum(PrenotazioniPiscina.lettini)).filter(
        PrenotazioniPiscina.data == booking.data).scalar() or 0
    if lettini_prenotati + booking.lettini > 80:
        lettini_disponibili = 80 - lettini_prenotati
        raise HTTPException(status_code=409, detail=f"Only {lettini_disponibili} lettini available on {booking.data}")

    # verifica se ci sono abbastanza ombrelloni
    ombrelloni_prenotati = db.query(func.sum(PrenotazioniPiscina.ombrelloni)).filter(
        PrenotazioniPiscina.data == booking.data).scalar() or 0
    if ombrelloni_prenotati + booking.ombrelloni > 20:
        ombrelloni_disponibili = 20 - ombrelloni_prenotati
        raise HTTPException(status_code=409, detail=f"Only {ombrelloni_disponibili} ombrelloni available on {booking.data}")

    # aggiunta della prenotazione
    new = PrenotazioniPiscina(
        cf=cf,
        data=booking.data,
        lettini=booking.lettini,
        ombrelloni=booking.ombrelloni)
    db.add(new)
    db.commit()
    return Message(detail="Booking added")


# rimuove la prenotazione della piscina di un membro in una certa data
@router.delete("/piscina/{cf}/{data}")
def delete_piscina(cf: str, data: date, db: Session = Depends(get_db)) -> Message:
    prenotazione = db.query(PrenotazioniPiscina).filter_by(
        cf=cf.upper(),
        data=data
    ).delete(synchronize_session=False)
    db.commit()

    if prenotazione == 0:
        raise HTTPException(status_code=404, detail="Booking not found")
    return Message(detail="Booking deleted")


app.include_router(router)
Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)
