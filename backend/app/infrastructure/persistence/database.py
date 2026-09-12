from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def create_session_factory(database_url: str) -> sessionmaker[Session]:
    connect_args = (
        {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    )
    engine = create_engine(
        database_url,
        connect_args=connect_args,
        pool_pre_ping=True,
    )
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def session_scope(factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    session = factory()
    try:
        yield session
    finally:
        session.close()
