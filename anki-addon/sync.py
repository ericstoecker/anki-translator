"""Sync logic between Anki and the cloud backend."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone


class AnkiTranslatorSync:
    def __init__(self, backend_url: str):
        self.backend_url = backend_url.rstrip("/")
        self.api_token: str | None = None
        self._last_sync_key = "anki_translator_last_sync"

    def login(self, username: str, password: str):
        """Authenticate with the backend and store the JWT token."""
        url = f"{self.backend_url}/auth/login"
        body = json.dumps({"username": username, "password": password}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                self.api_token = result["access_token"]
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            raise RuntimeError(f"Login failed: {e.code} {e.reason} - {error_body}")

    def _request(self, method: str, path: str, data: dict | None = None) -> dict:
        url = f"{self.backend_url}{path}"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }
        body = json.dumps(data).encode("utf-8") if data else None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            raise RuntimeError(
                f"Backend request failed: {e.code} {e.reason} - {error_body}"
            )

    def upload_templates(self, mw):
        """Upload all deck and note type info to the backend."""
        col = mw.col
        decks_data = []
        for deck in col.decks.all():
            decks_data.append({
                "anki_deck_id": deck["id"],
                "name": deck["name"],
            })

        note_types_data = []
        for model in col.models.all():
            # Find which deck this model is most associated with
            deck_id = model.get("did", 1)
            templates = model.get("tmpls", [])
            front_tmpl = templates[0]["qfmt"] if templates else ""
            back_tmpl = templates[0]["afmt"] if templates else ""

            fields = []
            for i, fld in enumerate(model.get("flds", [])):
                fields.append({
                    "name": fld["name"],
                    "ordinal": i,
                })

            note_types_data.append({
                "anki_model_id": model["id"],
                "anki_deck_id": deck_id,
                "name": model["name"],
                "css": model.get("css", ""),
                "card_template_front": front_tmpl,
                "card_template_back": back_tmpl,
                "fields": fields,
            })

        self._request("POST", "/sync/templates", {
            "decks": decks_data,
            "note_types": note_types_data,
        })

    def pull_new_cards(self, mw) -> int:
        """Pull cards created via the phone app and create them in Anki."""
        col = mw.col
        last_sync = self._get_last_sync(mw)

        params = f"?since={urllib.parse.quote(last_sync)}" if last_sync else ""
        result = self._request("GET", f"/sync/pull{params}")
        cards = result.get("cards", [])

        if not cards:
            return 0

        confirm_items = []
        for card_data in cards:
            # Find the note type by backend note_type_id
            # We need to map backend IDs to Anki model IDs
            note_type_id = card_data.get("note_type_id")
            fields = card_data.get("fields", {})
            tags = card_data.get("tags", "")

            # Find matching model - we need to look up anki_model_id
            # For now, use the first model that has matching field names
            model = self._find_matching_model(col, fields)
            if not model:
                continue

            # Find the target deck
            deck_id = card_data.get("deck_id")
            anki_deck = self._find_matching_deck(col, deck_id)
            if not anki_deck:
                # Use default deck
                anki_deck = col.decks.current()

            note = col.newNote(model)
            for field_name, value in fields.items():
                if field_name in note:
                    note[field_name] = value

            if tags:
                note.tags = col.tags.split(tags)

            col.addNote(note)

            confirm_items.append({
                "backend_id": card_data["id"],
                "anki_note_id": note.id,
            })

        if confirm_items:
            self._request("POST", "/sync/confirm", {"items": confirm_items})

        return len(confirm_items)

    def push_local_cards(self, mw) -> int:
        """Push cards created/modified in Anki to the backend."""
        col = mw.col
        last_sync = self._get_last_sync(mw)

        # Find notes modified since last sync
        if last_sync:
            last_sync_ts = datetime.fromisoformat(last_sync).timestamp()
            note_ids = col.findNotes(f"edited:1")  # Notes edited in last day
            # Filter by actual modification time
            recent_notes = []
            for nid in note_ids:
                note = col.getNote(nid)
                if note.mod >= last_sync_ts:
                    recent_notes.append(note)
        else:
            # First sync - push all notes
            note_ids = col.findNotes("")
            recent_notes = [col.getNote(nid) for nid in note_ids]

        if not recent_notes:
            return 0

        cards_data = []
        for note in recent_notes:
            model = note.note_type()
            # Get the deck of the first card
            card_ids = note.card_ids()
            if not card_ids:
                continue
            card = col.getCard(card_ids[0])

            fields = {}
            for i, fld in enumerate(model["flds"]):
                if i < len(note.fields):
                    fields[fld["name"]] = note.fields[i]

            cards_data.append({
                "anki_note_id": note.id,
                "anki_deck_id": card.did,
                "anki_model_id": model["id"],
                "fields": fields,
                "tags": " ".join(note.tags),
            })

        if cards_data:
            self._request("POST", "/sync/push", {"cards": cards_data})

        return len(cards_data)

    def _find_matching_model(self, col, fields: dict):
        """Find an Anki model whose field names match the given fields."""
        field_names = set(fields.keys())
        for model in col.models.all():
            model_fields = {fld["name"] for fld in model.get("flds", [])}
            if field_names.issubset(model_fields):
                return model
        return None

    def _find_matching_deck(self, col, backend_deck_id: str):
        """Find Anki deck matching a backend deck ID. Returns deck dict or None."""
        # This is a simple approach - in practice we'd store the mapping
        return None

    def _get_last_sync(self, mw) -> str | None:
        config = mw.addonManager.getConfig(__name__) or {}
        return config.get(self._last_sync_key)

    def _set_last_sync(self, mw):
        config = mw.addonManager.getConfig(__name__) or {}
        config[self._last_sync_key] = datetime.now(timezone.utc).isoformat()
        mw.addonManager.writeConfig(__name__, config)

    def full_sync(self, mw) -> dict:
        """Run the complete sync flow."""
        results = {}

        # Step 1: Upload templates
        self.upload_templates(mw)
        results["templates"] = "uploaded"

        # Step 2: Pull new cards from backend
        pulled = self.pull_new_cards(mw)
        results["pulled"] = pulled

        # Step 3: Push local changes
        pushed = self.push_local_cards(mw)
        results["pushed"] = pushed

        # Update last sync timestamp
        self._set_last_sync(mw)
        results["last_sync"] = datetime.now(timezone.utc).isoformat()

        return results
