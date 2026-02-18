import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.card import Card, CardStatus
from app.models.deck import Deck, NoteType, NoteTypeField


@pytest.fixture
async def deck_and_note_type(db: AsyncSession, test_user):
    deck = Deck(
        id="deck-1",
        anki_deck_id=1234567890,
        user_id=test_user.id,
        name="Test Deck",
        source_language="German",
        target_language="English",
    )
    db.add(deck)

    note_type = NoteType(
        id="nt-1",
        anki_model_id=9876543210,
        deck_id=deck.id,
        name="Basic",
        css=".card { font-family: arial; }",
        card_template_front="{{Front}}",
        card_template_back="{{Back}}",
    )
    db.add(note_type)
    await db.flush()

    for i, name in enumerate(["Front", "Back"]):
        field = NoteTypeField(note_type_id=note_type.id, name=name, ordinal=i)
        db.add(field)

    await db.commit()
    return deck, note_type


class TestCards:
    async def test_create_card(self, client, test_user, auth_headers, deck_and_note_type):
        deck, note_type = deck_and_note_type
        resp = await client.post("/cards", json={
            "deck_id": deck.id,
            "note_type_id": note_type.id,
            "fields": {"Front": "Hund", "Back": "dog"},
            "source_word": "Hund",
            "source_language": "German",
            "target_language": "English",
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["fields"]["Front"] == "Hund"
        assert data["status"] == "draft"

    async def test_list_cards(self, client, test_user, auth_headers, deck_and_note_type, db):
        deck, note_type = deck_and_note_type
        card = Card(
            deck_id=deck.id,
            note_type_id=note_type.id,
            user_id=test_user.id,
            fields={"Front": "Katze", "Back": "cat"},
            status=CardStatus.DRAFT,
        )
        db.add(card)
        await db.commit()

        resp = await client.get("/cards", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    async def test_accept_card(self, client, test_user, auth_headers, deck_and_note_type, db):
        deck, note_type = deck_and_note_type
        card = Card(
            id="card-accept",
            deck_id=deck.id,
            note_type_id=note_type.id,
            user_id=test_user.id,
            fields={"Front": "Haus", "Back": "house"},
            status=CardStatus.DRAFT,
        )
        db.add(card)
        await db.commit()

        resp = await client.post(f"/cards/card-accept/accept", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending_sync"

    async def test_accept_non_draft_fails(self, client, test_user, auth_headers, deck_and_note_type, db):
        deck, note_type = deck_and_note_type
        card = Card(
            id="card-synced",
            deck_id=deck.id,
            note_type_id=note_type.id,
            user_id=test_user.id,
            fields={"Front": "Baum", "Back": "tree"},
            status=CardStatus.SYNCED,
        )
        db.add(card)
        await db.commit()

        resp = await client.post(f"/cards/card-synced/accept", headers=auth_headers)
        assert resp.status_code == 400

    async def test_delete_card(self, client, test_user, auth_headers, deck_and_note_type, db):
        deck, note_type = deck_and_note_type
        card = Card(
            id="card-del",
            deck_id=deck.id,
            note_type_id=note_type.id,
            user_id=test_user.id,
            fields={"Front": "Blume", "Back": "flower"},
            status=CardStatus.DRAFT,
        )
        db.add(card)
        await db.commit()

        resp = await client.delete(f"/cards/card-del", headers=auth_headers)
        assert resp.status_code == 204


class TestDecks:
    async def test_list_decks(self, client, test_user, auth_headers, deck_and_note_type):
        resp = await client.get("/decks", headers=auth_headers)
        assert resp.status_code == 200
        decks = resp.json()
        assert len(decks) == 1
        assert decks[0]["name"] == "Test Deck"

    async def test_update_deck_languages(self, client, test_user, auth_headers, deck_and_note_type):
        deck, _ = deck_and_note_type
        resp = await client.patch(f"/decks/{deck.id}", json={
            "source_language": "French",
            "target_language": "Spanish",
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["source_language"] == "French"

    async def test_get_note_types(self, client, test_user, auth_headers, deck_and_note_type):
        deck, _ = deck_and_note_type
        resp = await client.get(f"/decks/{deck.id}/note-types", headers=auth_headers)
        assert resp.status_code == 200
        nts = resp.json()
        assert len(nts) == 1
        assert nts[0]["name"] == "Basic"
        assert len(nts[0]["fields"]) == 2
