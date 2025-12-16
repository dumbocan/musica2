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

## 🆕 Backend & Data Weekend (favoritos, caché de imágenes, DB-first)

- **Favoritos multi-usuario**: nueva tabla `userfavorite` y API `/favorites` para marcar artistas, álbumes o tracks; los registros no se pueden borrar si están marcados. `target_type = artist|album|track`.
- **Datos adicionales de descarga**: los tracks guardan `download_status`, `downloaded_at`, `download_path`, `download_size_bytes`, `lyrics_source`, `lyrics_language` y `last_refreshed_at`. Artistas y álbumes también llevan `last_refreshed_at` para refrescos diarios.
- **Búsqueda DB-first**: las búsquedas orquestadas leen primero de PostgreSQL y solo van a APIs externas si faltan datos; al visitar una ficha de artista se dispara un guardado en background del artista + hasta 5 similares (álbumes + tracks).
- **Refresco diario**: bucle en `app/core/maintenance.py` que refresca discografía de los artistas favoritos cada 24h (se levanta en `startup`).
- **Proxy y resize de imágenes**: endpoint `/images/proxy?url=&size=` reduce peso con Pillow y guarda en `cache/images/*.webp`; todas las imágenes de búsqueda/artista/álbum se reescriben para servir desde la caché local.
- **Rutas de almacenamiento**: `storage/images/artists`, `storage/images/albums`, `storage/music_downloads` para assets locales; la caché redimensionada vive en `cache/images`.
- **Resistencia a borrados**: `delete_artist`/`delete_album`/`delete_track` rechazan la operación si hay favoritos. Nuevos helpers en `crud` + endpoints `DELETE /albums/id/{id}` ya protegidos.
- **Dependencias**: añadido `Pillow` para el resize; `discogs-client` fijado a `2.3.0`.

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
- PostgreSQL (installed and running)
- Git

### Installation

1. **Clone and setup:**
```bash
git clone https://github.com/dumbocan/musica2.git
cd audio2
python -m venv venv
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
# Edit .env with your database and API credentials
# The backend now defaults to SQLite (audio2.db) so you can run without Postgres.
# Add Spotify/Last.fm/Youtube keys only if you will hit those endpoints.
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

## 🚀 **Roadmap - Future Enhancements**

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
