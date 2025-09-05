from fastapi import FastAPI
from db import engine, get_db
from model import Base, Member
import uvicorn
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List
from schema import *
import requests

app = FastAPI()
router = APIRouter(prefix="/members", tags=["members"])


# verifica se una persona è associata al club
@router.get("/{cf}")
def check_member(cf: str, db: Session = Depends(get_db)) -> MemberOut:
    member = db.query(Member).filter(Member.cf == cf.upper()).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    return member


# aggiunge un nuovo membro al club
@router.post("", status_code=status.HTTP_201_CREATED)
def add_member(member: MemberCreate, db: Session = Depends(get_db)) -> Message:
    cf = member.cf.upper()

    # verifica se esiste già
    existing = db.query(Member).filter(Member.cf == cf).first()
    if existing:
        raise HTTPException(status_code=409, detail="Member already exists")

    new_member = Member(
        cf=cf,
        name=member.name,
        surname=member.surname,
        registration_date=datetime.utcnow().date()
    )
    db.add(new_member)
    db.commit()
    return Message(detail="Member added")


# rimuove un membro dal club
@router.delete("/{cf}")
def delete_member(cf: str, db: Session = Depends(get_db)) -> Message:
    cf = cf.upper()

    # verifica se il membro esiste
    member = db.query(Member).filter(Member.cf == cf).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    db.delete(member)
    db.commit()

    # rimozione delle prenotazioni del membro
    try:
        url = f"http://resource-service:5000/resources/prenotazioni/{cf}"
        response = requests.delete(url)
        if response.status_code != 204:
            raise HTTPException(status_code=502, detail=f"Errore nel cancellare le prenotazioni per {cf}")
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Servizio prenotazioni non raggiungibile: {str(e)}")

    return Message(detail="Member deleted")


# mostra tutti i membri presenti
@router.get("", response_model=List[MemberOut])
def all_members(db: Session = Depends(get_db)) -> List[MemberOut]:
    members = db.query(Member).all()
    return members


app.include_router(router)
Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
