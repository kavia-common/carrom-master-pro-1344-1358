"""
Database connection and session management module.

Uses SQLAlchemy for ORM and connects to PostgreSQL using
environment variables: POSTGRES_URL, POSTGRES_USER, POSTGRES_PASSWORD,
POSTGRES_DB, POSTGRES_PORT.
"""
import os
import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Read database connection from environment variables
# POSTGRES_URL format: postgresql://localhost:5000/myapp
POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://localhost:5000/myapp")
POSTGRES_USER = os.getenv("POSTGRES_USER", "appuser")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "dbuser123")
POSTGRES_DB = os.getenv("POSTGRES_DB", "myapp")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5000")

# Build the SQLAlchemy database URL
DATABASE_URL = (
    f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@localhost:{POSTGRES_PORT}/{POSTGRES_DB}"
)

logger.info("Connecting to database at localhost:%s/%s", POSTGRES_PORT, POSTGRES_DB)

engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# PUBLIC_INTERFACE
def get_db():
    """
    Dependency that provides a database session.

    Yields a SQLAlchemy session and ensures it is closed after use.
    Used as a FastAPI dependency injection.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
