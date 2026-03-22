from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampedMixin


class ChatThread(TimestampedMixin, Base):
    __tablename__ = "chat_threads"

    title: Mapped[str] = mapped_column(String(255), nullable=False)

    messages = relationship("ChatMessage", back_populates="thread", cascade="all, delete-orphan")
