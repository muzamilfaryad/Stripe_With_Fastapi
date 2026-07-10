from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Only echo SQL queries in DEBUG mode to avoid performance issues in production
engine = create_engine(
    settings.DATABASE_URL, 
    echo=settings.DEBUG,
    pool_pre_ping=True,  # Verify connections before using them
    pool_size=5,  # Connection pool size
    max_overflow=10  # Maximum overflow connections
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
