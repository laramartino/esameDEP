from sqlalchemy import Column, String, Integer, Date
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class PrenotazioniCampi(Base):
    __tablename__ = "PrenotazioniCampi"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    cf = Column(String(16), index=True, nullable=False)  # codice fiscale socio
    data = Column(Date, index=True, nullable=False)
    ora = Column(Integer, index=True, nullable=False)    # dalle 10 alle 21
    tipologia = Column(String(50), index=True, nullable=False)  # beach, tennis, calcio


class PrenotazioniPiscina(Base):
    __tablename__ = "PrenotazioniPiscina"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    cf = Column(String(16), index=True, nullable=False)
    data = Column(Date, index=True, nullable=False)
    lettini = Column(Integer, index=True, nullable=False)     # max 80 in totale
    ombrelloni = Column(Integer, index=True, nullable=False)  # max 20 in totale
