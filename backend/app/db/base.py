# Import Base and all models here so Alembic can detect them.
from app.db.base_class import Base  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.chat import ChatSession, ChatMessage  # noqa: F401
