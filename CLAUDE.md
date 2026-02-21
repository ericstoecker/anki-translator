# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Anki Translator is an automated flashcard creation system for language learning. It allows a user to photograph text (e.g., from a book), extract words, translate them, and create Anki flashcards that match the style/template of an existing deck. The app runs on a phone but syncs with Anki on a Mac — the Anki app is **not** installed on the phone.

## Architecture

Three components:
1. **Cloud Backend** (Python/FastAPI + SQLite/PostgreSQL) — REST API, LLM integration, card/deck storage
2. **Mobile Frontend** (React PWA) — camera capture, word selection, translation, card preview
3. **Anki Add-on** (Python plugin) — syncs templates and cards bidirectionally with the backend

## Project Structure

```
backend/           Python FastAPI backend
  app/
    api/           Route handlers (auth, ocr, translate, cards, decks, sync, duplicates)
    models/        SQLAlchemy models (User, Deck, NoteType, Card)
    services/      Business logic (llm_service, duplicate_service, sync_service)
    schemas/       Pydantic request/response models
    main.py        FastAPI app entry point
    config.py      Settings from env vars (ANKI_ prefix)
    auth.py        JWT auth + bcrypt password hashing
    database.py    Async SQLAlchemy session
  tests/           pytest tests (36 tests, all passing)
  create_user.py   CLI to create initial user
frontend/          React + TypeScript PWA (Vite)
  src/
    pages/         LoginPage, CameraPage, WordSelectPage, TranslatePage, CardsPage, ConfigPage
    api/client.ts  API client with JWT auth
  e2e-test.mjs     Playwright E2E test script (21 assertions, 9 test scenarios)
anki-addon/        Anki add-on for sync
  __init__.py      Add-on entry point, menu item, auto-sync on startup
  sync.py          Full sync logic (template upload, pull, push, confirm)
  config.py        Add-on configuration
```

## Build & Run

### Backend (development)
```bash
cd backend

# First time setup
~/.local/bin/uv venv .venv
~/.local/bin/uv pip install -e ".[dev]"

# Create .env with API key
echo 'ANKI_ANTHROPIC_API_KEY=sk-ant-...' > .env

# Create initial user
.venv/bin/python create_user.py <username> <password>

# Run server (uses SQLite by default for local dev)
.venv/bin/uvicorn app.main:app --reload --port 8000
```

### Frontend (development)
```bash
cd frontend
npm install
npm run dev    # proxies /api to backend at localhost:8000
```

### Full stack (production)
```bash
# Copy .env.example to .env and fill in values
# Set ANKI_DATABASE_URL to a PostgreSQL URL for production
docker compose up --build
```

## Running Tests

```bash
cd backend

# Unit tests (35 tests, mocked LLM, uses SQLite)
.venv/bin/pytest tests/test_auth.py tests/test_cards.py tests/test_sync.py tests/test_llm_service.py -v

# Anki integration tests (3 tests, requires backend running on localhost:8000)
.venv/bin/pytest tests/test_anki_integration.py -v -s

# All backend tests
.venv/bin/pytest tests/ -v

# Frontend E2E tests (21 assertions, requires backend + frontend running)
cd frontend
npm install    # includes playwright
npx playwright install chromium
node e2e-test.mjs
```

### Test files:
- `test_auth.py` — password hashing, JWT, login/auth endpoints (9 tests)
- `test_cards.py` — card CRUD, accept/delete, deck listing, note types (8 tests)
- `test_sync.py` — template sync, pull/push, confirm, upsert (7 tests)
- `test_llm_service.py` — OCR, translation (list return + dict fallback), native translation, card formatting, duplicate detection (11 tests, mocked)
- `test_anki_integration.py` — real Anki library sync against running backend (3 tests)
- `frontend/e2e-test.mjs` — Playwright browser tests: login, login failure, camera, OCR, word selection, settings, cards, logout, auth guard (21 assertions, all passing)

## Key Design Decisions

- **bcrypt directly** (not passlib) — passlib is unmaintained and has compatibility issues with bcrypt 5.x
- **String columns for enums** — SQLite doesn't support native Postgres ENUM types, using String columns with Python str enums for portability
- **JSON columns for card fields** — flexible schema that matches Anki's field structure
- **uv** for Python package management — faster than pip, installed in `~/.local/bin/uv`
- **SQLite default for dev** — no PostgreSQL needed locally; switch to PostgreSQL in production via `ANKI_DATABASE_URL`
- **Lazy embedding computation** — embeddings for duplicate detection are computed on first duplicate check, not at card creation time
- **Anki pip package** — `aqt` is pip-installable for integration testing without needing the full Anki GUI
- **Two-step translate→format flow** — `POST /translate` returns 1-3 translation options via `translate_word()`, user picks one, then `POST /translate/format-card` formats a card with `format_card_fields()` using the chosen translation (no redundant LLM calls). `translate_native()` handles native-language translation at format time if requested.

## Configuration

All backend config via env vars with `ANKI_` prefix (see `app/config.py`):
- `ANKI_DATABASE_URL` — database URL (default: `sqlite+aiosqlite:///anki_translator.db`)
- `ANKI_SECRET_KEY` — JWT signing key
- `ANKI_ANTHROPIC_API_KEY` / `ANKI_OPENAI_API_KEY` — LLM API keys
- `ANKI_LLM_PROVIDER` — "anthropic" or "openai"
- `ANKI_LLM_MODEL` — model name for LLM calls
- `ANKI_CARD_EXAMPLE_COUNT` — number of recent cards used for style derivation (default 250)
- `ANKI_DUPLICATE_EMBEDDING_THRESHOLD` — cosine similarity threshold for duplicate pre-filter (default 0.6)

## Verified Features

All tested with real LLM (Claude) and real Anki library:
- [x] OCR: photo → word extraction (tested with German text image)
- [x] Translation: word → 1-3 translation options (user picks one) → card formatting (two-step, no redundant LLM calls)
- [x] Native translation: additional translation to user's native language (German→French with English native)
- [x] Card formatting: matches existing deck style (e.g., "der Fuchs (m.)" matching "der Hund (m.)" pattern)
- [x] Card lifecycle: create (draft) → accept (pending_sync) → sync confirm (synced)
- [x] Semantic duplicate detection: "Hund" matches "der Hund (m.)", "Hunde" matches "Hund", "rennen" matches "laufen"
- [x] Sync: template upload, card push (Anki→backend), card pull (backend→Anki), confirm
- [x] Auth: JWT login, protected endpoints, user creation CLI
- [x] Frontend proxy: Vite dev server proxies /api to backend
- [x] Frontend E2E: Playwright browser tests covering login, OCR, word selection, settings, cards, logout, auth guard (21 assertions passing)

### Current dev environment state:
- Backend runs on `localhost:8000` (uvicorn with SQLite)
- Frontend runs on `localhost:5175` (Vite dev server, proxies /api to backend)
- Test user: `testuser` / `testpass123`
- Test image at `/tmp/test_german.png` (German sentence: "Der schnelle Fuchs springt über den faulen Hund im Garten")
- DB has test decks (German::Vocabulary with source_language=German, target_language=English) and 22 cards
- Playwright MCP is configured in `~/.claude/settings.json` but has NOT been used for interactive browser testing yet

### Still needed:
- [ ] Manual E2E testing via Playwright MCP (interactive browser walkthrough of full user flow)
- [ ] Deploy to VPS with Docker Compose
- [ ] Production security hardening (rate limiting, fail2ban)

## Working Instructions

After completing any task that changes code:
1. **Always review CLAUDE.md** — check if any sections need updating (architecture, features, test counts, design decisions, config, etc.)
2. **Update CLAUDE.md** if the change affects: API endpoints, schemas, new/removed features, test structure, build steps, configuration, or project structure
3. If unsure whether an update is needed, err on the side of updating — stale docs are worse than verbose docs
