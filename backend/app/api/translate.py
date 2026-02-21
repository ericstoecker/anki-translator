import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.models.card import Card, CardStatus
from app.models.deck import Deck, NoteType
from app.models.user import User
from app.schemas.ocr import (
    FormatCardRequest,
    TranslateRequest,
    TranslateResponse,
    TranslationOption,
)
from app.services.llm_service import format_card_fields, translate_native, translate_word

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/translate", tags=["translate"])


@router.post("", response_model=TranslateResponse)
async def translate(
    body: TranslateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return 1-3 translation options for a word. No card formatting."""
    source_lang = body.source_language
    target_lang = body.target_language
    if body.deck_id and (not source_lang or not target_lang):
        deck_result = await db.execute(
            select(Deck).where(Deck.id == body.deck_id, Deck.user_id == user.id)
        )
        deck = deck_result.scalar_one_or_none()
        if deck:
            source_lang = source_lang or deck.source_language or ""
            target_lang = target_lang or deck.target_language or ""

    native_lang = body.native_language or user.native_language
    try:
        results = await translate_word(
            word=body.word,
            source_language=source_lang,
            target_language=target_lang,
            native_language=native_lang,
        )
    except Exception as e:
        logger.exception("Translation failed")
        raise HTTPException(status_code=502, detail=f"Translation service error: {e}")

    translations = [
        TranslationOption(
            word=r.get("word", body.word),
            translation=r.get("translation", ""),
            part_of_speech=r.get("part_of_speech"),
            context=r.get("context"),
            native_translation=r.get("native_translation"),
        )
        for r in results
    ]
    return TranslateResponse(translations=translations)


@router.post("/format-card")
async def format_card(
    body: FormatCardRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Format a card using the chosen translation. No re-translation."""
    # Resolve languages from deck
    deck_result = await db.execute(
        select(Deck).where(Deck.id == body.deck_id, Deck.user_id == user.id)
    )
    deck = deck_result.scalar_one_or_none()
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")

    source_lang = deck.source_language or ""
    target_lang = deck.target_language or ""

    # Get the note type and its field names
    result = await db.execute(
        select(NoteType)
        .where(NoteType.deck_id == body.deck_id)
        .options(selectinload(NoteType.fields))
        .limit(1)
    )
    note_type = result.scalar_one_or_none()
    if not note_type:
        raise HTTPException(status_code=404, detail="No note type found for this deck")

    field_names = [f.name for f in note_type.fields]

    # Get example cards for style derivation
    card_result = await db.execute(
        select(Card)
        .where(
            Card.deck_id == body.deck_id,
            Card.user_id == user.id,
            Card.status != CardStatus.DELETED,
        )
        .order_by(Card.created_at.desc())
        .limit(settings.card_example_count)
    )
    example_cards = [{"fields": c.fields} for c in card_result.scalars().all()]

    # Get native translation if requested
    native_translation = None
    if body.native_language:
        try:
            native_translation = await translate_native(
                word=body.word,
                source_language=source_lang,
                native_language=body.native_language,
            )
        except Exception:
            logger.exception("Native translation failed")
            # Non-fatal — continue without native translation

    try:
        formatted = await format_card_fields(
            word=body.word,
            translation=body.translation,
            field_names=field_names,
            example_cards=example_cards,
            source_language=source_lang,
            target_language=target_lang,
            part_of_speech=body.part_of_speech,
            native_translation=native_translation,
            context=body.context,
        )
    except Exception as e:
        logger.exception("Card formatting failed")
        raise HTTPException(status_code=502, detail=f"LLM service error: {e}")

    return {
        "note_type_id": note_type.id,
        "fields": formatted,
    }
