from functools import lru_cache

from app.core.config import DATA_DIR
from app.repositories import Database, LocalStore
from app.services.plan_processor import PlanProcessor


@lru_cache
def get_store() -> LocalStore:
    return LocalStore(DATA_DIR)


@lru_cache
def get_database() -> Database:
    return Database(DATA_DIR / "goodwe.sqlite3")


@lru_cache
def get_plan_processor() -> PlanProcessor:
    return PlanProcessor()
