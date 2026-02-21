import json

from tests.conftest import create_card_via_api


class TestOCR:
    async def test_when_ocr_then_extracts_words(self, client, mock_anthropic):
        mock_anthropic["set_response"](
            json.dumps(
                {
                    "raw_text": "Der Hund ist groß",
                    "words": ["Der", "Hund", "ist", "groß"],
                }
            )
        )

        resp = await client.post(
            "/ocr",
            files={"file": ("test.jpg", b"fake-image-bytes", "image/jpeg")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["words"] == ["Der", "Hund", "ist", "groß"]
        assert data["raw_text"] == "Der Hund ist groß"

    async def test_given_code_fenced_response_when_ocr_then_parses_json(
        self, client, mock_anthropic
    ):
        mock_anthropic["set_response"](
            '```json\n{"raw_text": "hello", "words": ["hello"]}\n```'
        )

        resp = await client.post(
            "/ocr",
            files={"file": ("test.jpg", b"fake", "image/jpeg")},
        )
        assert resp.status_code == 200
        assert resp.json()["words"] == ["hello"]


class TestTranslate:
    async def test_when_translate_then_returns_single_option(
        self, client, auth_headers, mock_anthropic
    ):
        mock_anthropic["set_response"](
            json.dumps(
                [
                    {
                        "word": "Hund",
                        "translation": "dog",
                        "part_of_speech": "noun",
                        "context": "Der Hund bellt. (The dog barks.)",
                    }
                ]
            )
        )

        resp = await client.post(
            "/translate",
            json={
                "word": "Hund",
                "source_language": "German",
                "target_language": "English",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        translations = resp.json()["translations"]
        assert len(translations) == 1
        assert translations[0]["translation"] == "dog"
        assert translations[0]["part_of_speech"] == "noun"

    async def test_given_ambiguous_word_when_translate_then_returns_multiple_options(
        self, client, auth_headers, mock_anthropic
    ):
        mock_anthropic["set_response"](
            json.dumps(
                [
                    {
                        "word": "Schloss",
                        "translation": "castle",
                        "part_of_speech": "noun",
                        "context": "Das Schloss steht auf dem Hügel.",
                    },
                    {
                        "word": "Schloss",
                        "translation": "lock",
                        "part_of_speech": "noun",
                        "context": "Das Schloss ist kaputt.",
                    },
                ]
            )
        )

        resp = await client.post(
            "/translate",
            json={
                "word": "Schloss",
                "source_language": "German",
                "target_language": "English",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        translations = resp.json()["translations"]
        assert len(translations) == 2
        assert translations[0]["translation"] == "castle"
        assert translations[1]["translation"] == "lock"

    async def test_given_dict_response_when_translate_then_wraps_in_list(
        self, client, auth_headers, mock_anthropic
    ):
        """If the LLM returns a single dict instead of a list, it gets wrapped."""
        mock_anthropic["set_response"](
            json.dumps(
                {
                    "word": "Hund",
                    "translation": "dog",
                    "part_of_speech": "noun",
                    "context": "Der Hund bellt.",
                }
            )
        )

        resp = await client.post(
            "/translate",
            json={
                "word": "Hund",
                "source_language": "German",
                "target_language": "English",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        translations = resp.json()["translations"]
        assert len(translations) == 1
        assert translations[0]["translation"] == "dog"

    async def test_given_native_language_when_translate_then_includes_native_translation(
        self, client, auth_headers, mock_anthropic
    ):
        mock_anthropic["set_response"](
            json.dumps(
                [
                    {
                        "word": "perro",
                        "translation": "chien",
                        "native_translation": "dog",
                        "part_of_speech": "noun",
                        "context": "El perro ladra.",
                    }
                ]
            )
        )

        resp = await client.post(
            "/translate",
            json={
                "word": "perro",
                "source_language": "Spanish",
                "target_language": "French",
                "native_language": "English",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        translations = resp.json()["translations"]
        assert translations[0]["native_translation"] == "dog"


class TestFormatCard:
    async def test_when_format_card_then_returns_styled_fields(
        self, client, auth_headers, synced_templates, mock_anthropic
    ):
        # Set deck languages first
        await client.patch(
            f"/decks/{synced_templates['deck_id']}",
            json={"source_language": "German", "target_language": "English"},
            headers=auth_headers,
        )

        # Create example cards for style derivation
        await create_card_via_api(
            client,
            auth_headers,
            synced_templates["deck_id"],
            synced_templates["note_type_id"],
            {"Front": "die Katze", "Back": "cat (f.)"},
        )

        mock_anthropic["set_response"](
            json.dumps({"Front": "der Hund", "Back": "dog (m.)"})
        )

        resp = await client.post(
            "/translate/format-card",
            json={
                "deck_id": synced_templates["deck_id"],
                "word": "Hund",
                "translation": "dog",
                "part_of_speech": "noun",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["fields"]["Front"] == "der Hund"
        assert data["fields"]["Back"] == "dog (m.)"
        assert "note_type_id" in data

    async def test_given_native_language_when_format_card_then_makes_two_llm_calls(
        self, client, auth_headers, synced_templates, mock_anthropic
    ):
        """format-card with native_language makes 2 sequential LLM calls."""
        await client.patch(
            f"/decks/{synced_templates['deck_id']}",
            json={"source_language": "German", "target_language": "English"},
            headers=auth_headers,
        )

        # First call: translate_native returns "dog"
        # Second call: format_card_fields returns the formatted fields
        mock_anthropic["set_responses"](
            [
                "dog",
                json.dumps({"Front": "der Hund", "Back": "dog (m.) [dog]"}),
            ]
        )

        resp = await client.post(
            "/translate/format-card",
            json={
                "deck_id": synced_templates["deck_id"],
                "word": "Hund",
                "translation": "dog",
                "part_of_speech": "noun",
                "native_language": "English",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["fields"]["Front"] == "der Hund"
        # Verify 2 LLM calls were made
        assert mock_anthropic["create_mock"].call_count == 2
