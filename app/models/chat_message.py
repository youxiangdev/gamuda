from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampedMixin


class ChatMessage(TimestampedMixin, Base):
    __tablename__ = "chat_messages"

    thread_id: Mapped[str] = mapped_column(ForeignKey("chat_threads.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="completed")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")

    thread = relationship("ChatThread", back_populates="messages")

