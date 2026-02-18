from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, cards, decks, duplicates, ocr, sync, translate
from app.database import engine
from app.models import Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="Anki Translator", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(ocr.router)
app.include_router(translate.router)
app.include_router(cards.router)
app.include_router(decks.router)
app.include_router(sync.router)
app.include_router(duplicates.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
