"""Conexión a Microsoft SQL Server mediante SQLAlchemy y pyodbc.

SQL Server es la única base de datos admitida. No existe sustituto silencioso
con SQLite o PostgreSQL: si la URL no es ``mssql+pyodbc`` se rechaza.
"""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

SUPPORTED_DRIVER = "mssql+pyodbc"


class UnsupportedDatabaseError(ValueError):
    pass


def validate_database_url(url: str) -> None:
    driver = make_url(url).drivername
    if driver != SUPPORTED_DRIVER:
        raise UnsupportedDatabaseError(
            f"Solo se admite SQL Server ({SUPPORTED_DRIVER}); se recibió '{driver}'."
        )


@lru_cache
def get_engine(url: str) -> Engine:
    validate_database_url(url)
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=1800,
        fast_executemany=True,
    )


def get_session_factory(url: str) -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(url), expire_on_commit=False)
