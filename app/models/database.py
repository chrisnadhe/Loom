from sqlmodel import SQLModel, create_engine
import os
from dotenv import load_dotenv

load_dotenv()

sqlite_url = os.getenv("DATABASE_URL", "sqlite:///./loom.db")
engine = create_engine(sqlite_url, echo=True)

def create_db_and_tables():
    from app.models.config import Template, Configuration # Ensure models are registered
    SQLModel.metadata.create_all(engine)
