from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.sync import (
    SyncConfirmRequest,
    SyncPullResponse,
    SyncPushRequest,
    TemplateSyncRequest,
)
from app.services.sync_service import (
    confirm_sync,
    pull_cards,
    push_cards,
    sync_templates,
)

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/templates")
async def upload_templates(
    body: TemplateSyncRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await sync_templates(body, user.id, db)


@router.get("/pull", response_model=SyncPullResponse)
async def pull(
    since: datetime | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cards = await pull_cards(user.id, since, db)
    return SyncPullResponse(cards=cards)


@router.post("/confirm")
async def confirm(
    body: SyncConfirmRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await confirm_sync(body.items, user.id, db)


@router.post("/push")
async def push(
    body: SyncPushRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await push_cards(body.cards, user.id, db)
