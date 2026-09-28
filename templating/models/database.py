"""Совместимые импорты; единственные Base и engine находятся в db/."""
from db.base import Base
from db.session import engine, async_session_maker as SessionLocal, get_db
