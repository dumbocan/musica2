# CLAUDE.md

## Working relationship
- You can push back on ideas-this can lead to better documentation. Cite sources and explain your reasoning when you do so
- ALWAYS ask for clarification rather than making assumptions
- NEVER lie, guess, or make up information

## Project context
- Audio2 is a personal music streaming API and web application
- Backend: FastAPI (Python) + PostgreSQL
- Frontend: React/TypeScript + Vite
- Integrations: Spotify, Last.fm, YouTube Data API

## Content strategy
- Document just enough for user success - not too much, not too little
- Prioritize accuracy and usability of information
- Make content evergreen when possible
- Search for existing information before adding new changes. Avoid duplication
- Check existing patterns for consistency
- Start by making the smallest reasonable changes

## Git workflow
- Create a new branch for significant changes when no clear branch exists
- Commit frequently throughout development
- NEVER skip or disable pre-commit hooks (flake8 validation)
- Ask how to handle uncommitted changes before starting

## Code quality
- ALL Python code MUST pass flake8 before committing
- Run: `flake8 app/ --max-line-length=120 --ignore=E501,W503`
- Fix any lint errors (F401 unused imports, E302 blank lines, W293 whitespace, etc.)
- Pre-commit hooks will block commits with flake8 errors - do not bypass with --no-verify

## Playback & Download Policy (BIBLIA - Never Regress)

### 1. **DB-First**
- Check `YouTubeDownload` table for existing `youtube_video_id`
- If file exists on disk → use directly
- Only mark `completed` after file exists on disk

### 2. **Playback - Streaming + Parallel Cache**
- **Immediate stream**: play while downloading
- **Parallel cache**: save file while playing
- If `youtube_video_id` exists → sync with YouTube video
- Do NOT mark as `completed` until file physically exists

### 3. **Synchronized Video**
- If track has `youtube_video_id` → show YouTube video
- Video plays **synchronized** with audio
- Controls (play/pause/skip) affect both video and audio

### 4. **YouTube API (if no link)**
- Search video on YouTube Data API v3
- If found → save to BD with `link_source="youtube_api"`, status `link_found`
- If not found → status `video_not_found`

### 5. **yt-dlp Fallback (if API fails)**
- If YouTube API quota exhausted (403/429) → use yt-dlp
- Use browser cookies (`--cookies-from-browser chrome`)
- Save to BD with `link_source="ytdlp"`
- Log to `storage/logs/ytdlp_fallback.log`

### 6. **Actual Download (when completing)**
- Correct path: `downloads/Artist/Album/Track.mp3`
- Format: **MP3** (not webm, not m4a)
- Verify file exists before marking as `completed`

### 7. **Logs & Debug**
- yt-dlp fallback → `storage/logs/ytdlp_fallback.log`
- Prefetch → `logs/uvicorn.log` (grep "youtube_prefetch")
- Errors → `logs/app.log`

### Golden Rules
- `youtube_video_id` only valid if 11 characters (`[A-Za-z0-9_-]{11}`)
- Parallel download is **best-effort**: 403 must not break playback
- This policy applies to Tracks, Playlists, and Albums
- Keep frontend and backend consistent

## Do not
- Skip frontmatter on any documentation files
- Use absolute URLs for internal links
- Include untested code examples
- Make assumptions - always ask for clarification


## Favorites Policy (SAGRADO - No Regresion)

- Fuente unica de verdad: tabla `userfavorite` en PostgreSQL.
- Favoritos son globales por usuario: clave logica `user_id + target_type + target_id`.
- `target_type` permitido: `ARTIST`, `ALBUM`, `TRACK`.
- Espejo obligatorio en UI: si marcas en Albums, debe verse en Tracks y Artists segun el tipo.
- Persistencia obligatoria: tras recargar, el estado se reconstruye desde BD (nunca solo estado local).
- Identidad consistente: todas las llamadas de favoritos y listados filtrados deben usar el mismo `user_id` efectivo (token activo).
- Regla de no-regresion: cualquier cambio que rompa el espejo Albums <-> Tracks (TRACK) se considera bug critico.

---

## Code Stability Rules (SAGRADO - Never Regress)

### Golden Rules for Any Code Change

1. **DO NOT modify working code without explicit user permission**
   - If it works, don't touch it
   - Only modify if user explicitly requests it or there's a critical bug

2. **If you MUST modify code:**
   - Understand the existing behavior BEFORE making changes
   - Run `flake8` BEFORE committing (will block on errors)
   - Test that the change doesn't break existing functionality
   - If you're unsure, ask the user before proceeding

3. **Before modifying ANY endpoint/function:**
   - Read the full file to understand the context
   - Identify all places that call this function
   - Verify the change won't break dependent code

4. **Async/Await Pattern (Critical):**
   - In async endpoints, ALWAYS use `await` with `session.exec()`
   - Wrong: `session.exec(select(...)).first()` → Fails silently in async
   - Correct: `(await session.exec(select(...))).first()`

5. **Imports (Critical):**
   - If you use a module (e.g., `asyncio`), you MUST import it
   - Missing imports cause F821 errors that flake8 will catch

6. **When in doubt, ask:**
   - "Do you want me to modify X?"
   - "Should I change this behavior?"
   - "I'm not sure about changing this code - can you confirm?"
