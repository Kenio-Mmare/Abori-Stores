from app.database.base import Base
from app.database.database import engine

# Import models so SQLAlchemy knows about them
from app.models.user import User


def initialize_database():
    Base.metadata.create_all(bind=engine)
    print("Database initialized successfully.")


if __name__ == "__main__":
    initialize_database()
    