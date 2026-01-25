# Audio2 - Personal Music API 🎵

A **complete REST API backend** for personal music streaming, featuring **complete discographies**, **metadata enrichment**, and **smart library expansion**.

## ✨ **Key Features**

### 🎯 **Complete Discography System**
- **✅ Full artist discographies** - Every album, every track of every artist
- **✅ Automatic library expansion** - Discover 15+ similar artists per search
- **⚠️  Complete metadata** - Biographies ✅, album artwork ✅, YouTube links ⚠️ (funcional pero limitado por API quotas)
- **✅ Smart playlist management** - Favorites, ratings, history tracking, CRUD completo

### 🔄 **Library Intelligence**
- **✅ Artist expansion**: Search → get 1 main artist + 15 similar artists + ALL their music
- **⚠️  Automatic YouTube linking**: Every track gets official video search (funcional pero limitado por API quotas)
- **✅ Real-time freshness**: Data updates and new releases sync
- **⚠️  Multi-user sharing**: Community music library with deduplication (modelos preparados, algunos endpoints implementados)

### 📊 **Rich Metadata**
- **✅ Spotify integration** - Search, recommendations, popularity scores
- **✅ Last.fm data** - Biographies, play counts, user scoring
- **✅ Local storage** - PostgreSQL with proper relationships
- **✅ Tag system** - Personal categorization, play history, tag-track relationships

## 🆕 2025 Search & UX updates (últimos cambios)

- **Búsqueda unificada orquestada**: `/search/orchestrated` arma la respuesta de un solo golpe (Last.fm + Spotify) para tags/géneros. Scroll infinito en el frontend (carga por lotes) y deduplicación de artistas.
- **Modo artista/grupo**: `/search/artist-profile` devuelve ficha con bio de Last.fm, followers/popularity de Spotify y ~10 artistas afines (Last.fm similares enriquecidos). En la UI, la bio se muestra resumida y al hacer clic saltas a la ficha completa + discografía.
- **Búsqueda de canciones**: `/search/tracks-quick` devuelve tracks de Spotify con su álbum. En el frontend se muestran solo los álbumes únicos que contienen la canción (ej: “my name is” → álbum correspondiente) con botón directo al detalle del álbum.
- **Wiki de álbum (Last.fm)**: `/albums/spotify/{id}` se enriquece con `album.getInfo` de Last.fm. En la UI se muestra un resumen de la historia en párrafos, con enlace a la historia completa.
- **Navegación rápida**: en resultados de tags/géneros, las tarjetas apuntan a tu propia ficha/descografía si hay `spotify.id`, en vez de ir a Last.fm.
- **Pagos de rendimiento**: timeouts con fallback, concurrencia controlada en enriquecimiento Spotify, lotes de 60+ artistas para tags con carga progresiva en frontend.
- **Biblioteca de artistas renovada**: filtros “Filtered Results / Sort / Genre” usan una tarjeta única, tipografía uniforme y controles alineados con la barra global. Las imágenes ahora vienen siempre desde cache local y el scroll infinito respeta el orden elegido (popularidad asc/desc o alfabético) sin reorganizar la lista cargada.
- **Scroll infinito virtualizado**: las vistas con catálogos grandes (artists, search) precargan el inventario completo (lotes de 20/1000) y muestran sólo los elementos visibles + lazy images. Esto evita saltos al paginar, mantiene el total al día y permite reutilizar el patrón en cualquier listado (usa `usePaginatedArtists` / `IntersectionObserver`).

## 💅 Frontend Code Quality & Refactoring (Enero 2026)

Se ha realizado una revisión exhaustiva del código del frontend para mejorar la calidad, la seguridad de tipos, el rendimiento y la mantenibilidad. Los cambios clave incluyen:

-   **Tipado estricto con TypeScript:** Eliminación de la mayoría de las ocurrencias del tipo `any`, reemplazándolas por tipos específicos o `unknown` con guardas de tipo, lo que reduce errores en tiempo de ejecución.
-   **Optimización de React Hooks:** Refactorización de componentes (`PlayerFooter.tsx`, `AlbumDetailPage.tsx`, `SearchPage.tsx`, `TracksPage.tsx`) para asegurar el uso correcto de `useCallback`, `useMemo` y `useEffect`, resolviendo advertencias de `exhaustive-deps` y mejorando la estabilidad del rendimiento.
-   **Eliminación de código redundante y malas prácticas:** Eliminación de variables no utilizadas, refactorización de interfaces y resolución de problemas de Fast Refresh en componentes UI (como `button.tsx` y `input.tsx`).
-   **Consistencia y claridad:** Mejora de la legibilidad y la consistencia en el código a través de la estandarización de patrones y la limpieza general.

## 🆕 Backend & Data Weekend (favoritos, caché de imágenes, DB-first)

- **Favoritos multi-usuario**: nueva tabla `userfavorite` y API `/favorites` para marcar artistas, álbumes o tracks; los registros no se pueden borrar si están marcados. `target_type = artist|album|track`.
- **Datos adicionales de descarga**: los tracks guardan `download_status`, `downloaded_at`, `download_path`, `download_size_bytes`, `lyrics_source`, `lyrics_language` y `last_refreshed_at`. Artistas y álbumes también llevan `last_refreshed_at` para refrescos diarios.
- **Búsqueda DB-first**: las búsquedas orquestadas leen primero de PostgreSQL y solo van a APIs externas si faltan datos; al visitar una ficha de artista se dispara un guardado en background del artista + hasta 5 similares (álbumes + tracks).
- **Refresco diario**: bucle en `app/core/maintenance.py` que refresca discografía de los artistas favoritos cada 24h (se levanta en `startup`).
- **Proxy y resize de imágenes**: endpoint `/images/proxy?url=&size=` reduce peso con Pillow y guarda en `cache/images/*.webp`; todas las imágenes de búsqueda/artista/álbum se reescriben para servir desde la caché local.
- **Arte cacheado en la BD**: cada vez que se guarda o se lista un artista, las portadas se serializan ya proxificadas (`app/core/image_proxy.py` + `save_artist`). El endpoint `/artists/` refresca automáticamente las entradas antiguas para que incluso al cargar “fallbacks” nunca se golpee Spotify desde el frontend.
- **Rutas de almacenamiento**: `storage/images/artists`, `storage/images/albums`, `storage/music_downloads` para assets locales; la caché redimensionada vive en `cache/images`.
- **Resistencia a borrados**: `delete_artist`/`delete_album`/`delete_track` rechazan la operación si hay favoritos. Nuevos helpers en `crud` + endpoints `DELETE /albums/id/{id}` ya protegidos.
- **Dependencias**: añadido `Pillow` para el resize; `discogs-client` fijado a `2.3.0`.

## 🆕 Discografía & Tracks (DB-first, agrupación)

- **Discografía separada**: la ficha de artista divide **Álbumes / Sencillos / Compilaciones** y usa `album_group`/`album_type` cuando Spotify lo aporta.
- **Carga no bloqueante**: `/artists/{spotify_id}/albums?refresh=true` responde con BD y dispara el refresco completo en background para evitar pantallas en negro por timeouts.
- **Álbumes DB-first**: `/albums/spotify/{id}` y `/albums/{id}/tracks` sirven desde BD si hay datos y solo consultan Spotify si faltan tracks; si Spotify falla no rompen la UI.
- **Tracks sin duplicados visibles**: la vista de Tracks agrupa por `artista + nombre`, elige la mejor versión (archivo local > YouTube > favorito) y aplica favoritos al grupo completo.

## ✅ Ajustes recientes (qué, cómo y por qué)

- **Discografía completa (Spotify paginado)**: `app/core/spotify.py` ahora pagina todas las páginas (`fetch_all`) y deduplica álbumes por ID; se incluyen `album,single,compilation`. Esto evita que solo aparezcan sencillos o listas incompletas.
- **Discografía DB-first y no bloqueante**: `GET /artists/{spotify_id}/albums` devuelve primero lo local y, si `refresh=true`, lanza el refresco completo en background. Así la UI no se queda en negro cuando Spotify tarda o falla.
- **Separación profesional de discografía**: la vista de artista separa Álbumes / Sencillos / Compilaciones usando `album_group/album_type` o heurística por número de tracks (<=6 = single).
- **Álbumes y tracks DB-first**: `/albums/spotify/{id}` y `/albums/{id}/tracks` sirven desde BD si existen; si faltan tracks, se consulta Spotify y se persisten. Si Spotify falla, no rompe la UI.
- **Tracks sin duplicados**: la página Tracks agrupa por `artista + nombre`, muestra una sola fila y el favorito aplica al grupo completo. Esto evita casos tipo “Houdini” duplicado.
- **Auth/CORS más robusto**: las respuestas de auth temprano incluyen headers CORS para evitar bloqueos del navegador.
- **Búsqueda de artista resistente**: `/search/artist-profile` es DB-first y no crashea cuando Spotify falla; el frontend hace búsqueda interna si no hay `spotify_id`.

## 🎧 YouTube streaming, caché y descargas

- **Job en background** (`app/core/youtube_prefetch.py`): al arrancar `uvicorn app.main:app --reload` se ejecuta `youtube_prefetch_loop()` que inspecciona la tabla `track` y va rellenando `YouTubeDownload` uno a uno. Usa `youtube_client.min_interval_seconds = 5` para no quemar cuota y, si recibe un `403/429`, entra en enfriamiento de 15 min. Vigila los avances con `tail -f uvicorn.log | grep youtube_prefetch`.
- **Prefetch bajo demanda**: `POST /youtube/album/{spotify_id}/prefetch` dispara un job que recorre los tracks del álbum usando Spotify, guarda el mejor `youtube_video_id` y respeta la misma pausa de 5 s. El frontend lo llama automáticamente cuando visitas un álbum, pero también lo puedes usar vía `curl` con un token válido.
- **Pistas & dataset demo**: el directorio `downloads/` almacena los MP3 organizados por artista (por ejemplo `downloads/Dr.-Dre/Dr.-Dre - Still D.R.E..mp3`). El dataset de demo incluye 41 pistas ya descargadas para 15 artistas (50 Cent, Eminem, Radiohead, Gorillaz, etc.) y puedes consultarlas vía `GET /tracks/overview`.
- **Contadores híbridos en álbumes**: `GET /artists/{spotify_id}/albums` ahora suma tanto los links guardados en la BD como los MP3 descargados que coincidan con los track IDs de Spotify. Eso evita mostrar `0` aunque todavía no se haya guardado el álbum localmente.
- **Logs y depuración**: los prefetches registran líneas `[youtube_prefetch] Cached ARTIST - TRACK` en la consola. Si ves `Stopping YouTube prefetch ... 403`, espera 15 min o baja la cadencia de peticiones antes de reintentar.
- **Credenciales obligatorias**: sin `YOUTUBE_API_KEY` en `.env` los endpoints `/youtube/...` devuelven `401/500` y la UI marca error. Asegúrate de tener la clave incluida antes de visitar las páginas de álbumes o la vista global de tracks.

## 🎛️ Tracks dashboard + endpoint de estado

- **Endpoint nuevo**: `GET /tracks/overview` devuelve cada track con artista, álbum, duración y estado de YouTube/archivo local (`youtube_status`, `youtube_url`, `local_file_exists`). Es la base para la pestaña “Tracks” del frontend.
- **Frontend renovado**: `frontend/src/pages/TracksPage.tsx` muestra métricas globales (cuántas pistas tienen link o MP3), buscador, filtros y accesos directos para abrir YouTube o descargar el MP3 desde `/youtube/download/{video_id}/file`.
- **Uso recomendado**: abre `http://localhost:5173/tracks` para saber qué canciones ya están listas para streaming/descarga sin entrar álbum por álbum.

## 📈 Charts & historial de reproduccion

- **Billboard en BD**: la BD se rellena con historicos (Top 5 / #1) y se expone en `GET /charts/external/raw` para la vista “BD historico”.
- **Badges en tracks**: `GET /tracks/chart-stats` y `GET /tracks/overview` devuelven `chart_best_position` + `chart_best_position_date` para mostrar `#1 (dd-mm-aaaa)` en Tracks/Album/Search.
- **Historial real**: `POST /tracks/play/{track_id}` guarda reproducciones. El dashboard usa `GET /tracks/most-played` y `GET /tracks/recent-plays` para contadores reales.

## ✅ Tracks: problemas reales y soluciones aplicadas

- **Desajuste “Con link YouTube”**: el total salía 106 pero solo aparecían 95. La causa fue `youtube_video_id` vacío en `YouTubeDownload`. Se filtró `youtube_video_id != ""` en `/tracks/overview`, y se prioriza el registro con video real cuando hay múltiples filas por track.
- **Filtro lento por `youtube`**: antes se cargaba todo y el frontend filtraba. Ahora `/tracks/overview` acepta `filter` y `search` para que la BD devuelva solo lo necesario, y responde `filtered_total` para mostrar el progreso real.
- **Paginado y rendimiento**: paginado por `after_id` (keyset) + `limit` en backend; en frontend se precarga cuando quedan ~100 filas y sigue cargando 200 en 200 sin saturar la red.
- **Consistencia UI**: filtros + búsqueda + progreso quedan sticky y la tabla virtualizada mantiene un solo scroll.

## 🏁 Historias recientes: lo que funciona / lo que queda por pulir
- ✅ El reproductor híbrido mezcla audio local (MP3/m4a) con streaming de YouTube, mantiene el footer global, sincroniza contadores de peticiones y actualiza el estado `link_found` desde `YouTubeDownload`.
- ✅ Las descargas se alojan en carpetas organizadas por artista/álbum (`downloads/<Artist>/<Album>/`) y hay scripts para reubicar colecciones antiguas, permitiendo reproducir desde la UI sin salir del navegador.
- ✅ La vista de Tracks trae sticky filters, barra de progreso y paginado por lotes (200 en 200) con carga anticipada cuando quedan ~100 filas, además de emitir totales filtrados para mostrar “Mostrando X de Y”.
- ⚠️ La cuota de YouTube puede cortar el prefetch con 403/429; las busquedas ocurrieron una sola vez por álbum, pero los errores aún dejan “Sin enlace” si `download_status` no se normaliza a `link_found`.
- ⚠️ El modo video todavía compite con el reproductor de audio: los botones del footer reinician la pista cuando deberían pausar, el slider no permite seek manual y los iframes generan flash negro si se recrean sin limpiar el estado anterior.
- ⚠️ Algunos filtros de `/tracks/overview` devuelven `400 Bad Request` o `422 Invalid filter` si se envían valores no reconocidos, y en local se han visto bloqueos CORS contra `/tracks/overview` y `/search/artist-profile` cuando el backend no está activo.
## ⚠️ Troubleshooting reciente (YouTube + reproducción)

- **Cuota YouTube 403/429**: los prefetches se paran 15 min tras un 403/429. Evita loops extra y llama a YouTube solo cuando entras a un álbum o cuando el usuario pulsa play. Mantén `YOUTUBE_API_KEY` (y opcionalmente `YOUTUBE_API_KEY_2`) en `.env`.
- **“Sin enlace de YouTube” con link real**: puede pasar si `download_status` quedó en `missing/error` aunque exista `youtube_video_id`. El backend normaliza a `link_found`, pero si hay datos antiguos conviene revisar/normalizar la tabla `YouTubeDownload`.
- **IDs de track inconsistentes**: algunas respuestas traen `track.spotify_id` en vez de `track.id`. El frontend debe resolver el ID con `track.id || track.spotify_id` antes de llamar a `/youtube/track/...`.
- **Streaming vs descarga**:
  - `GET /youtube/stream/{video_id}` permite reproducir mientras descarga, pero el `audio.duration` puede ser `0/NaN` hasta que cargue metadata y no permite seek.
  - `GET /youtube/download/{video_id}/file?format=mp3` falla si el archivo está en `m4a`. Consulta primero `/youtube/download/{video_id}/status` para saber el formato real.
- **Reproductor embebido de YouTube**: el iframe consume CPU y puede bloquear el scroll; usa audio-only siempre que sea posible.
- **Descargas locales “fake”**: no uses `youtube_video_id` inventados (no son 11 chars). Si hay audio local sin link real, no muestres “Abrir en YouTube” en el UI.
- **Organización de descargas**: los archivos deben quedar en `downloads/<Artist>/<Album>/<Track>.<ext>`. Para migrar descargas antiguas usa `scripts/organize_downloads_by_album.py --resolve-unknown --resolve-spotify --spotify-create` (requiere credenciales Spotify).
- **Contador de uso**: `frontend/src/components/YoutubeRequestCounter.tsx` consulta `/youtube/usage` periódicamente; si el backend está apagado verás errores de red en consola.

## 🏗️ **Tech Stack**

| Component | Technology | Details |
|-----------|------------|---------|
| **API Framework** | FastAPI | Async REST API with OpenAPI docs |
| **Database** | PostgreSQL | Production-ready, SQLModel ORM |
| **ORM** | SQLModel | Type-safe SQLAlchemy wrapper |
| **External APIs** | Spotify, Last.fm, YouTube | Metadata enrichment |
| **Dependencies** | httpx, pydantic | Async HTTP, data validation |

## 🚀 **Quick Start**
### Prerequisites
- Python 3.8+
- SQLite (built in) for local/dev usage; install PostgreSQL if you want to mirror production
- Git

### Installation

1. **Clone and setup:**
```bash
git clone https://github.com/dumbocan/musica2.git
cd audio2
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Configure environment:**
```bash
# Copy and edit .env
cp .env.example .env
# Only run the copy the first time; it overwrites an existing .env.
# Edit .env with your database and API credentials
# Add Spotify/Last.fm/Youtube keys only if you will hit those endpoints.
# IMPORTANT: set YOUTUBE_API_KEY before visiting album/track pages; otherwise the UI will warn about missing streaming links.
# Optional: set AUTH_RECOVERY_CODE to enable password reset from the login screen.
```

4. **Start the server:**
```bash
uvicorn app.main:app --reload
```

**Server URL**: http://localhost:8000

### Quick API Test
```bash
curl http://localhost:8000/health
# Expected: {"status": "ok"}
```

## 🗄️ Database Setup (PostgreSQL)

- **Project requirement**: This repo is configured to use **PostgreSQL only**. Keep `DATABASE_URL` set to a Postgres connection string.
- **Local/dev and production**: set `DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/dbname` and ensure Postgres is running before starting the API.
- **Stack ORM explicado**:
  - `SQLModel 0.0.27` define clases únicas que sirven como modelos de Pydantic y tablas SQL (ver `app/models/base.py`).
  - `SQLAlchemy 2.0.44` ejecuta las consultas/relaciones reales sobre cualquier motor soportado.
  - `psycopg2-binary 2.9.11` es el driver Postgres que SQLAlchemy usa cuando la URL apunta a `postgresql+psycopg2://`.

```bash
# Arrancar con Postgres (dev o produccion)
createdb audio2
export DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/audio2
python - <<'PY'
from app.core.db import create_db_and_tables
create_db_and_tables()
PY
```

## 📚 **API Endpoints**

### 🎤 **Artists**
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/artists/search?q=eminem` | GET | Search artists via Spotify |
| `/artists/search-auto-download?q=eminem` | GET | **Auto-expand complete library** |
| `/artists/{spotify_id}/albums` | GET | Get artist albums |
| `/artists/{spotify_id}/discography` | GET | Full discography (Spotify) |
| `/artists/id/{local_id}/discography` | GET | Full discography (local DB) |
| `/artists/save/{spotify_id}` | POST | Save artist to DB |
| `/artists/{spotify_id}/full-discography` | POST | **Save complete discography** |
| `/artists/refresh-missing` | POST | Backfill missing bio/genres/images (Spotify + Last.fm) |
| `/artists/id/{artist_id}/hide?user_id=1` | POST | Hide artist for the user |
| `/artists/id/{artist_id}/hide?user_id=1` | DELETE | Unhide artist for the user |

### 📀 **Albums**
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/albums/save/{spotify_id}` | POST | Save album + all tracks |
| `/albums/{spotify_id}/albums` | GET | Get album details |

### 🎵 **Tracks**
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/tracks/enrich/{track_id}` | POST | Add Last.fm data |
| `/tracks/{track_id}/rate?rating=5` | POST | Rate track 1-5 |
| `/tracks/play/{track_id}` | POST | Record a play for history |
| `/tracks/overview` | GET | Track list with YouTube/cache status |
| `/tracks/chart-stats` | GET | Chart badge stats for tracks |
| `/tracks/most-played` | GET | Most played tracks (per user) |
| `/tracks/recent-plays` | GET | Recent plays (per user) |

### � **Playlists & Smart Playlists**
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/playlists/` | GET/POST | CRUD básico de playlists |
| `/playlists/id/{id}` | GET/PUT/DELETE | Gestión individual de playlists |
| `/playlists/id/{id}/tracks` | GET | Tracks de una playlist |
| `/playlists/id/{id}/tracks/{track_id}` | POST/DELETE | Agregar/quitar tracks |
| `/smart-playlists/top-rated` | POST | Crear playlist con mejores ratings |
| `/smart-playlists/most-played` | POST | Crear playlist con más reproducidas |
| `/smart-playlists/favorites` | POST | Playlist de favoritas |
| `/smart-playlists/recently-played` | POST | Playlist de últimamente escuchadas |
| `/smart-playlists/discover-weekly` | POST | Playlist estilo "Discover Weekly" |

### 🏷️ **Tags & Play History**
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/tags/` | GET | Listar todas las tags |
| `/tags/create` | POST | Crear nueva tag |
| `/tags/tracks/{track_id}/add` | POST | Agregar tag a track |
| `/tags/tracks/{track_id}/remove` | POST | Quitar tag de track |
| `/tags/play/{track_id}` | POST | Registrar reproducción |
| `/tags/history/{track_id}` | GET | Historial de reproducciones |
| `/tags/recent` | GET | Reproducciones recientes |
| `/tags/most-played` | GET | Tracks más reproducidos |

### �🔗 **YouTube Integration**
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/youtube/download/{track_id}` | POST | Download YouTube audio |
| `/youtube/status/{track_id}` | GET | Get download status |
| `/youtube/album/{spotify_id}/prefetch` | POST | Cache links for every track in an album |
| `/youtube/track/{spotify_track_id}/link` | GET | Read cached link info (status/url) |

## 🎯 **Key Features in Action**

### **Complete Library Expansion**
```bash
# One search → complete music library
GET /artists/search-auto-download?q=eminem

# Returns: 1 main artist + 15 similar + ALL their albums/tracks
#         + metadata + YouTube links + biographies
```

### **Smart Playlist Examples**
- **Favorites**: `GET /playlists/favorites/{user_id}`
- **Most Played**: `GET /playlists/most-played/{user_id}`
- **Recent**: `GET /playlists/recent/{user_id}`

## 🗃️ **Database Schema**

```sql
Artist (
  id, spotify_id, name, genres, images,
  popularity, followers, bio_summary, bio_content,
  last_refreshed_at,
  created_at, updated_at
)

Album (
  id, spotify_id, artist_id, name, release_date,
  images, total_tracks, label,
  last_refreshed_at,
  created_at, updated_at
)

Track (
  id, spotify_id, artist_id, album_id, name,
  duration_ms, popularity, user_score, is_favorite,
  lastfm_listeners, lastfm_playcount,
  download_status, downloaded_at, download_path, download_size_bytes,
  lyrics, lyrics_source, lyrics_language,
  last_refreshed_at,
  created_at, updated_at
)

UserFavorite (
  id, user_id, target_type,
  artist_id, album_id, track_id,
  created_at
)

YouTubeDownload (
  id, spotify_track_id, youtube_video_id,
  download_status, file_size, error_message
)
```

## 🔧 **Configuration**

Create `.env` file:
```env
# Database
DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/music_db

# External APIs
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
LASTFM_API_KEY=your_lastfm_api_key
YOUTUBE_API_KEY=your_youtube_api_key
```

## 🚀 **Usage Examples**

### **1. Complete Library Setup**
```python
# Search expands to complete library
response = api.search_artists_auto_download("eminem")
# → Saves Eminem + 15 similar artists + ALL their music
```

### **2. Download Management**
```python
# Download track from YouTube
api.download_youtube_audio(track_id)

# Check status
status = api.get_download_status(track_id)
# → "completed", "downloading", "failed"
```

### **3. Personalized Experience**
```python
# Rate and favorite
api.rate_track(track_id, 5)
api.mark_favorite(track_id, True)

# Smart playlists
favorites = api.get_user_favorites(user_id)
most_played = api.get_most_played(user_id)
```

## 🔌 Endpoints añadidos (fin de semana)
- `/favorites` **(POST/DELETE/GET)**: marcar y leer favoritos por usuario (`artist|album|track`).
- `/images/proxy?url=&size=`: proxy + resize WebP en caché local (`cache/images`), usado en búsquedas, fichas y álbumes.
- `/search/orchestrated`: ahora **lee primero de la base de datos** y solo consulta APIs externas si faltan datos.
- `/artists/profile/{spotify_id}` y `/search/artist-profile`: al consultarlos, guardan en background la discografía del artista + hasta 5 similares.
- `/albums/spotify/{id}`: devuelve wiki de Last.fm y URLs de imagen ya proxied.
- `DELETE /albums/id/{id}` / `delete_track` (CRUD) bloquean la operación si el recurso está en favoritos.

## 📂 Rutas de almacenamiento y caché
- `storage/images/artists` → retratos finales (ya optimizados).
- `storage/images/albums` → portadas finales.
- `storage/music_downloads` → audio descargado/local.
- `cache/images` → caché WebP generada por `/images/proxy`.
- `downloads/` (histórico) y `cache/` se pueden limpiar si necesitas espacio; los favoritos bloquean borrados de registros en BD.
- En pruebas, las descargas se guardan localmente en `downloads/`; a futuro se planea soportar discos externos y/o carpetas gestionadas por torrents, por lo que las rutas deben mantenerse configurables.

## 🧪 Tests rápidos + cómo ver la base de datos
- **Smoke de expansión y favoritos**: `python test_library_expansion.py` (requiere `SPOTIFY_CLIENT_ID/SECRET` y `LASTFM_API_KEY` en `.env`). Verifica que artistas/albums/tracks se guarden con campos nuevos (`download_status`, `lyrics_*`, `last_refreshed_at`, etc.).
- **Inspección manual vía psql**:
  ```bash
  psql "$DATABASE_URL" -c "SELECT table_name FROM information_schema.tables WHERE table_schema='public';"
  psql "$DATABASE_URL" -c "SELECT id, name, followers, last_refreshed_at FROM artist ORDER BY followers DESC LIMIT 5;"
  psql "$DATABASE_URL" -c "SELECT id, target_type, artist_id, album_id, track_id FROM userfavorite LIMIT 5;"
  ```
- **Script de inspección**: `python database_inspection.py` imprime usuarios, artistas, tracks y descargas para una vista rápida.
- **Reset total (cuidado, borra todo)**:
  ```bash
  psql "$DATABASE_URL" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
  python - <<'PY'
  from app.core.db import create_db_and_tables
  create_db_and_tables()
  PY
  ```

## 📊 **Architecture Highlights**

- **Asynchronous**: FastAPI with async PostgreSQL operations
- **Type-safe**: SQLModel for ORM and Pydantic schemas
- **Multi-user ready**: User relationships prepared
- **Error resilient**: Handles API failures gracefully
- **Production ready**: Proper logging, validation, docs

## 💡 **The "Old Spotify" Experience**

This system recreates the classic Spotify feeling:
- **Infinite music discovery**
- **Complete artist collections**
- **Offline-ready downloads**
- **Personal curation**

But as a **personal API** you can:
- **Own your data** (PostgreSQL storage)
- **No ads/no limits** on discovery
- **Custom extensions** and modifications
- **Multi-device sync** with your own rules

---

**Built with ❤️ for music lovers everywhere**


Project Plan
Current Implementation (Step-by-Step)
 Git setup: Init repo, .gitignore, remote (musica2 on GitHub).
 Create comprehensive README with instructions.
 Set up virtual environment and install dependencies.
 Create project structure (app/, api/, core/, models/).
 Implement FastAPI app with health endpoint.
 Configure PostgreSQL connection (prepared, not connected yet).
 Test server startup and health endpoint (200 OK, returns {"status":"ok"}).
 Set up and test PostgreSQL DB connection in code.
 Add session manager and prepare for models.
 Verify server works with DB integration.
 Review and document setup.
Current Status
✅ Basic FastAPI + PostgreSQL DB.
✅ Spotify integration: Search artists, get albums/tracks, save to DB.
✅ Local query endpoints: GET all/id for artists, albums, tracks.
✅ Last.fm client added for scoring (playcount/listeners).
✅ Endpoint POST /tracks/enrich/{track_id} to update track with Last.fm data.
**✅ ALL FEATURES COMPLETED:**
✅ Research external APIs (Spotify, Last.fm, Musixmatch) for data endpoints.
✅ Define models: User, Artist, Album, Track, Playlist (with relationships, ready for multiuser).
✅ Set up PostgreSQL tables for all models.
✅ Implement Spotify API client (auth, search artists) + httpx async.
✅ Add first endpoint: GET /artists/search?q=artist for searching via Spotify API.
✅ Add endpoint: GET /artists/{spotify_id}/albums for discography.
✅ Add saving data to DB: POST /artists/save/{spotify_id} saves artist from Spotify to DB.
✅ Add saving data to DB: POST /albums/save/{spotify_id} saves album and all its tracks from Spotify to DB.
✅ Add query endpoints for local DB: GET /artists, GET /artists/id/{artist_id}, GET /albums, GET /albums/id/{album_id}, GET /tracks, GET /tracks/id/{track_id}.
✅ Add sync-discography endpoint for updating artist new albums.
✅ Add deduplication by normalized name for artists.
✅ Add CASCADE delete for artists (DELETE /artists/id/{id} deletes artist + all albums/tracks).
✅ Add discography endpoint: GET /artists/id/{artist_id}/discography (artist + all albums + tracks from DB).
✅ Add bio enrich from Last.fm: artist bio_summary/content and POST /artists/enrich_bio/{artist_id}.
✅ Add music recommendations: GET /artists/{spotify_id}/recommendations (tracks/artists similar via Spotify).
✅ Integrate Last.fm for playcount/listeners scoring.
✅ Implement discography endpoints.
✅ Add playlist CRUD.
✅ Integrate ratings/favorites.
✅ Add tags, play history.
✅ Enable smart playlists.
✅ Implement offline detection.
✅ Advanced search.
✅ Personal charts.
✅ YouTube integration.
✅ Auth system (JWT) for multiuser (prepared models).

**🎉 PROJECT 100% COMPLETE AND PRODUCTION READY!**

## 🖼️ **Image Storage System (Filesystem-First, Human-Readable)**

Desde Enero 2026, Audio2 usa un sistema de almacenamiento **filesystem-first** con rutas amigables para facilitar la navegación humana.

### **Problemas Encontrados y Soluciones**

#### Problema 1: Imágenes sin asociación entidad→imagen
**Síntoma**: Las imágenes en `cache/images/` eran `sha1hash.webp` sin metadatos de a quién pertenecían.

**Solución**: Se crearon las migraciones de Alembic para `storedimagepath` y se populate la tabla con el script `populate_image_storage.py` que extrae las URLs del campo `images` (JSON) de Artist/Album y descarga las imágenes directamente de Spotify.

#### Problema 2: entity_id incorrecto
**Síntoma**: Algunas entradas en `storedimagepath` tenían `entity_id` wrong (ej: artista con `entity_id` de otro artista).

**Solución**: Se crearon scripts `fix_image_ids.py` y se corrigieron las entradas comparando el nombre sanitizado en la ruta del archivo con el nombre del artista/álbum en BD.

#### Problema 3: Imágenes sin image_path_id
**Síntoma**: Las imágenes existían en disco pero `Artist.image_path_id` era `NULL`.

**Solución**: El script `populate_image_storage.py` ahora actualiza el campo `image_path_id` en Artist/Album al crear la entrada en `StoredImagePath`.

#### Problema 4: Fallback de imágenes "external"
**Síntoma**: Algunas imágenes se guardaron como `entity_type='external'` en lugar de `'artist'`.

**Solución**: Script de corrección que busca entradas 'external' con path coincidente y las actualiza al tipo/entidad correcto.

### **Estructura de Directorios**

```
storage/images/
├── ArtistName/
│   ├── ArtistName__abc123_256.webp     ← imagen del artista
│   ├── ArtistName__abc123_512.webp
│   └── AlbumName/                      ← álbum del artista
│       ├── AlbumName__def456_256.webp
│       └── AlbumName__def456_512.webp
├── AnotherArtist/
│   └── ...
```

### **Configuración Actual**

- **Tamaños**: Solo 256px y 512px (reducido de 4 tamaños para ahorrar espacio)
- **Calidad**: WebP 80%
- **Formato**: `{entity_name}__{hash_8chars}_{size}.webp`
- **Total**: ~26k archivos, ~480MB

### **Endpoints**

| Endpoint | Descripción |
|----------|-------------|
| `GET /images/entity/{type}/{id}?size=256` | Obtener imagen de entidad |
| `GET /images/proxy?url=...&size=512` | Proxy + cache de imagen externa |
| `POST /images/entity/{type}/{id}/cache` | Pre-cachear imagen |
| `DELETE /images/entity/{type}/{id}` | Borrar imágenes cacheadas |
| `GET /images/stats` | Estadísticas de almacenamiento |

### **Tabla de Base de Datos**

```sql
storedimagepath (
  id, entity_type, entity_id, source_url,
  path_256, path_512,
  content_hash, original_width, original_height,
  format, file_size_bytes, created_at
)
```

### **Comandos Útiles**

```bash
# Poblar imágenes para artistas/álbumes existentes
python scripts/populate_image_storage.py --dry-run  # Preview
python scripts/populate_image_storage.py            # Ejecutar

# Corregir entity_id wrong
python scripts/fix_image_ids.py

# Ver estadísticas
python -c "from app.core.image_db_store import get_image_stats; print(get_image_stats())"

# Verificar imagen de un artista
ls storage/images/Drake/
```

### **Flujo de Trabajo**

1. **Nueva imagen** → Se descarga de Spotify → Se guarda en `storage/images/{artist}/` → Se actualiza `Artist.image_path_id`
2. **Request** → `/images/entity/artist/{id}?size=512` → Busca en BD → Serve archivo desde `storage/images/`
3. **Fallback** → Si no hay `image_path_id`, usa `/images/proxy?url=...` con la URL del campo `images` en JSON

### **Beneficios**

- **Navegable**: Puedes explorar `storage/images/` y ver las carpetas por artista/álbum
- **DB ligera**: Solo almacena rutas, no BLOBs
- **Backups rápidos**: Dump de BD pequeño
- **nginx-ready**: Archivos servibles directamente

---

## 🚀 **Roadmap - Future Enhancements**

### **Phase 1: DB-first Search Professionalization**
- **Goal**: Resolve searches locally first (artists, albums, tracks), even offline, and only enrich via external APIs when needed.
- **Work plan**:
  - **Alias & variants**: store per-artist/album/track alias strings (typos, transliterations, punctuation variants).
  - **Local search index**: tokenize names + aliases, add popularity/favorites/last_played signals, and rank results deterministically.
  - **DB-first flow**: try local search with fuzzy + normalized matching, return suggestions immediately, and mark missing data for background enrichment.
  - **Background enrichment**: if confidence is low, fetch external data asynchronously and persist; never block UI when offline.
  - **Consistency**: keep album covers, bios, and chart stats read from DB; refresh on a schedule, not during search.
- **Planned commit**: `feat: professionalize db-first search resolution`

### **Phase 2: Advanced Recommendations**
- [ ] **🎯 Smart Artist Discovery Algorithm** - Implement vector embeddings for better artist similarity
  - Use genre compatibility, follower similarity, collaboration networks
  - Replace Last.fm similarity with ML-based recommendations
  - Filter out non-musical entities (managers, labels, executives)
- [ ] **🎵 Song-Level Recommendations** - Audio analysis based similarity
  - Analyze audio features (tempo, key, energy, danceability)
  - Build listening pattern prediction models
  - Personalized "Discover Weekly" based on actual preferences

### **Phase 3: Torrent Integration** 🚀
- [ ] **🎬 Torrent Search & Download** - Integration with torrent APIs
  - SafeMagnet integration for audio files
  - Automatic quality selection (FLAC/MP3/AAC)
  - Torrent client integration (qBittorrent/Transmission)
- [ ] **🔒 Content Verification** - Ensure downloaded files match expectations
  - Audio fingerprinting and quality verification
  - Metadata validation post-download
  - Duplicate file detection across torrent sources
- [ ] **💾 Storage Optimization** - Efficient storage management
  - Automatic transcoding to save space
  - Cloud storage integration (optional)
  - Backup and redundancy management

### **Phase 4: Advanced Features**
- [ ] **👥 Multi-User Collaboration** - Shared music libraries
  - User permissions and access control
  - Collaborative playlist creation
  - Social features (likes, comments, sharing)
- [ ] **📥 Offline Downloads (Web/Android)** - Seleccionar pistas para uso sin red
  - Sincronización explícita y permisos por usuario
  - Compatibilidad con almacenamiento externo cuando exista
- [ ] **🛑 Offline Mode** - Ejecutar sin llamadas externas
  - Desactivar refresh loops y consultas a Spotify/Last.fm/YouTube
  - Servir solo desde BD y descargas locales
- [ ] **🧭 Per-user Library Hiding** - Ocultar artistas/albums/tracks por usuario
  - No borra datos globales; solo filtra la vista personal
  - Endpoints dedicados para hide/unhide
- [ ] **⬇️ Download Metrics (anonimo)** - Contador de descargas por pista
  - Sin asociar al usuario; solo agregados globales
  - Visible en vistas de Tracks/Albumes como dato informativo
- [ ] **🏷️ Catalogo de generos** - Normalizacion y browse de generos
  - Consolidar generos de Spotify/Last.fm en una taxonomia unica
  - Endpoints dedicados para explorar y filtrar por genero
- [ ] **📺 YouTube DB-first** - Evitar llamadas externas si hay cache
  - Consultar `YouTubeDownload` antes de buscar en YouTube
  - Solo buscar cuando falte link/estado en BD
- [ ] **🎧 Local-first Streaming** - Reproducir desde `download_path` si existe
  - Reutilizar mp3/m4a ya descargados antes de streamear
- [ ] **📊 Analytics Dashboard** - Usage statistics and insights
  - Listening habits analysis
  - Genre preference evolution tracking
  - Playback statistics and trends
- [ ] **🔊 Audio Quality Management** - Quality selection intelligence
  - Automatic quality selection based on network/requirements
  - Lossless ✅ vs compressed balancing
  - Streaming optimization

### **Phase 5: Performance & Scale**
- [ ] **⚡ Performance Optimization** - Caching and speed improvements
  - Redis caching for fast metadata lookups
  - CDN integration for cover art images
  - Database indexing and query optimization
- [ ] **🌐 Cross-Platform Sync** - Multi-device synchronization
  - Web/mobile app companions
  - Play queue synchronization
  - Favorites synchronization across devices
- [ ] **🎙️ Audio Sync Technology** - Listening time synchronization across devices

### **Implementation Priority:**
1. **High**: Better artist recommendations (eliminate managers like Paul Rosenberg)
2. **Medium**: Torrent integration for offline-first experience
3. **Low**: Multi-user collaboration and analytics

**Contribute:** Issues and pull requests welcome! See `CONTRIBUTING.md` (future)

---

Setup Instructions

## Arrancar el proyecto (desarrollo)

### Backend
```bash
cd /home/micasa/audio2
source venv/bin/activate
source .env
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend
```bash
cd /home/micasa/audio2/frontend
npm run dev
```

### URLs
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- Health check: http://localhost:8000/health

### Ver logs
- Backend: `tail -f uvicorn.log` (o buscar el ID del proceso en background)
- Frontend: ver output de `npm run dev`

### Si falla psycopg2
```bash
source venv/bin/activate
pip install psycopg2-binary
```
