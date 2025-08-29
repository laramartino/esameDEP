from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "db/members.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()