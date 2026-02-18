import enum

from sqlalchemy import BigInteger, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.models.base import Base, TimestampMixin, generate_uuid


class CardStatus(str, enum.Enum):
    DRAFT = "draft"  # user hasn't accepted yet
    PENDING_SYNC = "pending_sync"  # accepted, waiting for Anki sync
    SYNCED = "synced"
    MODIFIED = "modified"  # modified after last sync
    DELETED = "deleted"


class CardSource(str, enum.Enum):
    APP = "app"  # created via phone app
    ANKI = "anki"  # created in Anki, synced to backend


class Card(Base, TimestampMixin):
    __tablename__ = "cards"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    anki_note_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    deck_id: Mapped[str] = mapped_column(String(36), ForeignKey("decks.id"))
    note_type_id: Mapped[str] = mapped_column(String(36), ForeignKey("note_types.id"))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))

    fields: Mapped[dict] = mapped_column(JSON, default=dict)
    tags: Mapped[str] = mapped_column(Text, default="")

    status: Mapped[str] = mapped_column(String(20), default=CardStatus.DRAFT.value)
    source: Mapped[str] = mapped_column(String(10), default=CardSource.APP.value)

    source_word: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    target_language: Mapped[str | None] = mapped_column(String(50), nullable=True)

    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)
