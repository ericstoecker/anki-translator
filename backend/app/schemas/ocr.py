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


class TranslationOption(BaseModel):
    word: str
    translation: str
    part_of_speech: str | None = None
    context: str | None = None
    native_translation: str | None = None


class TranslateResponse(BaseModel):
    translations: list[TranslationOption]


class FormatCardRequest(BaseModel):
    deck_id: str
    word: str
    translation: str
    part_of_speech: str | None = None
    context: str | None = None
    native_language: str | None = None
