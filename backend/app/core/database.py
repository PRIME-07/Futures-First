from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

# PostgreSQL Setup (Sync) — Local staging DB for user-uploaded CSV/Excel files
# We use sync SQLAlchemy with run_in_executor to not block the async event loop
engine = create_engine(settings.POSTGRES_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# MongoDB Setup (Async)
mongo_client = AsyncIOMotorClient(settings.MONGO_URL)
mongo_db = mongo_client[settings.MONGO_DB]

def get_mongo_db():
    return mongo_db


# External Database Engine Factory (Ephemeral, Session-Scoped)

_DIALECT_MAP = {
    "postgresql": "postgresql",
    "mysql": "mysql+pymysql",
    "sqlite": "sqlite",
}


def build_connection_url(db_type: str, host: str = None, port: int = None,
                         username: str = None, password: str = None,
                         database_name: str = None) -> str:
    """
    Build a SQLAlchemy connection URL from structured credentials.
    Supports postgresql, mysql, and sqlite.
    """
    dialect = _DIALECT_MAP.get(db_type)
    if not dialect:
        raise ValueError(f"Unsupported db_type '{db_type}'. Supported: {list(_DIALECT_MAP.keys())}")

    if db_type == "sqlite":
        # SQLite uses a file path as the database_name
        return f"sqlite:///{database_name}" if database_name else "sqlite://"

    # Network databases (PostgreSQL, MySQL)
    creds = ""
    if username:
        creds = username
        if password:
            creds += f":{password}"
        creds += "@"

    host_part = host or "localhost"
    if port:
        host_part += f":{port}"

    return f"{dialect}://{creds}{host_part}/{database_name or ''}"


def create_external_engine(db_type: str, host: str = None, port: int = None,
                           username: str = None, password: str = None,
                           database_name: str = None):
    """
    Create a lightweight, ephemeral SQLAlchemy engine for an external database.
    These engines are NOT globally cached — they are created on demand and
    should be disposed after use.
    """
    url = build_connection_url(db_type, host, port, username, password, database_name)
    return create_engine(url, pool_pre_ping=True)
