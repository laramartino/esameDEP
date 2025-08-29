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


# --- Funzioni di supporto ---
def check_member(cf: str) -> bool:
    try:
        member_service_url = f"http://member-service:5000/members/{cf}"
        response = requests.get(member_service_url)
        if response.status_code == 404:
            return False
        response.raise_for_status()
        data = response.json()
        return True
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Cannot reach member service: {str(e)}")


# --- Endpoints ---
@router.get("/campiliberi/{data}/{tipologia}")
def get_campo(data: date, tipologia: TipologiaEnum, db: Session = Depends(get_db)):

    ore_disponibili = range(10, 22)  # 10..21 inclusi
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

    return {"detail": liberi}


@router.post("/campo")
def add_campo(booking: CampoBooking, db: Session = Depends(get_db)):
    # Controllo membro
    cf = booking.cf.upper()
    if not check_member(cf):
        raise HTTPException(status_code=404, detail="cf doesn't exist")

    # Controllo slot già prenotato
    existing = db.query(PrenotazioniCampi).filter_by(
        data=booking.data,
        ora=booking.ora,
        tipologia=booking.tipologia
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Slot già prenotato")

    # Creazione prenotazione
    new = PrenotazioniCampi(
        cf=cf,
        data=booking.data,
        ora=booking.ora,
        tipologia=booking.tipologia
    )
    db.add(new)
    db.commit()
    return {"detail": "Booking added"}


@router.delete("/campo")
def delete_campo(booking: CampoBooking, db: Session = Depends(get_db)):
    prenotazione = db.query(PrenotazioniCampi).filter_by(
        cf=booking.cf.upper(),
        data=booking.data,
        ora=booking.ora,
        tipologia=booking.tipologia
    ).first()
    if prenotazione:
        db.delete(prenotazione)
        db.commit()
        return {"detail": "Booking deleted"}
    raise HTTPException(status_code=404, detail="Booking not found")


@router.delete("/prenotazioni/{cf}")
def delete_prenotazioni(cf: str, db: Session = Depends(get_db)):
    db.query(PrenotazioniCampi).filter(PrenotazioniCampi.cf == cf).delete(synchronize_session=False)
    db.query(PrenotazioniPiscina).filter(PrenotazioniPiscina.cf == cf).delete(synchronize_session=False)
    db.commit()
    return


@router.get("/piscinalibera/{data}")
def get_piscina(data: date, db: Session = Depends(get_db)):

    prenotazioni = db.query(PrenotazioniPiscina).filter(PrenotazioniPiscina.data == data).first()

    if prenotazioni:
        lettini_liberi = 80 - prenotazioni.lettini
        ombrelloni_liberi = 20 - prenotazioni.ombrelloni
    else:
        lettini_liberi = 80
        ombrelloni_liberi = 20

    return {"detail": {"lettini_liberi": lettini_liberi,
                        "ombrelloni_liberi": ombrelloni_liberi}}


@router.post("/piscina")
def add_piscina(booking: PiscinaBooking, db: Session = Depends(get_db)):
    # Controllo membro
    cf = booking.cf.upper()
    if not check_member(cf):
        raise HTTPException(status_code=404, detail="cf doesn't exist")

    # Validazione lettini
    lettini_prenotati = db.query(func.sum(PrenotazioniPiscina.lettini)).filter(
        PrenotazioniPiscina.data == booking.data
    ).scalar() or 0
    if lettini_prenotati + booking.lettini > 80:
        lettini_disponibili = 80 - lettini_prenotati
        raise HTTPException(status_code=409, detail=f"Only {lettini_disponibili} lettini available on {booking.data}")

    # Validazione ombrelloni
    ombrelloni_prenotati = db.query(func.sum(PrenotazioniPiscina.ombrelloni)).filter(
        PrenotazioniPiscina.data == booking.data
    ).scalar() or 0
    if ombrelloni_prenotati + booking.ombrelloni > 20:
        ombrelloni_disponibili = 20 - ombrelloni_prenotati
        raise HTTPException(status_code=409, detail=f"Only {ombrelloni_disponibili} ombrelloni available on {booking.data}")

    # Controllo doppia prenotazione
    existing = db.query(PrenotazioniPiscina).filter_by(
        data=booking.data,
        cf=cf
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"{cf} has already a reservation")

    # Creazione prenotazione
    new = PrenotazioniPiscina(
        cf=cf,
        data=booking.data,
        lettini=booking.lettini,
        ombrelloni=booking.ombrelloni
    )
    db.add(new)
    db.commit()
    return {"detail": "Booking added"}


@router.delete("/piscina")
def delete_piscina(booking: PiscinaBooking, db: Session = Depends(get_db)):
    prenotazione = db.query(PrenotazioniPiscina).filter_by(
        cf=booking.cf.upper(),
        data=booking.data,
        lettini=booking.lettini,
        ombrelloni=booking.ombrelloni
    ).first()
    if prenotazione:
        db.delete(prenotazione)
        db.commit()
        return {"detail": "Booking deleted"}
    raise HTTPException(status_code=404, detail="Booking not found")


app.include_router(router)
Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)
