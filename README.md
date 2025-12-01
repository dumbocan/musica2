# Audio2 - Personal Music API

A REST API backend for a personal music application, inspired by Spotify, using local file library and enriched with external APIs (Spotify, Last.fm, etc.) for metadata, recommendations, and lyrics.

## Project Overview

This backend will serve:

- Full artist discographies (albums, songs, lyrics).
- Metadata from APIs (recommendations, scoring).
- Playlists management.
- Local file handling (magnet links for downloads).
- Future: Multiuser support, ratings, tags, play history, smart playlists, charts, YouTube integration.

Current Focus: Basic FastAPI setup, PostgreSQL connection, health endpoint.

## Tech Stack

- **Language**: Python 3.x
- **API Framework**: FastAPI
- **Server**: Uvicorn
- **Database**: PostgreSQL with SQLModel (connection tested and working)
- **ORM**: SQLModel for async operations
- **Env Management**: pydantic-settings with python-dotenv
- **Other**: psycopg2-binary for connection

## Project Plan

### Current Implementation (Step-by-Step)

- [x] Git setup: Init repo, .gitignore, remote (musica2 on GitHub).
- [x] Create comprehensive README with instructions.
- [x] Set up virtual environment and install dependencies.
- [x] Create project structure (app/, api/, core/, models/).
- [x] Implement FastAPI app with health endpoint.
- [x] Configure PostgreSQL connection (prepared, not connected yet).
- [x] Test server startup and health endpoint (200 OK, returns {"status":"ok"}).
- [x] Set up and test PostgreSQL DB connection in code.
- [x] Add session manager and prepare for models.
- [x] Verify server works with DB integration.
- [ ] Review and document setup.

### Future Tasks (to be implemented incrementally)

- [ ] Research external APIs (Spotify, Last.fm) for data endpoints.
- [ ] Define models: User, Artist, Album, Track, Playlist.
- [ ] Implement discography endpoints.
- [ ] Add playlist CRUD.
- [ ] Integrate ratings/favorites.
- [ ] Add tags, play history.
- [ ] Enable smart playlists.
- [ ] Implement offline detection.
- [ ] Advanced search.
- [ ] Personal charts.
- [ ] YouTube integration.
- [ ] Auth system (JWT) for multiuser (prepared models).

## Setup Instructions

### Prerequisites

- Python 3.8+
- PostgreSQL (install and set up DB, but connection prepared only).
- Git

### Clone and Install

```bash
git clone https://github.com/dumbocan/musica2.git
cd audio2  # or the local dir name
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Environment Variables

Create `.env` from `.env.example`:

```
DATABASE_URL=postgresql+psycopg2://usuario:password@localhost:5432/music_db
# Add API keys later: SPOTIFY_CLIENT_ID=, etc.
```

### Run the Server

```bash
uvicorn app.main:app --reload
```

Server will run on `http://127.0.0.1:8000/`

### Health Check

Test: `http://localhost:8000/health` → Expected: `{"status": "ok"}`

### Development

- Test all functionality.
- Commit after each step.
- Push to GitHub.

## Contributing

Work in small steps, test thoroughly, avoid breaking existing code. Commits frequent.

## License

Personal project, no license.
