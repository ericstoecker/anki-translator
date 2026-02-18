from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import get_current_user
from app.database import get_db
from app.models.deck import Deck, NoteType
from app.models.user import User
from app.schemas.decks import DeckResponse, DeckUpdate, NoteTypeResponse

router = APIRouter(prefix="/decks", tags=["decks"])


@router.get("", response_model=list[DeckResponse])
async def list_decks(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Deck).where(Deck.user_id == user.id))
    return result.scalars().all()


@router.get("/{deck_id}", response_model=DeckResponse)
async def get_deck(
    deck_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Deck).where(Deck.id == deck_id, Deck.user_id == user.id)
    )
    deck = result.scalar_one_or_none()
    if deck is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return deck


@router.patch("/{deck_id}", response_model=DeckResponse)
async def update_deck(
    deck_id: str,
    body: DeckUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Deck).where(Deck.id == deck_id, Deck.user_id == user.id)
    )
    deck = result.scalar_one_or_none()
    if deck is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if body.source_language is not None:
        deck.source_language = body.source_language
    if body.target_language is not None:
        deck.target_language = body.target_language
    db.add(deck)
    await db.commit()
    await db.refresh(deck)
    return deck


@router.get("/{deck_id}/note-types", response_model=list[NoteTypeResponse])
async def list_note_types(
    deck_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify deck ownership
    deck_result = await db.execute(
        select(Deck).where(Deck.id == deck_id, Deck.user_id == user.id)
    )
    if deck_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    result = await db.execute(
        select(NoteType)
        .where(NoteType.deck_id == deck_id)
        .options(selectinload(NoteType.fields))
    )
    return result.scalars().all()
