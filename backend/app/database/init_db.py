from backend.app.database.base import Base
from backend.app.database.session import engine
from backend.app.database import models  # noqa: F401


def init_database() -> None:
    Base.metadata.create_all(bind=engine)
