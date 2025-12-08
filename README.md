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
  created_at, updated_at
)

Album (
  id, spotify_id, artist_id, name, release_date,
  images, total_tracks, label, created_at
)

Track (
  id, spotify_id, artist_id, album_id, name,
  duration_ms, popularity, user_score, is_favorite,
  lastfm_listeners, lastfm_playcount, created_at
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
Future Tasks (to be implemented incrementally)
 Research external APIs (Spotify, Last.fm, Musixmatch) for data endpoints.
 Define models: User, Artist, Album, Track, Playlist (with relationships, ready for multiuser).
 Set up PostgreSQL tables for all models.
 Implement Spotify API client (auth, search artists) + httpx async.
 Add first endpoint: GET /artists/search?q=artist for searching via Spotify API.
 Add endpoint: GET /artists/{spotify_id}/albums for discography.
 Add saving data to DB: POST /artists/save/{spotify_id} saves artist from Spotify to DB.
 Add saving data to DB: POST /albums/save/{spotify_id} saves album and all its tracks from Spotify to DB.
 Add query endpoints for local DB: GET /artists, GET /artists/id/{artist_id}, GET /albums, GET /albums/id/{album_id}, GET /tracks, GET /tracks/id/{track_id}.
 Add sync-discography endpoint for updating artist new albums.
 Add deduplication by normalized name for artists.
 Add CASCADE delete for artists (DELETE /artists/id/{id} deletes artist + all albums/tracks).
 Add discography endpoint: GET /artists/id/{artist_id}/discography (artist + all albums + tracks from DB).
 Add bio enrich from Last.fm: artist bio_summary/content and POST /artists/enrich_bio/{artist_id}.
 Add music recommendations: GET /artists/{spotify_id}/recommendations (tracks/artists similar via Spotify).
 Integrate Last.fm for playcount/listeners scoring.
 Implement discography endpoints.
 Add playlist CRUD.
 Integrate ratings/favorites.
 Add tags, play history.
 Enable smart playlists.
 Implement offline detection.
 Advanced search.
 Personal charts.
 YouTube integration.
 Auth system (JWT) for multiuser (prepared models).
Setup Instructions
