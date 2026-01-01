# Repository Guidelines

## Project Structure & Module Organization
Audio2 couples a FastAPI backend (`app/`) with a Vite + TypeScript frontend (`frontend/`). Routers stay in `app/api/`, while persistence, jobs, and auth helpers belong to `app/core/`; SQLModel entities and schemas live in `app/models/` and `app/schemas/`. Place heavy integrations (Spotify, YouTube, Last.fm) under `app/services/`, stash research helpers in `scripts/`, and treat `cache/images`, `storage/*`, and `downloads/` as generated assets alongside the root-level scenario runners (`smoke_test.py`, `test_*.py`).

## Build, Test, and Development Commands
- `python -m venv venv && source venv/bin/activate` — create and enter the virtual environment.
- `pip install -r requirements.txt` — install backend dependencies.
- `uvicorn app.main:app --reload` — start the API locally with a populated `.env`.
- `npm install && npm run dev --prefix frontend` — boot the Vite UI wired to the localhost CORS origins in `app/main.py`.
- `python smoke_test.py` / `python test_complete_system.py` — run integration checks that call live APIs.

## Coding Style & Naming Conventions
Follow PEP 8 with four-space indents, type hints, and snake_case names; keep SQLModel and Pydantic classes in PascalCase (see `app/models/base.py`). Endpoints should expose concise nouns or verbs (`/artists/save/{spotify_id}`) and return typed schemas, not raw dicts. Shared utilities must accept dependency-injected sessions (`Depends(get_session)`) and avoid bare prints. Frontend code follows the Vite ESLint and Tailwind defaults in `frontend/src`.

## Testing Guidelines
Use the root-level runners for regression coverage: `smoke_test.py` for sanity checks, `test_download_no_duplicates.py` for storage safety, and `test_multi_user_freshness.py` for orchestration. New features should ship with a similarly named script or FastAPI test that seeds its data via `create_db_and_tables()` and aborts if credentials are absent. Keep tests idempotent by creating temporary users or artists instead of truncating shared tables.

## Commit & Pull Request Guidelines
Most recent commits use a Conventional prefix (`feat:`, `docs:`, `fix:`); keep that style with an imperative summary under 72 characters. PRs should outline the endpoints or views touched, list the commands you ran (curl, `python` scripts, `npm run build`), and call out new config or schema migrations plus any artifacts that must be cleared. Attach screenshots or sample JSON whenever UI/API behavior changes.

## Security & Configuration Tips
Secrets stay in `.env`; never hard-code tokens or client secrets. Honor the auth middleware in `app/main.py`—if you add public endpoints, list them in `PUBLIC_PATHS` with justification. Cached media often contains licensed artwork, so clear `cache/` and `storage/` before sharing archives, and reuse the throttling helpers in `app/core/data_freshness.py` when calling external APIs.
