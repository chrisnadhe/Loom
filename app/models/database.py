import os
from sqlmodel import SQLModel, create_engine
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./loom.db")
APP_ENV = os.getenv("APP_ENV", "development")

# Only enable SQL echo in development mode for debugging
engine = create_engine(DATABASE_URL, echo=(APP_ENV == "development"))


def create_db_and_tables() -> None:
    """Create all database tables if they don't exist."""
    from app.models.config import Configuration  # noqa: F401 — register model
    SQLModel.metadata.create_all(engine)
