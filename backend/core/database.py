from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env file

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/mydb")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """
    Dependency to get a database session.
    Ensures the database session is always closed after the request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Function to create all tables.
# This is typically used with Alembic for migrations in a production setup.
def create_db_and_tables():
    # Import all models here before calling create_all
    # This ensures they are registered with SQLAlchemy's metadata.
    # from backend.models.user_model import User # Example
    # from backend.models.course_model import Course # Example
    # ... and so on for all your models
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    print("Creating database tables based on models...")
    # Note: You'd typically want to manage your database schema with Alembic.
    # This direct call is useful for initial setup or simple applications.
    # Ensure all your model modules are imported above if you use this.
    # For this example, we are not importing any specific models yet.
    # You would need to uncomment and add imports for your actual models.
    create_db_and_tables()
    print("Database tables created (if they didn't exist).")
