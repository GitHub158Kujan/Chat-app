from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base


SQLALCHEMY_DB_URL="sqlite:///./chat_app.db"

engine = create_engine(SQLALCHEMY_DB_URL, connect_args= {"check_same_thread":False})
SessionLocal = sessionmaker(autocommit = False, bind= engine)
Base = declarative_base()


async def get_db():
    db = SessionLocal()
    try:
        yield  db
    finally:
        db.close()


