from tests.conftest import (
    accept_card_via_api,
    confirm_card_via_api,
    create_card_via_api,
)


class TestCards:
    async def test_when_create_card_then_returns_draft(
        self, client, auth_headers, synced_templates
    ):
        resp = await client.post(
            "/cards",
            json={
                "deck_id": synced_templates["deck_id"],
                "note_type_id": synced_templates["note_type_id"],
                "fields": {"Front": "Hund", "Back": "dog"},
                "source_word": "Hund",
                "source_language": "German",
                "target_language": "English",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["fields"]["Front"] == "Hund"
        assert data["status"] == "draft"

    async def test_given_one_card_when_list_then_returns_it(
        self, client, auth_headers, synced_templates
    ):
        await create_card_via_api(
            client,
            auth_headers,
            synced_templates["deck_id"],
            synced_templates["note_type_id"],
            {"Front": "Katze", "Back": "cat"},
        )

        resp = await client.get("/cards", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    async def test_when_accept_draft_then_status_pending_sync(
        self, client, auth_headers, synced_templates
    ):
        card = await create_card_via_api(
            client,
            auth_headers,
            synced_templates["deck_id"],
            synced_templates["note_type_id"],
            {"Front": "Haus", "Back": "house"},
        )

        resp = await client.post(f"/cards/{card['id']}/accept", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending_sync"

    async def test_given_synced_card_when_accept_then_returns_400(
        self, client, auth_headers, synced_templates
    ):
        card = await create_card_via_api(
            client,
            auth_headers,
            synced_templates["deck_id"],
            synced_templates["note_type_id"],
            {"Front": "Baum", "Back": "tree"},
        )
        # Accept it first (draft → pending_sync)
        await accept_card_via_api(client, auth_headers, card["id"])
        # Confirm it (pending_sync → synced)
        await confirm_card_via_api(client, auth_headers, card["id"])

        # Now try to accept again — should fail
        resp = await client.post(f"/cards/{card['id']}/accept", headers=auth_headers)
        assert resp.status_code == 400

    async def test_when_delete_card_then_card_is_gone(
        self, client, auth_headers, synced_templates
    ):
        card = await create_card_via_api(
            client,
            auth_headers,
            synced_templates["deck_id"],
            synced_templates["note_type_id"],
            {"Front": "Blume", "Back": "flower"},
        )

        resp = await client.delete(f"/cards/{card['id']}", headers=auth_headers)
        assert resp.status_code == 204

        # Verify card is soft-deleted (status changed to "deleted")
        resp = await client.get(f"/cards/{card['id']}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"


class TestDecks:
    async def test_given_synced_deck_when_list_decks_then_returns_it(
        self, client, auth_headers, synced_templates
    ):
        resp = await client.get("/decks", headers=auth_headers)
        assert resp.status_code == 200
        decks = resp.json()
        assert len(decks) == 1
        assert decks[0]["name"] == "Test Deck"

    async def test_when_update_deck_languages_then_persists(
        self, client, auth_headers, synced_templates
    ):
        resp = await client.patch(
            f"/decks/{synced_templates['deck_id']}",
            json={
                "source_language": "French",
                "target_language": "Spanish",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["source_language"] == "French"

    async def test_given_synced_deck_when_get_note_types_then_returns_them(
        self, client, auth_headers, synced_templates
    ):
        resp = await client.get(
            f"/decks/{synced_templates['deck_id']}/note-types", headers=auth_headers
        )
        assert resp.status_code == 200
        nts = resp.json()
        assert len(nts) == 1
        assert nts[0]["name"] == "Basic"
        assert len(nts[0]["fields"]) == 2
