from datetime import datetime

from pydantic import BaseModel

from app.models.card import CardSource, CardStatus


class CardCreate(BaseModel):
    deck_id: str
    note_type_id: str
    fields: dict[str, str]
    tags: str = ""
    source_word: str | None = None
    source_language: str | None = None
    target_language: str | None = None


class CardUpdate(BaseModel):
    fields: dict[str, str] | None = None
    tags: str | None = None
    status: CardStatus | None = None


class CardResponse(BaseModel):
    id: str
    anki_note_id: int | None
    deck_id: str
    note_type_id: str
    fields: dict[str, str]
    tags: str
    status: CardStatus
    source: CardSource
    source_word: str | None
    source_language: str | None
    target_language: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
