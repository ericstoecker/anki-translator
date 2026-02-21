from tests.conftest import (
    accept_card_via_api,
    confirm_card_via_api,
    create_card_via_api,
)


class TestTemplateSync:
    async def test_when_upload_templates_then_deck_created(self, client, auth_headers):
        resp = await client.post(
            "/sync/templates",
            json={
                "decks": [{"anki_deck_id": 999, "name": "New Deck"}],
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
                    }
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

    async def test_given_existing_deck_when_upload_templates_then_updates(
        self, client, auth_headers, synced_templates
    ):
        # Upload again with updated name (same anki_deck_id)
        resp = await client.post(
            "/sync/templates",
            json={
                "decks": [{"anki_deck_id": 1234567890, "name": "Updated Name"}],
                "note_types": [],
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200

        deck_resp = await client.get("/decks", headers=auth_headers)
        deck = next(d for d in deck_resp.json() if d["anki_deck_id"] == 1234567890)
        assert deck["name"] == "Updated Name"


class TestPullPush:
    async def test_given_pending_card_when_pull_then_returns_it(
        self, client, auth_headers, synced_templates
    ):
        card = await create_card_via_api(
            client,
            auth_headers,
            synced_templates["deck_id"],
            synced_templates["note_type_id"],
            {"Front": "Hund", "Back": "dog"},
        )
        await accept_card_via_api(client, auth_headers, card["id"])

        resp = await client.get("/sync/pull", headers=auth_headers)
        assert resp.status_code == 200
        cards = resp.json()["cards"]
        assert len(cards) == 1
        assert cards[0]["id"] == card["id"]

    async def test_given_synced_card_when_pull_then_excludes_it(
        self, client, auth_headers, synced_templates
    ):
        card = await create_card_via_api(
            client,
            auth_headers,
            synced_templates["deck_id"],
            synced_templates["note_type_id"],
            {"Front": "already", "Back": "synced"},
        )
        await accept_card_via_api(client, auth_headers, card["id"])
        await confirm_card_via_api(client, auth_headers, card["id"])

        resp = await client.get("/sync/pull", headers=auth_headers)
        assert resp.json()["cards"] == []

    async def test_when_confirm_sync_then_card_marked_synced(
        self, client, auth_headers, synced_templates
    ):
        card = await create_card_via_api(
            client,
            auth_headers,
            synced_templates["deck_id"],
            synced_templates["note_type_id"],
            {"Front": "test", "Back": "test"},
        )
        await accept_card_via_api(client, auth_headers, card["id"])

        resp = await client.post(
            "/sync/confirm",
            json={"items": [{"backend_id": card["id"], "anki_note_id": 12345}]},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["confirmed"] == 1

        # Verify status changed
        card_resp = await client.get(f"/cards/{card['id']}", headers=auth_headers)
        assert card_resp.json()["status"] == "synced"
        assert card_resp.json()["anki_note_id"] == 12345

    async def test_when_push_new_card_then_creates_it(
        self, client, auth_headers, synced_templates
    ):
        resp = await client.post(
            "/sync/push",
            json={
                "cards": [
                    {
                        "anki_note_id": 99999,
                        "anki_deck_id": 1234567890,
                        "anki_model_id": 9876543210,
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

    async def test_given_existing_card_when_push_then_updates_it(
        self, client, auth_headers, synced_templates
    ):
        # Push a card first (creates it via Anki sync path)
        await client.post(
            "/sync/push",
            json={
                "cards": [
                    {
                        "anki_note_id": 77777,
                        "anki_deck_id": 1234567890,
                        "anki_model_id": 9876543210,
                        "fields": {"Front": "old", "Back": "old"},
                    }
                ],
            },
            headers=auth_headers,
        )

        # Push again with updated fields
        resp = await client.post(
            "/sync/push",
            json={
                "cards": [
                    {
                        "anki_note_id": 77777,
                        "anki_deck_id": 1234567890,
                        "anki_model_id": 9876543210,
                        "fields": {"Front": "updated", "Back": "updated"},
                    }
                ],
            },
            headers=auth_headers,
        )
        assert resp.json()["updated"] == 1
