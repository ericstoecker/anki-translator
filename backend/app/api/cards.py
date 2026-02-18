from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.card import Card, CardStatus
from app.models.user import User
from app.schemas.cards import CardCreate, CardResponse, CardUpdate

router = APIRouter(prefix="/cards", tags=["cards"])


@router.get("", response_model=list[CardResponse])
async def list_cards(
    deck_id: str | None = None,
    card_status: CardStatus | None = Query(None, alias="status"),
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Card).where(Card.user_id == user.id)
    if deck_id:
        query = query.where(Card.deck_id == deck_id)
    if card_status:
        query = query.where(Card.status == card_status)
    query = query.order_by(Card.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("", response_model=CardResponse, status_code=status.HTTP_201_CREATED)
async def create_card(
    body: CardCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    card = Card(
        deck_id=body.deck_id,
        note_type_id=body.note_type_id,
        user_id=user.id,
        fields=body.fields,
        tags=body.tags,
        source_word=body.source_word,
        source_language=body.source_language,
        target_language=body.target_language,
        status=CardStatus.DRAFT,
    )
    db.add(card)
    await db.commit()
    await db.refresh(card)
    return card


@router.get("/{card_id}", response_model=CardResponse)
async def get_card(
    card_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Card).where(Card.id == card_id, Card.user_id == user.id)
    )
    card = result.scalar_one_or_none()
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return card


@router.patch("/{card_id}", response_model=CardResponse)
async def update_card(
    card_id: str,
    body: CardUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Card).where(Card.id == card_id, Card.user_id == user.id)
    )
    card = result.scalar_one_or_none()
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if body.fields is not None:
        card.fields = body.fields
    if body.tags is not None:
        card.tags = body.tags
    if body.status is not None:
        card.status = body.status
    db.add(card)
    await db.commit()
    await db.refresh(card)
    return card


@router.post("/{card_id}/accept", response_model=CardResponse)
async def accept_card(
    card_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Card).where(Card.id == card_id, Card.user_id == user.id)
    )
    card = result.scalar_one_or_none()
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if card.status != CardStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Card is not in draft status",
        )
    card.status = CardStatus.PENDING_SYNC
    db.add(card)
    await db.commit()
    await db.refresh(card)
    return card


@router.delete("/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_card(
    card_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Card).where(Card.id == card_id, Card.user_id == user.id)
    )
    card = result.scalar_one_or_none()
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    card.status = CardStatus.DELETED
    db.add(card)
    await db.commit()
