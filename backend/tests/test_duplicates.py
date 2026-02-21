import json

from tests.conftest import create_card_via_api


class TestDuplicateCheck:
    async def test_given_similar_card_exists_when_check_then_duplicate_detected(
        self,
        client,
        auth_headers,
        synced_templates,
        mock_embeddings,
        mock_anthropic,
    ):
        # Create an existing card
        await create_card_via_api(
            client,
            auth_headers,
            synced_templates["deck_id"],
            synced_templates["note_type_id"],
            {"Front": "to have", "Back": "haben"},
        )

        # Mock: embeddings produce high similarity (handled by mock_embeddings fixture),
        # LLM confirms duplicate
        mock_anthropic["set_response"](
            json.dumps(
                {
                    "is_duplicate": True,
                    "duplicate_of_id": "will-be-any-id",
                    "explanation": "'have' is a form of 'to have'",
                }
            )
        )

        # Set the deck's source_language
        await client.patch(
            f"/decks/{synced_templates['deck_id']}",
            json={"source_language": "English"},
            headers=auth_headers,
        )

        resp = await client.post(
            "/duplicates/check",
            json={
                "word": "have",
                "deck_id": synced_templates["deck_id"],
                "source_language": "English",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_duplicate"] is True
        assert data["explanation"] is not None

    async def test_given_unrelated_card_exists_when_check_then_no_duplicate(
        self,
        client,
        auth_headers,
        synced_templates,
        mock_embeddings,
        mock_anthropic,
    ):
        await create_card_via_api(
            client,
            auth_headers,
            synced_templates["deck_id"],
            synced_templates["note_type_id"],
            {"Front": "cat", "Back": "Katze"},
        )

        mock_anthropic["set_response"](
            json.dumps(
                {
                    "is_duplicate": False,
                    "duplicate_of_id": None,
                    "explanation": "No semantic match found.",
                }
            )
        )

        resp = await client.post(
            "/duplicates/check",
            json={
                "word": "dog",
                "deck_id": synced_templates["deck_id"],
                "source_language": "English",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_duplicate"] is False

    async def test_given_empty_deck_when_check_then_no_duplicate(
        self, client, auth_headers, synced_templates
    ):
        """Empty deck — should return is_duplicate: false without needing mocks."""
        resp = await client.post(
            "/duplicates/check",
            json={
                "word": "dog",
                "deck_id": synced_templates["deck_id"],
                "source_language": "English",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_duplicate"] is False
