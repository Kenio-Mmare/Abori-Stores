from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


# Project root directory
BASE_DIR = Path(__file__).resolve().parents[2]

# SQLite database file
DATABASE_PATH = BASE_DIR / "abori.db"

# SQLAlchemy database URL
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# Create database engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

# Create database sessions
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)
