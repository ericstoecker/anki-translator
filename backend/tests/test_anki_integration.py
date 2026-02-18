"""Integration test: Anki add-on sync logic against the real backend.

This test:
1. Creates a test Anki collection with a deck and sample cards
2. Runs the sync logic (template upload + card push) against the running backend
3. Verifies cards appear in the backend
4. Creates a card via the backend API
5. Pulls it into Anki and verifies it exists

Requires: backend running on localhost:8000 with a test user created.
Run with: pytest tests/test_anki_integration.py -v -s
"""

import json
import os
import tempfile
import urllib.request

import pytest
from anki.collection import Collection


BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
TEST_USER = "testuser"
TEST_PASS = "testpass123"

# Note: These tests are NOT isolated from each other — they share the same
# backend database. Each test uploads its own templates before operating.
# Anki model/deck IDs change per test run since each creates a fresh collection.


def api_request(method, path, token=None, data=None):
    url = f"{BACKEND_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def get_token():
    result = api_request("POST", "/auth/login", data={
        "username": TEST_USER,
        "password": TEST_PASS,
    })
    return result["access_token"]


@pytest.fixture
def token():
    return get_token()


@pytest.fixture
def anki_col():
    """Create a test Anki collection with a German vocab deck and sample cards."""
    tmpdir = tempfile.mkdtemp()
    col_path = os.path.join(tmpdir, "test_integration.anki2")
    col = Collection(col_path)

    # Create a deck
    deck_id = col.decks.id("German::Vocabulary", create=True)
    col.decks.set_current(deck_id)

    # Create a note type (model) with Front/Back fields
    model = col.models.new("Basic (German)")
    col.models.add_field(model, col.models.new_field("Front"))
    col.models.add_field(model, col.models.new_field("Back"))
    tmpl = col.models.new_template("Card 1")
    tmpl["qfmt"] = "<div class='front'>{{Front}}</div>"
    tmpl["afmt"] = "<div class='back'>{{FrontSide}}<hr>{{Back}}</div>"
    model["css"] = ".card { font-family: arial; font-size: 20px; text-align: center; }"
    model["did"] = deck_id
    col.models.add_template(model, tmpl)
    col.models.add(model)

    # Add sample cards
    sample_words = [
        ("der Hund (m.)", "dog"),
        ("die Katze (f.)", "cat"),
        ("das Haus (n.)", "house"),
        ("der Baum (m.)", "tree"),
        ("die Blume (f.)", "flower"),
        ("laufen (v.)", "to run"),
        ("essen (v.)", "to eat"),
        ("schlafen (v.)", "to sleep"),
        ("groß (adj.)", "big, tall"),
        ("klein (adj.)", "small, little"),
    ]
    for front, back in sample_words:
        note = col.newNote(model)
        note["Front"] = front
        note["Back"] = back
        col.addNote(note)

    yield col
    col.close()


class TestAnkiSync:
    def test_template_upload(self, anki_col, token):
        """Test uploading Anki templates to the backend."""
        col = anki_col

        # Build template data like the add-on would
        decks_data = []
        for deck in col.decks.all():
            decks_data.append({
                "anki_deck_id": deck["id"],
                "name": deck["name"],
            })

        note_types_data = []
        for model in col.models.all():
            templates = model.get("tmpls", [])
            front_tmpl = templates[0]["qfmt"] if templates else ""
            back_tmpl = templates[0]["afmt"] if templates else ""
            fields = [{"name": f["name"], "ordinal": i}
                      for i, f in enumerate(model.get("flds", []))]

            # Find associated deck
            deck_id = model.get("did", 1)
            note_types_data.append({
                "anki_model_id": model["id"],
                "anki_deck_id": deck_id,
                "name": model["name"],
                "css": model.get("css", ""),
                "card_template_front": front_tmpl,
                "card_template_back": back_tmpl,
                "fields": fields,
            })

        result = api_request("POST", "/sync/templates", token, {
            "decks": decks_data,
            "note_types": note_types_data,
        })
        assert result["status"] == "ok"
        print(f"Templates uploaded: {result}")

        # Verify decks exist in backend
        decks = api_request("GET", "/decks", token)
        deck_names = [d["name"] for d in decks]
        assert "German::Vocabulary" in deck_names
        print(f"Backend decks: {deck_names}")

    def test_push_cards_to_backend(self, anki_col, token):
        """Test pushing Anki cards to the backend."""
        col = anki_col

        # First upload ALL templates (decks + note types)
        all_decks = [{"anki_deck_id": d["id"], "name": d["name"]}
                     for d in col.decks.all()]
        model = [m for m in col.models.all() if m["name"] == "Basic (German)"][0]
        vocab_deck = [d for d in col.decks.all() if d["name"] == "German::Vocabulary"][0]
        api_request("POST", "/sync/templates", token, {
            "decks": all_decks,
            "note_types": [{
                "anki_model_id": model["id"],
                "anki_deck_id": vocab_deck["id"],
                "name": model["name"],
                "css": model.get("css", ""),
                "card_template_front": model["tmpls"][0]["qfmt"],
                "card_template_back": model["tmpls"][0]["afmt"],
                "fields": [{"name": f["name"], "ordinal": i}
                           for i, f in enumerate(model["flds"])],
            }],
        })

        # Push cards
        note_ids = col.findNotes("")
        cards_data = []
        for nid in note_ids:
            note = col.get_note(nid)
            note_model = note.note_type()
            card_ids = note.card_ids()
            if not card_ids:
                continue
            card = col.get_card(card_ids[0])
            fields = {}
            for i, fld in enumerate(note_model["flds"]):
                if i < len(note.fields):
                    fields[fld["name"]] = note.fields[i]
            cards_data.append({
                "anki_note_id": note.id,
                "anki_deck_id": card.did,
                "anki_model_id": note_model["id"],
                "fields": fields,
                "tags": " ".join(note.tags),
            })

        result = api_request("POST", "/sync/push", token, {"cards": cards_data})
        print(f"Push result: {result}")
        assert result["created"] == len(cards_data)

        # Verify cards exist in backend
        backend_cards = api_request("GET", "/cards", token)
        print(f"Backend now has {len(backend_cards)} cards")
        assert len(backend_cards) >= len(cards_data)

    def test_pull_card_into_anki(self, anki_col, token):
        """Test creating a card in the backend and pulling it into Anki."""
        col = anki_col

        # Upload ALL templates first
        all_decks = [{"anki_deck_id": d["id"], "name": d["name"]}
                     for d in col.decks.all()]
        model = [m for m in col.models.all() if m["name"] == "Basic (German)"][0]
        vocab_deck = [d for d in col.decks.all() if d["name"] == "German::Vocabulary"][0]
        api_request("POST", "/sync/templates", token, {
            "decks": all_decks,
            "note_types": [{
                "anki_model_id": model["id"],
                "anki_deck_id": vocab_deck["id"],
                "name": model["name"],
                "css": model.get("css", ""),
                "card_template_front": model["tmpls"][0]["qfmt"],
                "card_template_back": model["tmpls"][0]["afmt"],
                "fields": [{"name": f["name"], "ordinal": i}
                           for i, f in enumerate(model["flds"])],
            }],
        })

        # Get the backend deck and note type IDs
        decks = api_request("GET", "/decks", token)
        backend_deck = next(d for d in decks if d["name"] == "German::Vocabulary")

        nt_list = api_request("GET", f"/decks/{backend_deck['id']}/note-types", token)
        backend_nt = nt_list[0]

        # Create a card in the backend (simulating phone app)
        card_result = api_request("POST", "/cards", token, {
            "deck_id": backend_deck["id"],
            "note_type_id": backend_nt["id"],
            "fields": {"Front": "der Tisch (m.)", "Back": "table"},
            "source_word": "Tisch",
            "source_language": "German",
            "target_language": "English",
        })
        card_id = card_result["id"]
        print(f"Created card: {card_id}")

        # Accept it (move to pending_sync)
        api_request("POST", f"/cards/{card_id}/accept", token)

        # Pull it
        pull_result = api_request("GET", "/sync/pull", token)
        assert len(pull_result["cards"]) >= 1
        pulled_card = next(c for c in pull_result["cards"] if c["id"] == card_id)
        print(f"Pulled card: {pulled_card['fields']}")

        # Create the note in Anki
        note = col.newNote(model)
        note["Front"] = pulled_card["fields"]["Front"]
        note["Back"] = pulled_card["fields"]["Back"]
        col.addNote(note)

        # Confirm sync
        api_request("POST", "/sync/confirm", token, {
            "items": [{"backend_id": card_id, "anki_note_id": note.id}],
        })

        # Verify the note exists in Anki
        found = col.findNotes(f'"der Tisch"')
        assert len(found) > 0
        found_note = col.get_note(found[0])
        assert found_note["Front"] == "der Tisch (m.)"
        assert found_note["Back"] == "table"
        print(f"Card successfully pulled into Anki: {found_note['Front']} -> {found_note['Back']}")

        # Verify backend marked it as synced
        backend_card = api_request("GET", f"/cards/{card_id}", token)
        assert backend_card["status"] == "synced"
        assert backend_card["anki_note_id"] == note.id
        print(f"Backend card status: {backend_card['status']}, anki_note_id: {backend_card['anki_note_id']}")
