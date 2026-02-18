from pydantic import BaseModel


class OCRResponse(BaseModel):
    words: list[str]
    raw_text: str


class TranslateRequest(BaseModel):
    word: str
    source_language: str
    target_language: str
    deck_id: str | None = None
    native_language: str | None = None


class TranslateResponse(BaseModel):
    word: str
    translation: str
    native_translation: str | None = None
    part_of_speech: str | None = None
    context: str | None = None
