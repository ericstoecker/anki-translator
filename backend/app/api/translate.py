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
from app.schemas.ocr import TranslateRequest, TranslateResponse
from app.services.llm_service import format_card_fields, translate_word

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/translate", tags=["translate"])


@router.post("", response_model=TranslateResponse)
async def translate(
    body: TranslateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Resolve languages from deck if not provided
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

    # Get example cards from the deck for style matching
    example_cards = []
    if body.deck_id:
        result = await db.execute(
            select(Card)
            .where(
                Card.deck_id == body.deck_id,
                Card.user_id == user.id,
                Card.status != CardStatus.DELETED,
            )
            .order_by(Card.created_at.desc())
            .limit(10)
        )
        example_cards = [{"fields": c.fields} for c in result.scalars().all()]

    native_lang = body.native_language or user.native_language
    try:
        result = await translate_word(
            word=body.word,
            source_language=source_lang,
            target_language=target_lang,
            native_language=native_lang,
            example_cards=example_cards,
        )
    except Exception as e:
        logger.exception("Translation failed")
        raise HTTPException(status_code=502, detail=f"Translation service error: {e}")

    return TranslateResponse(
        word=result.get("word", body.word),
        translation=result.get("translation", ""),
        native_translation=result.get("native_translation"),
        part_of_speech=result.get("part_of_speech"),
        context=result.get("context"),
    )


@router.post("/format-card")
async def format_card(
    body: TranslateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate formatted card fields matching deck style."""
    if not body.deck_id:
        return {"error": "deck_id is required for card formatting"}

    # Resolve languages from deck if not provided
    source_lang = body.source_language
    target_lang = body.target_language
    deck_result = await db.execute(
        select(Deck).where(Deck.id == body.deck_id, Deck.user_id == user.id)
    )
    deck = deck_result.scalar_one_or_none()
    if deck:
        source_lang = source_lang or deck.source_language or ""
        target_lang = target_lang or deck.target_language or ""

    # Get the note type and its field names
    result = await db.execute(
        select(NoteType)
        .where(NoteType.deck_id == body.deck_id)
        .options(selectinload(NoteType.fields))
        .limit(1)
    )
    note_type = result.scalar_one_or_none()
    if not note_type:
        return {"error": "No note type found for this deck"}

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

    # First translate
    native_lang = body.native_language or user.native_language
    try:
        translation_result = await translate_word(
            word=body.word,
            source_language=source_lang,
            target_language=target_lang,
            native_language=native_lang,
        )

        # Then format the card fields
        formatted = await format_card_fields(
            word=body.word,
            translation=translation_result.get("translation", ""),
            field_names=field_names,
            example_cards=example_cards,
            source_language=source_lang,
            target_language=target_lang,
            part_of_speech=translation_result.get("part_of_speech"),
            native_translation=translation_result.get("native_translation"),
            context=translation_result.get("context"),
        )
    except Exception as e:
        logger.exception("Card formatting failed")
        raise HTTPException(status_code=502, detail=f"LLM service error: {e}")

    return {
        "note_type_id": note_type.id,
        "fields": formatted,
        "translation": translation_result,
    }
