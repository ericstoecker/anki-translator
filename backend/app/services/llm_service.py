import base64
import json

import anthropic
import openai

from app.config import settings


async def _call_anthropic(
    prompt: str,
    image_b64: str | None = None,
    media_type: str = "image/jpeg",
) -> str:
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    content: list[dict] = []
    if image_b64:
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": image_b64,
                },
            }
        )
    content.append({"type": "text", "text": prompt})
    message = await client.messages.create(
        model=settings.llm_model,
        max_tokens=4096,
        messages=[{"role": "user", "content": content}],
    )
    return message.content[0].text


async def _call_openai(
    prompt: str,
    image_b64: str | None = None,
    media_type: str = "image/jpeg",
) -> str:
    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
    content: list[dict] = []
    if image_b64:
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{media_type};base64,{image_b64}",
                },
            }
        )
    content.append({"type": "text", "text": prompt})
    response = await client.chat.completions.create(
        model=settings.llm_model,
        max_tokens=4096,
        messages=[{"role": "user", "content": content}],
    )
    return response.choices[0].message.content


async def _call_llm(
    prompt: str,
    image_b64: str | None = None,
    media_type: str = "image/jpeg",
) -> str:
    if settings.llm_provider == "anthropic":
        return await _call_anthropic(prompt, image_b64, media_type)
    else:
        return await _call_openai(prompt, image_b64, media_type)


async def extract_words(image_bytes: bytes, media_type: str = "image/jpeg") -> dict:
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    prompt = (
        "Extract all readable words from this image. "
        "Return a JSON object with two keys:\n"
        '- "raw_text": the full extracted text as a string\n'
        '- "words": a list of unique individual words found in the text\n'
        "Return only the JSON object, no other text."
    )
    response = await _call_llm(prompt, image_b64, media_type)
    # Parse JSON from response, handling markdown code fences
    text = response.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(text)


async def translate_word(
    word: str,
    source_language: str,
    target_language: str,
    native_language: str | None = None,
) -> list[dict]:
    native_instruction = ""
    if native_language and native_language != target_language:
        native_instruction = f'\n- "native_translation": the translation of the word to {native_language}'

    prompt = (
        f'Translate the word "{word}" from {source_language} to {target_language}.\n'
        f"If the word has multiple distinct meanings, return up to 3 translations.\n"
        f"Return a JSON array of objects, each with these keys:\n"
        f'- "word": the original word\n'
        f'- "translation": the translation in {target_language}\n'
        f'- "part_of_speech": the part of speech (noun, verb, adjective, etc.)\n'
        f'- "context": a brief example sentence or usage note'
        f"{native_instruction}\n"
        f"Return only the JSON array, no other text."
    )
    response = await _call_llm(prompt)
    text = response.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    result = json.loads(text)
    # If the LLM returns a single dict instead of a list, wrap it
    if isinstance(result, dict):
        result = [result]
    return result


async def translate_native(
    word: str,
    source_language: str,
    native_language: str,
) -> str:
    prompt = (
        f'Translate the word "{word}" from {source_language} to {native_language}.\n'
        f"Return only the translated word or short phrase, no other text."
    )
    response = await _call_llm(prompt)
    return response.strip()


async def format_card_fields(
    word: str,
    translation: str,
    field_names: list[str],
    example_cards: list[dict],
    source_language: str,
    target_language: str,
    part_of_speech: str | None = None,
    native_translation: str | None = None,
    context: str | None = None,
) -> dict[str, str]:
    examples_text = ""
    for card in example_cards:
        examples_text += f"  {json.dumps(card['fields'])}\n"

    prompt = (
        f'I need to create a new flashcard for the word "{word}" '
        f'(translated as "{translation}" from {source_language} to {target_language}).\n\n'
        f"The card has these fields: {field_names}\n\n"
        f"Here are the most recent cards from this deck, ordered newest-first. "
        f"Derive the current formatting pattern and create a new card following "
        f"that pattern exactly:\n{examples_text}\n"
    )
    if part_of_speech:
        prompt += f"Part of speech: {part_of_speech}\n"
    if native_translation:
        prompt += (
            f"Also include the native language translation: {native_translation}\n"
        )
    if context:
        prompt += f"Context/usage: {context}\n"

    prompt += (
        f"\nReturn a JSON object mapping field names to their values, "
        f"following the formatting pattern from the examples above. "
        f"Return only the JSON object, no other text."
    )

    response = await _call_llm(prompt)
    text = response.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(text)


async def check_semantic_duplicate(
    word: str,
    candidate_cards: list[dict],
    source_language: str,
) -> dict | None:
    if not candidate_cards:
        return None

    cards_text = ""
    for card in candidate_cards:
        cards_text += f"  - id={card['id']}, fields={json.dumps(card['fields'])}\n"

    prompt = (
        f'Does the word "{word}" (in {source_language}) already exist in any form '
        f"among these existing cards? Consider conjugations, different forms, "
        f"synonyms, and semantic equivalents.\n\n"
        f"Existing cards:\n{cards_text}\n"
        f"Return a JSON object:\n"
        f'- "is_duplicate": true/false\n'
        f'- "duplicate_of_id": the id of the matching card (or null)\n'
        f'- "explanation": brief explanation of why it is or isn\'t a duplicate\n'
        f"Return only the JSON object, no other text."
    )
    response = await _call_llm(prompt)
    text = response.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    result = json.loads(text)
    if result.get("is_duplicate"):
        return result
    return None
