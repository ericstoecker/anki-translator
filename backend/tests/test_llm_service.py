import json
from unittest.mock import AsyncMock, patch

import pytest

from app.services.llm_service import (
    check_semantic_duplicate,
    extract_words,
    format_card_fields,
    translate_word,
)


@pytest.fixture
def mock_llm():
    with patch("app.services.llm_service._call_llm", new_callable=AsyncMock) as mock:
        yield mock


class TestExtractWords:
    async def test_extract_words(self, mock_llm):
        mock_llm.return_value = json.dumps({
            "raw_text": "Der Hund ist groß",
            "words": ["Der", "Hund", "ist", "groß"],
        })
        result = await extract_words(b"fake-image-bytes")
        assert result["words"] == ["Der", "Hund", "ist", "groß"]
        assert result["raw_text"] == "Der Hund ist groß"

    async def test_extract_words_with_code_fences(self, mock_llm):
        mock_llm.return_value = '```json\n{"raw_text": "hello", "words": ["hello"]}\n```'
        result = await extract_words(b"fake")
        assert result["words"] == ["hello"]


class TestTranslateWord:
    async def test_translate(self, mock_llm):
        mock_llm.return_value = json.dumps({
            "word": "Hund",
            "translation": "dog",
            "part_of_speech": "noun",
            "context": "Der Hund bellt. (The dog barks.)",
        })
        result = await translate_word("Hund", "German", "English")
        assert result["translation"] == "dog"
        assert result["part_of_speech"] == "noun"

    async def test_translate_with_native(self, mock_llm):
        mock_llm.return_value = json.dumps({
            "word": "perro",
            "translation": "chien",
            "native_translation": "dog",
            "part_of_speech": "noun",
            "context": "El perro ladra.",
        })
        result = await translate_word(
            "perro", "Spanish", "French", native_language="English"
        )
        assert result["native_translation"] == "dog"


class TestFormatCardFields:
    async def test_format(self, mock_llm):
        mock_llm.return_value = json.dumps({
            "Front": "der Hund",
            "Back": "dog (m.)",
        })
        result = await format_card_fields(
            word="Hund",
            translation="dog",
            field_names=["Front", "Back"],
            example_cards=[
                {"fields": {"Front": "die Katze", "Back": "cat (f.)"}},
                {"fields": {"Front": "das Haus", "Back": "house (n.)"}},
            ],
            source_language="German",
            target_language="English",
            part_of_speech="noun",
        )
        assert result["Front"] == "der Hund"
        assert result["Back"] == "dog (m.)"


class TestSemanticDuplicate:
    async def test_duplicate_found(self, mock_llm):
        mock_llm.return_value = json.dumps({
            "is_duplicate": True,
            "duplicate_of_id": "card-123",
            "explanation": "'have' is a form of 'to have'",
        })
        result = await check_semantic_duplicate(
            "have",
            [{"id": "card-123", "fields": {"Front": "to have"}}],
            "English",
        )
        assert result is not None
        assert result["duplicate_of_id"] == "card-123"

    async def test_no_duplicate(self, mock_llm):
        mock_llm.return_value = json.dumps({
            "is_duplicate": False,
            "duplicate_of_id": None,
            "explanation": "No semantic match found.",
        })
        result = await check_semantic_duplicate(
            "dog",
            [{"id": "card-1", "fields": {"Front": "cat"}}],
            "English",
        )
        assert result is None

    async def test_empty_candidates(self):
        result = await check_semantic_duplicate("dog", [], "English")
        assert result is None
