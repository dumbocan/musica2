# API Research for Audio2 - External Music Data Sources

This document outlines key endpoints from Spotify, Last.fm, and other APIs for building the music database models (Artist, Album, Track, etc.).

## 1. Spotify Web API (https://developer.spotify.com/documentation/web-api/)

### Authentication
- OAuth 2.0: Access token required for most endpoints.
- Supports Client Credentials flow for non-user data.

### Key Endpoints for Discography/Track Data

#### Artists
- **GET /v1/search?type=artist&q={artist_name}**:
  - Returns: artists (list with id, name, genres, followers, images, popularity)
  - Use: Find artist by name.

- **GET /v1/artists/{artist_id}**:
  - Returns: id, name, genres, followers, images, popularity, type ('artist')
  - Use: Get full artist info.

- **GET /v1/artists/{artist_id}/albums?include_groups=album (optional single, compilation)**:
  - Returns: items[] (album.id, name, total_tracks, release_date, images, type)
  - Use: Get all albums by artist (pagination needed for many).

#### Albums
- **GET /v1/albums/{album_id}**:
  - Returns: id, name, artists[], release_date, total_tracks, images, label, popularity, tracks (summary)
  - Use: Get full album details.

- **GET /v1/albums/{album_id}/tracks**:
  - Returns: items[] (id, name, artists[], disc_number, duration_ms, preview_url, track_number)
  - Use: Get tracks in album (pagination).

#### Tracks
- **GET /v1/tracks/{track_id}**:
  - Returns: id, name, artists[], album (summary), duration_ms, popularity, preview_url, external_urls (Spotify link)
  - Use: Full track details.

#### Recommendations/Search
- **GET /v1/search?type=track&q={track_name}**:
  - Returns: tracks (id, name, artists, album, etc.)
  - Use: Search tracks.

- **GET /v1/recommendations?seed_artists={artist_ids}&seed_tracks={track_ids}&seed_genres={genres}**:
  - Returns: tracks[] (recommended tracks based on seeds)
  - Use: Personalized recommendations.

### Rate Limits
- 25 requests/sec for search, albums; higher for audio features.
- Pagination: limit=50, offset for large lists.

### Data Fields to Store in Models
- Artist: spotify_id, name, genres[], images[], popularity, followers
- Album: spotify_id, name, artists[], release_date, total_tracks, images[], label
- Track: spotify_id, name, artists[], album_id, duration_ms, preview_url, external_urls['spotify'], popularity

## 2. Last.fm API (https://www.last.fm/api)

### Authentication
- API key (no OAuth needed for public data).

### Key Endpoints
- **artist.getTopTracks**:
  - Params: artist, api_key
  - Returns: track[] (name, playcount (scoring!))
  - Use: Scoring de tracks/listeners.

- **track.getInfo**:
  - Params: artist, track, api_key
  - Returns: name, artist, album, playcount, listeners, tags[], id?
  - Use: Playcount per track for scoring.

- **album.getInfo**:
  - Returns: album (name, artist, tracks[], tags[], playcount, listeners)
  - Use: Albums data with playcounts.

- **user.getLovedTracks** (si con user auth): Tracks favorited.

### Rate Limits
- 1 request/sec, but can apply for higher.

### Data Fields
- Track: lastfm_playcount, lastfm_listeners
- Album: lastfm_playcount (for scoring vs. Spotify popularity)

## 3. Lyrics APIs (for Track.lyrics field)
- **Musixmatch API** (https://developer.musixmatch.com):
  - **track.lyrics.get**: Params: track_id/apikey, Returns: lyrics_body
- **Genius API** (https://docs.genius.com):
  - Search/scraping with PyLyrics, pero oficial para adapt timestamps.

## Integration Plan for Models
1. Define models in app/models/ (User, Artist, Album, Track) with fields from above.
2. Add pydantic models for API responses validation.
3. Create API client functions in app/core/spotify.py, lastfm.py (async with httpx).
4. Store downloaded data in DB with foreign keys.
5. Endpoints in app/api/ for search artist -> fetch discography -> save to DB.

This covers the data needs: discografía completa, scoring from playcounts, lyrics, recommendations.
