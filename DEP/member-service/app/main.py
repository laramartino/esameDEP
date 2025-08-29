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


@router.get("/{cf}")
def check_member(cf: str, db: Session = Depends(get_db)):
    member = db.query(Member).filter(Member.cf == cf.upper()).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    return MemberOut(
        cf=member.cf,
        name=member.name,
        surname=member.surname,
        registration_date=member.registration_date
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def add_member(member: MemberCreate, db: Session = Depends(get_db)):
    cf = member.cf.upper()

    existing = db.query(Member).filter(Member.cf == cf).first()
    if existing:
        return HTTPException(status_code=409, detail="Member already exists")

    new_member = Member(
        cf=cf,
        name=member.name,
        surname=member.surname,
        registration_date=datetime.utcnow().date()
    )
    db.add(new_member)
    db.commit()
    return {"detail": "Member added"}


@router.delete("/{cf}")
def delete_member(cf: str, db: Session = Depends(get_db)):
    member = db.query(Member).filter(Member.cf == cf.upper()).first()
    if not member:
        return HTTPException(status_code=404, detail="Member not found")
    db.delete(member)
    db.commit()

    try:
        url = f"http://resource-service:5000/resources/prenotazioni/{cf.upper()}"
        response = requests.delete(url)
        if response.status_code != 200:
            raise Exception("Errore nel cancellare le prenotazioni")
    except Exception as e:
        print(f"Warning: impossibile eliminare prenotazioni per {cf}: {e}")

    return {"detail": "Member deleted"}


@router.get("", response_model=List[MemberOut])
def all_members(db: Session = Depends(get_db)):
    members = db.query(Member).all()
    return members


app.include_router(router)
Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
