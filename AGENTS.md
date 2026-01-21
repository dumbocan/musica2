# Repository Guidelines

## Project Structure & Module Organization
Audio2 couples a FastAPI backend (`app/`) with a Vite + TypeScript frontend (`frontend/`). Routers stay in `app/api/`, while persistence, jobs, and auth helpers belong to `app/core/`; SQLModel entities and schemas live in `app/models/` and `app/schemas/`. Place heavy integrations (Spotify, YouTube, Last.fm) under `app/services/`, stash research helpers in `scripts/`, and treat `cache/images`, `storage/*`, and `downloads/` as generated assets alongside the root-level scenario runners (`smoke_test.py`, `test_*.py`).

## Build, Test, and Development Commands
- `python -m venv venv && source venv/bin/activate` — create and enter the virtual environment.
- `pip install -r requirements.txt` — install backend dependencies.
- `uvicorn app.main:app --reload` — start the API locally with a populated `.env`.
- `npm install && npm run dev --prefix frontend` — boot the Vite UI wired to the localhost CORS origins in `app/main.py`.
- `python smoke_test.py` / `python test_complete_system.py` — run integration checks that call live APIs.
Note: this repository is configured to use PostgreSQL only. Ensure `DATABASE_URL` points to Postgres before running the API.

## Database Connection (PostgreSQL)
- Read `DATABASE_URL` from `.env` (defaults to Postgres in local dev). Example: `postgresql+psycopg2://user:pass@127.0.0.1:5432/music_db`.
- Verify Postgres is running before DB checks: `pg_isready -h 127.0.0.1 -p 5432`.
- If Postgres is stopped, start it (ask for permission first): `sudo systemctl start postgresql` or `docker start <container>`.
- To inspect quickly: `psql "$DATABASE_URL"` or a short `venv/bin/python` snippet using `app.core.db.get_session`.

## Coding Style & Naming Conventions
Follow PEP 8 with four-space indents, type hints, and snake_case names; keep SQLModel and Pydantic classes in PascalCase (see `app/models/base.py`). Endpoints should expose concise nouns or verbs (`/artists/save/{spotify_id}`) and return typed schemas, not raw dicts. Shared utilities must accept dependency-injected sessions (`Depends(get_session)`) and avoid bare prints. Frontend code follows the Vite ESLint and Tailwind defaults in `frontend/src`.

## Testing Guidelines
Use the root-level runners for regression coverage: `smoke_test.py` for sanity checks, `test_download_no_duplicates.py` for storage safety, and `test_multi_user_freshness.py` for orchestration. New features should ship with a similarly named script or FastAPI test that seeds its data via `create_db_and_tables()` and aborts if credentials are absent. Keep tests idempotent by creating temporary users or artists instead of truncating shared tables.

## Commit & Pull Request Guidelines
Most recent commits use a Conventional prefix (`feat:`, `docs:`, `fix:`); keep that style with an imperative summary under 72 characters. PRs should outline the endpoints or views touched, list the commands you ran (curl, `python` scripts, `npm run build`), and call out new config or schema migrations plus any artifacts that must be cleared. Attach screenshots or sample JSON whenever UI/API behavior changes.

## Security & Configuration Tips
Secrets stay in `.env`; never hard-code tokens or client secrets. Honor the auth middleware in `app/main.py`—if you add public endpoints, list them in `PUBLIC_PATHS` with justification. Cached media often contains licensed artwork, so clear `cache/` and `storage/` before sharing archives, and reuse the throttling helpers in `app/core/data_freshness.py` when calling external APIs.

## YouTube Prefetch & Downloads
- The backend launches `youtube_prefetch_loop()` on startup. It fetches one track every 5 s and sleeps 15 minutes after any 403/429. Do not spawn additional tight loops; use the existing helper or `POST /youtube/album/{spotify_id}/prefetch` if you need bursts.
- Every change touching YouTube must ensure `save_youtube_download()` writes `spotify_track_id`, `spotify_artist_id`, `youtube_video_id`, and `download_status`. The album counters and the Tracks dashboard depend on that table, even if MP3 files already exist.
- When debugging or documenting, instruct the user to redirect logs (`uvicorn app.main:app --reload > uvicorn.log 2>&1`) and tail for `[youtube_prefetch]` to monitor progress.
- Always remind contributors to set `YOUTUBE_API_KEY` in `.env`; without it, `/youtube/...` endpoints return errors and the frontend surfaces warnings.

## Future Storage & Offline Roadmap
- Dev/testing stores audio under the local `downloads/` folder (see `app/core/youtube.py`).
- Future work should support external disks and/or torrent-managed folders, so avoid hardcoding paths and keep download storage configurable.
- Production goal: allow user-selected offline downloads for web and Android with explicit sync/permissions behavior.
- Add an offline mode toggle that disables external API calls and background refresh loops, serving only from DB/downloads.

## Future Data Enhancements
- Add anonymous download counters per track (aggregated, not per-user).
- Normalize and expose a genre catalog for browse/filter endpoints.
- Make YouTube DB-first: read cached `YouTubeDownload` rows first and only hit YouTube when link/status is missing.
- Prefer local playback for `/youtube/stream` by checking `download_path` (mp3/m4a) before hitting YouTube.
- Add per-user hide/delete for albums and tracks (non-destructive, data remains for other users).

## DB-first Search Plan (Professionalization)
- Goal: resolve search locally for artists/albums/tracks (even offline), then enrich in background only if needed.
- Steps:
  - Add alias storage for artist/album/track names (typos, transliterations, punctuation variants).
  - Build a local search index with normalized tokens + ranking signals (popularity, favorites, last played).
  - Implement DB-first search flow: local match + suggestions → return immediately; low-confidence results trigger async enrichment.
  - Ensure the UI never blocks on external APIs; all external calls are best-effort and persisted.
  - Keep album covers, bios, and chart stats DB-sourced; refresh on schedule rather than during search.
- Planned commit: `feat: professionalize db-first search resolution`

## Tracks Overview Workflow
- The route `GET /tracks/overview` is the canonical way to expose track/YouTube/cache status. Any frontend widget that needs link/file info should consume this endpoint instead of hitting `/youtube/track/...` en masa.
- The Tracks page (`frontend/src/pages/TracksPage.tsx`) expects fields like `youtube_status`, `youtube_url`, and `local_file_exists`. When updating backend schemas, keep those keys stable or update the UI in the same change.
- Album link counters should combine DB data (`YouTubeDownload` joins) with downloaded track IDs. Make sure new features keep that dual-source logic intact, especially when introducing migrations or cleanup scripts.
- The Tracks page groups duplicates by `artist + track name` to avoid multiple rows; favorites should apply to the whole group and the UI picks the best version (local file > YouTube > favorite).

## Discography UX (DB-first)
- `/artists/{spotify_id}/albums?refresh=true` returns local DB data immediately and triggers a full Spotify refresh in the background to avoid timeouts blocking the UI.
- `/albums/spotify/{id}` and `/albums/{id}/tracks` should be DB-first and only call Spotify when tracks are missing; avoid hard failures when Spotify is slow/offline.
- The artist discography page separates **Albums**, **Singles**, and **Compilations** using `album_group`/`album_type` when present and falls back to track count heuristics when missing.

## Playback History & Charts
- `POST /tracks/play/{track_id}` records plays in `PlayHistory`; UI counters should read from backend endpoints instead of local-only state.
- `GET /tracks/most-played` and `GET /tracks/recent-plays` power the dashboard lists; they return `play_count` / `played_at` plus the same YouTube/cache fields as track lists.
- Chart badges come from `GET /tracks/chart-stats` and `GET /tracks/overview` fields (`chart_best_position`, `chart_best_position_date`); keep those keys stable in frontend.
- Billboard matches are computed from raw chart data via `TrackChartEntry` + `TrackChartStats`; the maintenance loop populates stats so the UI does not scrape external sites.

## Recent Troubleshooting Notes
- YouTube quota 403/429 stops prefetch for 15 min; avoid extra loops and only search on album entry or explicit play.
- “Sin enlace de YouTube” can appear if `download_status` is stale; normalize to `link_found` when `youtube_video_id` exists.
- Frontend must resolve `track.id || track.spotify_id` before calling `/youtube/track/...` to avoid 404s.
- Streaming uses `/youtube/stream` (no seek, duration may be 0 until metadata); downloads must honor the actual file format from `/youtube/download/.../status`.
- Keep `youtube_video_id` real (11 chars) or hide YouTube-only UI; local-only files should not pretend to be YouTube IDs.
- Use `scripts/organize_downloads_by_album.py --resolve-unknown --resolve-spotify --spotify-create` to align existing downloads to `downloads/<Artist>/<Album>/<Track>.<ext>`.
 - Tracks totals can be wrong if `youtube_video_id` is empty; treat empty strings as missing and prefer the row with a valid video ID when multiple `YouTubeDownload` rows exist for one track.
 - For performance, filter in `/tracks/overview` (`filter`, `search`) and use `filtered_total` rather than loading the entire library in the frontend.
 - Track pagination should use `after_id` keyset with `limit` and prefetch when ~100 rows remain to minimize network churn.

## Historial reciente y aprendizajes
- ✅ El nuevo reproductor mezcla audio local (descargas guardadas) con streaming ligero; el footer se mantiene activo, marca favoritos y escucha las pistas desde `downloads/`.
- ✅ La vista de Tracks y los filtros sticky presentan totales filtrados y cargan lotes graduales sin recargar toda la biblioteca, lo cual mejora la navegación del catálogo.
- ⚠️ La cuota de YouTube sigue generando 403/429 y algunos filtros (`filter=dr`) pueden devolver `400/422`; los escenarios con CORS bloqueados en `/tracks/overview` o `/search/artist-profile` deben verificar que el backend esté levantado y que se reusarán los tokens correctos.
- ⚠️ Los nuevos controles de video no han sustituido completamente al audio: los botones del footer reinician la pista tras pausar, el slider no permite `seek` y los iframes a veces muestran pantalla en negro; el modo video se mantiene como solución temporal que abre un iframe en el overlay e invoca solo el link de YouTube, sin recrear toda la lógica de audio.

## Frontend Code Quality Review Findings (Enero 2026)

Se realizó una revisión exhaustiva del código en el directorio `frontend/` para mejorar la calidad, la seguridad de tipos y la adherencia a las mejores prácticas. A continuación, se detallan los tipos de problemas encontrados y las soluciones aplicadas:

### 1. Eliminación de `any` explícitos (`@typescript-eslint/no-explicit-any`)

**Problema:** El uso extendido del tipo `any` debilitaba la seguridad de tipos de TypeScript, dificultando la detección de errores en tiempo de compilación y reduciendo la claridad del código.
**Solución:** Se reemplazó la mayoría de las ocurrencias de `any` con tipos específicos (como `Artist[]`, `SpotifyArtist[]`, `Track[]`, `LastfmArtist[]`) o con `unknown` cuando el tipo exacto no podía determinarse de inmediato. Esto incluyó la adición de `type guards` para el manejo seguro de errores en bloques `catch` (ej., `err: unknown`).

**Archivos afectados:**
-   `AlbumDetailPage.tsx`
-   `SearchPage.tsx`
-   `TracksPage.tsx`
-   `NetworkDebugger.tsx`
-   `YouTubeOverlayPlayer.tsx`
-   `useFavorites.ts`
-   `usePaginatedArtists.ts`
-   `HealthPage.tsx`
-   `LoginPage.tsx`
-   `useApiStore.ts`
-   `usePlayerStore.ts`
-   `types/api.ts`

### 2. Optimización de React Hooks (`react-hooks/exhaustive-deps`)

**Problema:** Advertencias sobre dependencias faltantes o innecesarias en `useEffect`, `useCallback` y `useMemo`. Esto podía llevar a `stale closures`, comportamientos inesperados o re-ejecuciones innecesarias de funciones y efectos.
**Solución:**
-   Se envolvieron funciones de manejo de eventos y lógicas reutilizables en `useCallback` (ej., `handlePlay`, `handlePause`, `handleLoadMore`, `performSearch`, `inferMode`, `resolveTrackKey`).
-   Se ajustaron correctamente los arrays de dependencias para `useEffect` y `useMemo`, asegurando que los hooks se re-ejecuten solo cuando sea necesario y que las funciones utilizadas dentro de ellos sean estables.
-   Se movieron funciones auxiliares (ej., `clampVolume`, `seekBy`, `toggleMute`) dentro del `useEffect` donde se utilizan exclusivamente para co-localizar la lógica y simplificar las dependencias.

**Archivos afectados:**
-   `PlayerFooter.tsx`
-   `AlbumDetailPage.tsx`
-   `SearchPage.tsx`
-   `TracksPage.tsx`

### 3. Refactorización y Mejores Prácticas

**Problema:** Detección de código redundante, interfaces vacías y problemas con Fast Refresh.
**Solución:**
-   **`components/ui/button.tsx`**: La definición de `buttonVariants` se movió a un archivo separado (`button-variants.ts`) para cumplir con la restricción de Fast Refresh de React de exportar solo componentes desde un archivo.
-   **`components/ui/input.tsx`**: Una interfaz vacía (`InputProps`) fue reemplazada por un alias de tipo (`type InputProps = ...`) para mayor concisión y evitar una advertencia del linter.
-   **`AlbumDetailPage.tsx`**: Eliminación de funciones `resolveImageUrl` duplicadas o no utilizadas.
-   **`ArtistsPage.tsx`**: Eliminación de directivas `eslint-disable` redundantes.

**Beneficios:**
La aplicación ahora cuenta con una base de código frontend más robusta, fácil de mantener y extensible, con una mayor confianza en la corrección lógica gracias a la mejora en la seguridad de tipos. El rendimiento y la experiencia de desarrollo también se han optimizado al reducir re-renders innecesarios y mejorar el soporte de Fast Refresh.
