from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, generate_uuid


class Deck(Base, TimestampMixin):
    __tablename__ = "decks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    anki_deck_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, unique=True
    )
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(255))
    source_language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    target_language: Mapped[str | None] = mapped_column(String(50), nullable=True)

    note_types: Mapped[list["NoteType"]] = relationship(back_populates="deck")


class NoteType(Base, TimestampMixin):
    __tablename__ = "note_types"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    anki_model_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, unique=True
    )
    deck_id: Mapped[str] = mapped_column(String(36), ForeignKey("decks.id"))
    name: Mapped[str] = mapped_column(String(255))
    css: Mapped[str | None] = mapped_column(Text, nullable=True)
    card_template_front: Mapped[str | None] = mapped_column(Text, nullable=True)
    card_template_back: Mapped[str | None] = mapped_column(Text, nullable=True)

    deck: Mapped["Deck"] = relationship(back_populates="note_types")
    fields: Mapped[list["NoteTypeField"]] = relationship(
        back_populates="note_type", order_by="NoteTypeField.ordinal"
    )


class NoteTypeField(Base):
    __tablename__ = "note_type_fields"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    note_type_id: Mapped[str] = mapped_column(String(36), ForeignKey("note_types.id"))
    name: Mapped[str] = mapped_column(String(255))
    ordinal: Mapped[int] = mapped_column(Integer)

    note_type: Mapped["NoteType"] = relationship(back_populates="fields")
