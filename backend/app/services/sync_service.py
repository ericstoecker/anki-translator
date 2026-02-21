from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.card import Card, CardSource, CardStatus
from app.models.deck import Deck, NoteType, NoteTypeField
from app.schemas.sync import (
    SyncConfirmItem,
    SyncPushCard,
    TemplateSyncRequest,
)


async def sync_templates(
    data: TemplateSyncRequest, user_id: str, db: AsyncSession
) -> dict:
    deck_map: dict[int, str] = {}  # anki_deck_id -> backend deck id

    # Upsert decks
    for deck_data in data.decks:
        result = await db.execute(
            select(Deck).where(
                Deck.anki_deck_id == deck_data.anki_deck_id,
                Deck.user_id == user_id,
            )
        )
        deck = result.scalar_one_or_none()
        if deck is None:
            deck = Deck(
                anki_deck_id=deck_data.anki_deck_id,
                user_id=user_id,
                name=deck_data.name,
            )
            db.add(deck)
            await db.flush()
        else:
            deck.name = deck_data.name
        deck_map[deck_data.anki_deck_id] = deck.id

    # Upsert note types
    for nt_data in data.note_types:
        if nt_data.anki_deck_id is None:
            continue
        backend_deck_id = deck_map.get(nt_data.anki_deck_id)
        if not backend_deck_id:
            continue

        result = await db.execute(
            select(NoteType).where(NoteType.anki_model_id == nt_data.anki_model_id)
        )
        note_type = result.scalar_one_or_none()
        if note_type is None:
            note_type = NoteType(
                anki_model_id=nt_data.anki_model_id,
                deck_id=backend_deck_id,
                name=nt_data.name,
                css=nt_data.css,
                card_template_front=nt_data.card_template_front,
                card_template_back=nt_data.card_template_back,
            )
            db.add(note_type)
            await db.flush()
        else:
            note_type.deck_id = backend_deck_id
            note_type.name = nt_data.name
            note_type.css = nt_data.css
            note_type.card_template_front = nt_data.card_template_front
            note_type.card_template_back = nt_data.card_template_back

        # Upsert fields - delete existing and recreate
        result = await db.execute(
            select(NoteTypeField).where(NoteTypeField.note_type_id == note_type.id)
        )
        for existing_field in result.scalars().all():
            await db.delete(existing_field)

        for field_data in nt_data.fields:
            field = NoteTypeField(
                note_type_id=note_type.id,
                name=field_data.name,
                ordinal=field_data.ordinal,
            )
            db.add(field)

    await db.commit()
    return {"status": "ok", "decks_synced": len(data.decks)}


async def pull_cards(
    user_id: str, since: datetime | None, db: AsyncSession
) -> list[dict]:
    query = select(Card).where(
        Card.user_id == user_id,
        Card.source == CardSource.APP,
        Card.status == CardStatus.PENDING_SYNC,
    )
    if since:
        query = query.where(Card.updated_at >= since)

    result = await db.execute(query)
    cards = result.scalars().all()

    return [
        {
            "id": card.id,
            "deck_id": card.deck_id,
            "note_type_id": card.note_type_id,
            "fields": card.fields,
            "tags": card.tags,
        }
        for card in cards
    ]


async def confirm_sync(
    items: list[SyncConfirmItem], user_id: str, db: AsyncSession
) -> dict:
    confirmed = 0
    for item in items:
        result = await db.execute(
            select(Card).where(Card.id == item.backend_id, Card.user_id == user_id)
        )
        card = result.scalar_one_or_none()
        if card:
            card.anki_note_id = item.anki_note_id
            card.status = CardStatus.SYNCED
            confirmed += 1

    await db.commit()
    return {"confirmed": confirmed}


async def push_cards(
    cards_data: list[SyncPushCard], user_id: str, db: AsyncSession
) -> dict:
    created = 0
    updated = 0

    for card_data in cards_data:
        # Check if card already exists by anki_note_id
        result = await db.execute(
            select(Card).where(
                Card.anki_note_id == card_data.anki_note_id,
                Card.user_id == user_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.fields = card_data.fields
            existing.tags = card_data.tags
            existing.status = CardStatus.SYNCED
            updated += 1
        else:
            # Find the backend deck and note type by anki IDs
            deck_result = await db.execute(
                select(Deck).where(
                    Deck.anki_deck_id == card_data.anki_deck_id,
                    Deck.user_id == user_id,
                )
            )
            deck = deck_result.scalar_one_or_none()
            if not deck:
                continue

            nt_result = await db.execute(
                select(NoteType).where(
                    NoteType.anki_model_id == card_data.anki_model_id
                )
            )
            note_type = nt_result.scalar_one_or_none()
            if not note_type:
                continue

            card = Card(
                anki_note_id=card_data.anki_note_id,
                deck_id=deck.id,
                note_type_id=note_type.id,
                user_id=user_id,
                fields=card_data.fields,
                tags=card_data.tags,
                status=CardStatus.SYNCED,
                source=CardSource.ANKI,
            )
            db.add(card)
            created += 1

    await db.commit()
    return {"created": created, "updated": updated}
