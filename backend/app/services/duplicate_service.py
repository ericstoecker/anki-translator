import logging

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.card import Card, CardStatus
from app.services.llm_service import check_semantic_duplicate

logger = logging.getLogger(__name__)

_embedding_model = None


def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer

        _embedding_model = SentenceTransformer(settings.embedding_model)
    return _embedding_model


def compute_embedding(text: str) -> list[float]:
    model = _get_embedding_model()
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def _card_text(card: Card) -> str:
    """Extract searchable text from a card's fields."""
    return " ".join(str(v) for v in card.fields.values() if v)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    a_arr = np.array(a)
    b_arr = np.array(b)
    return float(np.dot(a_arr, b_arr) / (np.linalg.norm(a_arr) * np.linalg.norm(b_arr)))


async def find_duplicates(
    word: str,
    deck_id: str,
    user_id: str,
    source_language: str,
    db: AsyncSession,
) -> dict | None:
    # Get all non-deleted cards in this deck
    result = await db.execute(
        select(Card).where(
            Card.deck_id == deck_id,
            Card.user_id == user_id,
            Card.status != CardStatus.DELETED,
        )
    )
    existing_cards = result.scalars().all()
    if not existing_cards:
        return None

    # Compute embedding for the new word
    word_embedding = compute_embedding(word)

    # Compute missing embeddings and score each card
    candidates = []
    for card in existing_cards:
        if not card.embedding:
            card_text = _card_text(card)
            if card_text:
                card.embedding = compute_embedding(card_text)
                db.add(card)

        if card.embedding:
            sim = cosine_similarity(word_embedding, card.embedding)
            if sim >= settings.duplicate_embedding_threshold:
                candidates.append(
                    {
                        "id": card.id,
                        "fields": card.fields,
                        "similarity": sim,
                    }
                )

    # Persist any newly computed embeddings
    await db.commit()

    if not candidates:
        return None

    # Sort by similarity, take top N for LLM confirmation
    candidates.sort(key=lambda x: x["similarity"], reverse=True)
    top_candidates = candidates[: settings.duplicate_llm_candidates]

    return await check_semantic_duplicate(word, top_candidates, source_language)
