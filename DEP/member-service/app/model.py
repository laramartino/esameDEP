from sqlalchemy import Column, String, Date
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Member(Base):
    __tablename__ = "members"
    cf = Column(String(16), primary_key=True, index=True)
    name = Column(String(50), index=True)
    surname = Column(String(50), index=True)
    registration_date = Column(Date, index=True)
