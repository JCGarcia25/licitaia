"""Sesión de base de datos (SQLAlchemy, soporta Postgres y SQLite para pruebas)."""
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine():
    settings = get_settings()
    url = settings.database_url
    kwargs: dict = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **kwargs)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    """Dependencia FastAPI: sesión por petición."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Crea el esquema (equivalente a la primera migración; en producción usar Alembic)."""
    from app.db import models  # noqa: F401  (registro de modelos)

    Base.metadata.create_all(bind=engine)
    # Older deployments may have been created with migration 0001 before the
    # SaaS/SECOP fields were added. Alembic's create_all does not alter existing
    # tables, so add missing nullable/defaulted columns at startup as a safe
    # compatibility step. This prevents auth and listings from failing with a
    # database-level "column does not exist" 500 during rolling deployments.
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in inspector.get_table_names():
                continue
            existing = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing:
                    continue
                col_type = column.type.compile(dialect=engine.dialect)
                nullable = "NULL"
                # New model fields are nullable/defaulted; avoid server-side
                # defaults here because SQLAlchemy applies model defaults.
                conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {col_type} {nullable}'))
