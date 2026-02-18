from pydantic import BaseModel


class DeckResponse(BaseModel):
    id: str
    anki_deck_id: int | None
    name: str
    source_language: str | None
    target_language: str | None

    model_config = {"from_attributes": True}


class DeckUpdate(BaseModel):
    source_language: str | None = None
    target_language: str | None = None


class NoteTypeFieldResponse(BaseModel):
    id: str
    name: str
    ordinal: int

    model_config = {"from_attributes": True}


class NoteTypeResponse(BaseModel):
    id: str
    anki_model_id: int | None
    name: str
    css: str | None
    card_template_front: str | None
    card_template_back: str | None
    fields: list[NoteTypeFieldResponse]

    model_config = {"from_attributes": True}
