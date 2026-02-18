from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.duplicate_service import find_duplicates

router = APIRouter(prefix="/duplicates", tags=["duplicates"])


class DuplicateCheckRequest(BaseModel):
    word: str
    deck_id: str
    source_language: str


class DuplicateCheckResponse(BaseModel):
    is_duplicate: bool
    duplicate_of_id: str | None = None
    explanation: str | None = None


@router.post("/check", response_model=DuplicateCheckResponse)
async def check_duplicate(
    body: DuplicateCheckRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await find_duplicates(
        word=body.word,
        deck_id=body.deck_id,
        user_id=user.id,
        source_language=body.source_language,
        db=db,
    )
    if result:
        return DuplicateCheckResponse(
            is_duplicate=True,
            duplicate_of_id=result.get("duplicate_of_id"),
            explanation=result.get("explanation"),
        )
    return DuplicateCheckResponse(is_duplicate=False)
