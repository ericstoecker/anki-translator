from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.auth import hash_password
from app.database import get_db
from app.main import app
from app.models import Base
from app.models.user import User

TEST_DB_URL = "sqlite+aiosqlite://"

engine = create_async_engine(
    TEST_DB_URL,
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
test_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db():
    async with test_session() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
async def db():
    async with test_session() as session:
        yield session


# --- User fixture (ORM — no user-creation API exists) ---


@pytest.fixture
async def test_user(db: AsyncSession):
    user = User(
        id="test-user-id",
        username="testuser",
        hashed_password=hash_password("testpass"),
        native_language="English",
    )
    db.add(user)
    await db.commit()
    return user


# --- Auth fixtures (API-driven) ---


@pytest.fixture
async def auth_token(client, test_user):
    resp = await client.post(
        "/auth/login",
        json={"username": "testuser", "password": "testpass"},
    )
    return resp.json()["access_token"]


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


# --- HTTP client ---


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# --- Synced templates fixture (API-driven via POST /sync/templates) ---


@pytest.fixture
async def synced_templates(client, auth_headers):
    """Create a deck + note type via the sync API (the production path)."""
    resp = await client.post(
        "/sync/templates",
        json={
            "decks": [{"anki_deck_id": 1234567890, "name": "Test Deck"}],
            "note_types": [
                {
                    "anki_model_id": 9876543210,
                    "anki_deck_id": 1234567890,
                    "name": "Basic",
                    "css": ".card { font-family: arial; }",
                    "card_template_front": "{{Front}}",
                    "card_template_back": "{{Back}}",
                    "fields": [
                        {"name": "Front", "ordinal": 0},
                        {"name": "Back", "ordinal": 1},
                    ],
                }
            ],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200

    # Discover created IDs via the API
    decks_resp = await client.get("/decks", headers=auth_headers)
    deck = next(d for d in decks_resp.json() if d["anki_deck_id"] == 1234567890)
    deck_id = deck["id"]

    nt_resp = await client.get(f"/decks/{deck_id}/note-types", headers=auth_headers)
    note_type = nt_resp.json()[0]
    note_type_id = note_type["id"]

    return {"deck_id": deck_id, "note_type_id": note_type_id}


# --- Boundary mock: Anthropic SDK ---


@pytest.fixture
def mock_anthropic():
    """Mock anthropic.AsyncAnthropic at the SDK boundary.

    Usage:
        set_response("json string")           — single response
        set_responses(["r1", "r2"])            — sequential responses
    """
    responses = []
    call_index = {"i": 0}

    def set_response(text):
        responses.clear()
        responses.append(text)
        call_index["i"] = 0

    def set_responses(texts):
        responses.clear()
        responses.extend(texts)
        call_index["i"] = 0

    mock_message_create = AsyncMock()

    async def _create_side_effect(**kwargs):
        idx = call_index["i"]
        call_index["i"] += 1
        text = responses[idx] if idx < len(responses) else responses[-1]
        content_block = MagicMock()
        content_block.text = text
        message = MagicMock()
        message.content = [content_block]
        return message

    mock_message_create.side_effect = _create_side_effect

    mock_client_instance = MagicMock()
    mock_client_instance.messages = MagicMock()
    mock_client_instance.messages.create = mock_message_create

    with patch("anthropic.AsyncAnthropic", return_value=mock_client_instance):
        yield {
            "set_response": set_response,
            "set_responses": set_responses,
            "create_mock": mock_message_create,
        }


# --- Boundary mock: SentenceTransformer ---


@pytest.fixture
def mock_embeddings():
    """Mock sentence_transformers.SentenceTransformer at the SDK boundary."""
    import app.services.duplicate_service as dup_mod

    saved_model = dup_mod._embedding_model

    mock_model = MagicMock()
    # Return a fixed-length embedding vector; tests can override via mock_model.encode
    import numpy as np

    mock_model.encode.side_effect = lambda text, **kw: (
        np.random.default_rng(hash(text) % 2**32).random(384).astype(np.float32)
    )

    dup_mod._embedding_model = mock_model

    with patch("sentence_transformers.SentenceTransformer", return_value=mock_model):
        yield mock_model

    dup_mod._embedding_model = saved_model


# --- Helper to create a card via the API ---


async def create_card_via_api(client, auth_headers, deck_id, note_type_id, fields):
    """Create a draft card via POST /cards and return the response JSON."""
    resp = await client.post(
        "/cards",
        json={
            "deck_id": deck_id,
            "note_type_id": note_type_id,
            "fields": fields,
            "source_word": list(fields.values())[0],
            "source_language": "German",
            "target_language": "English",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return resp.json()


async def accept_card_via_api(client, auth_headers, card_id):
    """Accept a card via POST /cards/{id}/accept and return the response JSON."""
    resp = await client.post(f"/cards/{card_id}/accept", headers=auth_headers)
    assert resp.status_code == 200
    return resp.json()


async def confirm_card_via_api(client, auth_headers, card_id, anki_note_id=12345):
    """Confirm a card sync via POST /sync/confirm and return the response JSON."""
    resp = await client.post(
        "/sync/confirm",
        json={"items": [{"backend_id": card_id, "anki_note_id": anki_note_id}]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    return resp.json()
