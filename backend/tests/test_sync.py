import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.card import Card, CardSource, CardStatus
from app.models.deck import Deck, NoteType, NoteTypeField


@pytest.fixture
async def synced_deck(db: AsyncSession, test_user):
    deck = Deck(
        id="sync-deck",
        anki_deck_id=111,
        user_id=test_user.id,
        name="Sync Test Deck",
    )
    db.add(deck)

    nt = NoteType(
        id="sync-nt",
        anki_model_id=222,
        deck_id=deck.id,
        name="Basic",
    )
    db.add(nt)
    await db.flush()

    for i, name in enumerate(["Front", "Back"]):
        db.add(NoteTypeField(note_type_id=nt.id, name=name, ordinal=i))

    await db.commit()
    return deck, nt


class TestTemplateSync:
    async def test_upload_templates(self, client, test_user, auth_headers):
        resp = await client.post(
            "/sync/templates",
            json={
                "decks": [
                    {"anki_deck_id": 999, "name": "New Deck"},
                ],
                "note_types": [
                    {
                        "anki_model_id": 888,
                        "anki_deck_id": 999,
                        "name": "Basic-new",
                        "css": ".card {}",
                        "card_template_front": "{{Front}}",
                        "card_template_back": "{{Back}}",
                        "fields": [
                            {"name": "Front", "ordinal": 0},
                            {"name": "Back", "ordinal": 1},
                        ],
                    },
                ],
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["decks_synced"] == 1

        # Verify deck was created
        deck_resp = await client.get("/decks", headers=auth_headers)
        names = [d["name"] for d in deck_resp.json()]
        assert "New Deck" in names

    async def test_template_upsert(self, client, test_user, auth_headers, synced_deck):
        # Upload again with updated name
        resp = await client.post(
            "/sync/templates",
            json={
                "decks": [{"anki_deck_id": 111, "name": "Updated Name"}],
                "note_types": [],
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200

        deck_resp = await client.get("/decks", headers=auth_headers)
        deck = next(d for d in deck_resp.json() if d["anki_deck_id"] == 111)
        assert deck["name"] == "Updated Name"


class TestPullPush:
    async def test_pull_pending_cards(
        self, client, test_user, auth_headers, synced_deck, db
    ):
        deck, nt = synced_deck
        card = Card(
            id="pull-card",
            deck_id=deck.id,
            note_type_id=nt.id,
            user_id=test_user.id,
            fields={"Front": "Hund", "Back": "dog"},
            status=CardStatus.PENDING_SYNC,
            source=CardSource.APP,
        )
        db.add(card)
        await db.commit()

        resp = await client.get("/sync/pull", headers=auth_headers)
        assert resp.status_code == 200
        cards = resp.json()["cards"]
        assert len(cards) == 1
        assert cards[0]["id"] == "pull-card"

    async def test_pull_excludes_synced(
        self, client, test_user, auth_headers, synced_deck, db
    ):
        deck, nt = synced_deck
        card = Card(
            deck_id=deck.id,
            note_type_id=nt.id,
            user_id=test_user.id,
            fields={"Front": "already", "Back": "synced"},
            status=CardStatus.SYNCED,
            source=CardSource.APP,
        )
        db.add(card)
        await db.commit()

        resp = await client.get("/sync/pull", headers=auth_headers)
        assert resp.json()["cards"] == []

    async def test_confirm_sync(self, client, test_user, auth_headers, synced_deck, db):
        deck, nt = synced_deck
        card = Card(
            id="confirm-card",
            deck_id=deck.id,
            note_type_id=nt.id,
            user_id=test_user.id,
            fields={"Front": "test", "Back": "test"},
            status=CardStatus.PENDING_SYNC,
            source=CardSource.APP,
        )
        db.add(card)
        await db.commit()

        resp = await client.post(
            "/sync/confirm",
            json={
                "items": [{"backend_id": "confirm-card", "anki_note_id": 12345}],
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["confirmed"] == 1

        # Verify status changed
        card_resp = await client.get("/cards/confirm-card", headers=auth_headers)
        assert card_resp.json()["status"] == "synced"
        assert card_resp.json()["anki_note_id"] == 12345

    async def test_push_new_card(self, client, test_user, auth_headers, synced_deck):
        resp = await client.post(
            "/sync/push",
            json={
                "cards": [
                    {
                        "anki_note_id": 99999,
                        "anki_deck_id": 111,
                        "anki_model_id": 222,
                        "fields": {"Front": "Haus", "Back": "house"},
                        "tags": "german",
                    }
                ],
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["created"] == 1

        # Verify card exists
        cards_resp = await client.get("/cards", headers=auth_headers)
        cards = cards_resp.json()
        assert any(c["anki_note_id"] == 99999 for c in cards)

    async def test_push_update_existing(
        self, client, test_user, auth_headers, synced_deck, db
    ):
        deck, nt = synced_deck
        card = Card(
            deck_id=deck.id,
            note_type_id=nt.id,
            user_id=test_user.id,
            anki_note_id=77777,
            fields={"Front": "old", "Back": "old"},
            status=CardStatus.SYNCED,
            source=CardSource.ANKI,
        )
        db.add(card)
        await db.commit()

        resp = await client.post(
            "/sync/push",
            json={
                "cards": [
                    {
                        "anki_note_id": 77777,
                        "anki_deck_id": 111,
                        "anki_model_id": 222,
                        "fields": {"Front": "updated", "Back": "updated"},
                    }
                ],
            },
            headers=auth_headers,
        )
        assert resp.json()["updated"] == 1
