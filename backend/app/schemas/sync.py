from pydantic import BaseModel


class SyncPullResponse(BaseModel):
    cards: list[dict]


class SyncConfirmItem(BaseModel):
    backend_id: str
    anki_note_id: int


class SyncConfirmRequest(BaseModel):
    items: list[SyncConfirmItem]


class SyncPushCard(BaseModel):
    anki_note_id: int
    anki_deck_id: int
    anki_model_id: int
    fields: dict[str, str]
    tags: str = ""


class SyncPushRequest(BaseModel):
    cards: list[SyncPushCard]


class DeckSyncData(BaseModel):
    anki_deck_id: int
    name: str


class NoteTypeFieldSyncData(BaseModel):
    name: str
    ordinal: int


class NoteTypeSyncData(BaseModel):
    anki_model_id: int
    anki_deck_id: int | None = None
    name: str
    css: str | None = None
    card_template_front: str | None = None
    card_template_back: str | None = None
    fields: list[NoteTypeFieldSyncData]


class TemplateSyncRequest(BaseModel):
    decks: list[DeckSyncData]
    note_types: list[NoteTypeSyncData]
