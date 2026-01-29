"""
Music Intelligence Module - Lógica de generación de playlists, bios y recomendaciones.

Este módulo usa el cliente Ollama para generar contenido inteligente
basado en los datos de la biblioteca musical del usuario.

Arquitectura:
- PostgreSQL → Backend (extracción de datos) → Ollama (procesamiento) → JSON estructurado
"""

import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from sqlmodel import select, func
from collections import Counter

from .ollama_service import ollama_client, OllamaConnectionError, check_ollama_health
from ..core.db import get_session
from ..models.base import (
    Artist, Album, Track, UserFavorite, PlayHistory
)
from ..utils.prompts import (
    AUDIO2_SYSTEM_PROMPT, PLAYLIST_GENERATION_PROMPT,
    ARTIST_BIO_PROMPT, ALBUM_SUMMARY_PROMPT,
    SEMANTIC_SEARCH_PROMPT, PERSONAL_RECOMMENDATIONS_PROMPT,
    USER_INSIGHTS_PROMPT, format_list
)

logger = logging.getLogger(__name__)


@dataclass
class TrackInfo:
    """Información mínima de una canción para el LLM."""
    id: int
    name: str
    artist: str
    artist_id: int
    album: Optional[str]
    album_id: Optional[int]
    duration_ms: int
    popularity: int
    user_score: Optional[int]
    is_favorite: bool
    genres: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ArtistInfo:
    """Información mínima de un artista para el LLM."""
    id: int
    name: str
    genres: List[str]
    popularity: int
    followers: int
    bio_summary: Optional[str]
    top_tracks: List[str]
    albums_count: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AlbumInfo:
    """Información mínima de un álbum para el LLM."""
    id: int
    name: str
    artist: str
    artist_id: int
    release_date: str
    total_tracks: int
    popularity: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MusicIntelligenceError(Exception):
    """Error general del módulo de inteligencia musical."""
    pass


class InsufficientDataError(MusicIntelligenceError):
    """Error cuando no hay suficientes datos para generar respuesta."""
    pass


class MusicIntelligenceService:
    """
    Servicio principal de inteligencia musical.

    Proporciona métodos para:
    - Generar playlists inteligentes
    - Crear biografías de artistas
    - Generar resúmenes de álbumes
    - Recomendaciones personalizadas
    - Búsqueda semántica
    - Análisis de patrones de escucha
    """

    def __init__(self):
        """Inicializar el servicio."""
        self.ollama = ollama_client

    def is_available(self) -> bool:
        """Verificar si el servicio está disponible."""
        return self.ollama.is_available()

    # =========================================================================
    # HELPER METHODS - Extracción de datos
    # =========================================================================

    def _get_user_favorite_artists(self, user_id: int, limit: int = 10) -> List[ArtistInfo]:
        """Obtener artistas favoritos del usuario."""
        session = get_session()
        try:
            favorites = session.exec(
                select(UserFavorite)
                .where(UserFavorite.user_id == user_id)
                .where(UserFavorite.target_type == "artist")
                .limit(limit * 2)  # Get more to filter
            ).all()

            artist_ids = [f.artist_id for f in favorites if f.artist_id]
            artists = session.exec(
                select(Artist).where(Artist.id.in_(artist_ids))
            ).all()

            artist_map = {a.id: a for a in artists}
            result = []
            for fav in favorites:
                if fav.artist_id and fav.artist_id in artist_map:
                    artist = artist_map[fav.artist_id]
                    genres = self._parse_genres(artist.genres)
                    result.append(ArtistInfo(
                        id=artist.id,
                        name=artist.name,
                        genres=genres,
                        popularity=artist.popularity,
                        followers=artist.followers,
                        bio_summary=artist.bio_summary,
                        top_tracks=[],  # Will be populated if needed
                        albums_count=len(artist.albums) if artist.albums else 0
                    ))

            return result[:limit]
        finally:
            session.close()

    def _get_user_top_tracks(
        self, user_id: int, limit: int = 20, by_score: bool = True
    ) -> List[TrackInfo]:
        """Obtener las mejores canciones del usuario."""
        session = get_session()
        try:
            if by_score:
                tracks = session.exec(
                    select(Track)
                    .where(Track.user_score > 0)
                    .order_by(Track.user_score.desc())
                    .limit(limit)
                ).all()
            else:
                # Get most played
                track_ids = session.exec(
                    select(PlayHistory.track_id)
                    .where(PlayHistory.user_id == user_id)
                    .group_by(PlayHistory.track_id)
                    .order_by(func.count(PlayHistory.id).desc())
                    .limit(limit)
                ).all()
                tracks = session.exec(
                    select(Track).where(Track.id.in_(track_ids))
                ).all()

            return [self._track_to_info(t, session) for t in tracks]
        finally:
            session.close()

    def _get_recent_plays(
        self, user_id: int, limit: int = 20, days: int = 7
    ) -> List[TrackInfo]:
        """Obtener canciones reproducidas recientemente."""
        session = get_session()
        try:
            since = datetime.utcnow() - timedelta(days=days)
            plays = session.exec(
                select(PlayHistory)
                .where(PlayHistory.user_id == user_id)
                .where(PlayHistory.played_at >= since)
                .order_by(PlayHistory.played_at.desc())
                .limit(limit)
            ).all()

            track_ids = [p.track_id for p in plays]
            if not track_ids:
                return []

            tracks = session.exec(
                select(Track).where(Track.id.in_(track_ids))
            ).all()

            track_map = {t.id: t for t in tracks}
            return [self._track_to_info(track_map[p.track_id], session)
                    for p in plays if p.track_id in track_map]
        finally:
            session.close()

    def _get_user_genres(self, user_id: int) -> List[str]:
        """Obtener géneros preferidos del usuario."""
        session = get_session()
        try:
            # Get genres from favorite artists
            favorites = session.exec(
                select(UserFavorite)
                .where(UserFavorite.user_id == user_id)
                .where(UserFavorite.target_type == "artist")
            ).all()

            artist_ids = [f.artist_id for f in favorites if f.artist_id]
            if not artist_ids:
                return []

            artists = session.exec(
                select(Artist).where(Artist.id.in_(artist_ids))
            ).all()

            all_genres = []
            for artist in artists:
                all_genres.extend(self._parse_genres(artist.genres))

            # Return most common genres
            genre_counts = Counter(all_genres)
            return [g for g, _ in genre_counts.most_common(10)]
        finally:
            session.close()

    def _get_artist_by_id(self, artist_id: int) -> Optional[ArtistInfo]:
        """Obtener información de un artista por ID."""
        session = get_session()
        try:
            artist = session.get(Artist, artist_id)
            if not artist:
                return None

            genres = self._parse_genres(artist.genres)

            # Get top tracks
            tracks = session.exec(
                select(Track)
                .where(Track.artist_id == artist_id)
                .order_by(Track.popularity.desc())
                .limit(5)
            ).all()
            top_track_names = [t.name for t in tracks]

            return ArtistInfo(
                id=artist.id,
                name=artist.name,
                genres=genres,
                popularity=artist.popularity,
                followers=artist.followers,
                bio_summary=artist.bio_summary,
                top_tracks=top_track_names,
                albums_count=len(artist.albums) if artist.albums else 0
            )
        finally:
            session.close()

    def _get_album_by_id(self, album_id: int) -> Optional[AlbumInfo]:
        """Obtener información de un álbum por ID."""
        session = get_session()
        try:
            album = session.get(Album, album_id)
            if not album:
                return None

            artist = session.get(Artist, album.artist_id)

            return AlbumInfo(
                id=album.id,
                name=album.name,
                artist=artist.name if artist else "Unknown",
                artist_id=album.artist_id,
                release_date=album.release_date,
                total_tracks=album.total_tracks,
                popularity=album.total_tracks  # Placeholder
            )
        finally:
            session.close()

    def _track_to_info(self, track: Track, session) -> TrackInfo:
        """Convertir Track model a TrackInfo."""
        artist = session.get(Artist, track.artist_id) if track.artist_id else None
        album = session.get(Album, track.album_id) if track.album_id else None

        genres = []
        if artist:
            genres = self._parse_genres(artist.genres)

        return TrackInfo(
            id=track.id,
            name=track.name,
            artist=artist.name if artist else "Unknown",
            artist_id=track.artist_id,
            album=album.name if album else None,
            album_id=track.album_id,
            duration_ms=track.duration_ms,
            popularity=track.popularity,
            user_score=track.user_score if track.user_score > 0 else None,
            is_favorite=track.is_favorite,
            genres=genres
        )

    def _parse_genres(self, genres_str: Optional[str]) -> List[str]:
        """Parsear string de géneros a lista."""
        if not genres_str:
            return []
        try:
            genres = json.loads(genres_str)
            if isinstance(genres, list):
                return [g for g in genres if g]
        except json.JSONDecodeError:
            pass
        return []

    def _search_tracks_by_text(self, query: str, limit: int = 50) -> List[TrackInfo]:
        """Buscar canciones por texto en nombre/artista/álbum."""
        session = get_session()
        try:
            search = f"%{query.lower()}%"
            tracks = session.exec(
                select(Track)
                .where(
                    (Track.name.ilike(search)) |
                    (Track.id.in_(
                        select(Track.id)
                        .join(Artist, Track.artist_id == Artist.id)
                        .where(Artist.name.ilike(search))
                    ))
                )
                .limit(limit)
            ).all()

            return [self._track_to_info(t, session) for t in tracks]
        finally:
            session.close()

    # =========================================================================
    # MAIN METHODS - Generación de contenido
    # =========================================================================

    def generate_playlist(
        self,
        user_id: int,
        mood: str,
        num_tracks: int = 20,
        language: str = "español"
    ) -> Dict[str, Any]:
        """
        Generar una playlist basada en mood/contexto.

        Args:
            user_id: ID del usuario
            mood: Mood o contexto (ej: "fiesta", "trabajar", "triste")
            num_tracks: Número de canciones
            language: Idioma para la respuesta

        Returns:
            Dict con la playlist estructurada
        """
        # Check Ollama availability
        if not self.is_available():
            raise OllamaConnectionError(
                "Ollama no está disponible. "
                "Asegúrate de que el servicio esté corriendo."
            )

        # Extract user data
        fav_artists = self._get_user_favorite_artists(user_id, limit=5)
        fav_genres = self._get_user_genres(user_id)
        top_tracks = self._get_user_top_tracks(user_id, limit=10)
        recent_plays = self._get_recent_plays(user_id, limit=10)

        # Check minimum data
        if not any([fav_artists, top_tracks, fav_genres]):
            raise InsufficientDataError(
                "No hay suficientes datos para generar una playlist. "
                "Añade favoritos, valoraciones o reproduce algunas canciones."
            )

        # Build context strings
        fav_artists_str = format_list([a.name for a in fav_artists])
        fav_genres_str = format_list(fav_genres[:5])
        top_tracks_str = format_list([f"{t.name} - {t.artist}" for t in top_tracks[:5]])
        recent_plays_str = format_list([f"{t.name} - {t.artist}" for t in recent_plays[:5]])

        # Build prompt
        prompt = PLAYLIST_GENERATION_PROMPT.format(
            fav_artists=fav_artists_str,
            fav_genres=fav_genres_str,
            top_tracks=top_tracks_str,
            recent_plays=recent_plays_str,
            mood=mood,
            num_tracks=num_tracks,
            language=language
        )

        # Generate response
        response = self.ollama.generate_structured(
            prompt=prompt,
            system_prompt=AUDIO2_SYSTEM_PROMPT,
            response_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "mood": {"type": "string"},
                    "tracks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer"},
                                "title": {"type": "string"},
                                "artist": {"type": "string"},
                                "reason": {"type": "string"}
                            }
                        }
                    },
                    "notes": {"type": "string"}
                }
            },
            temperature=0.7
        )

        if not response.success:
            raise MusicIntelligenceError(
                f"Error generando playlist: {response.error}"
            )

        # Parse and return
        try:
            result = json.loads(response.text)
            logger.info(f"Generated playlist: {result.get('name', 'Unknown')}")
            return result
        except json.JSONDecodeError:
            logger.error(f"Failed to parse playlist response: {response.text}")
            raise MusicIntelligenceError(
                "Error parseando la respuesta del LLM"
            )

    def generate_artist_bio(
        self,
        artist_id: int,
        language: str = "español"
    ) -> Dict[str, Any]:
        """
        Generar biografía de un artista.

        Args:
            artist_id: ID del artista
            language: Idioma para la respuesta

        Returns:
            Dict con la biografía estructurada
        """
        if not self.is_available():
            raise OllamaConnectionError("Ollama no está disponible")

        # Get artist info
        artist = self._get_artist_by_id(artist_id)
        if not artist:
            raise ValueError(f"Artista con ID {artist_id} no encontrado")

        session = get_session()
        try:
            # Get albums
            albums = session.exec(
                select(Album)
                .where(Album.artist_id == artist_id)
                .order_by(Album.release_date)
            ).all()

            # Get top tracks
            tracks = session.exec(
                select(Track)
                .where(Track.artist_id == artist_id)
                .order_by(Track.popularity.desc())
                .limit(5)
            ).all()
            top_track_names = [t.name for t in tracks]

            albums_str = format_list([a.name for a in albums[:5]])
            top_tracks_str = format_list(top_track_names)

            prompt = ARTIST_BIO_PROMPT.format(
                artist_name=artist.name,
                genres=format_list(artist.genres),
                popularity=artist.popularity,
                followers=artist.followers,
                existing_bio=artist.bio_summary or "Sin información previa",
                albums=albums_str,
                top_tracks=top_tracks_str,
                language=language
            )

            response = self.ollama.generate_structured(
                prompt=prompt,
                system_prompt=AUDIO2_SYSTEM_PROMPT,
                response_schema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "biography": {"type": "string"},
                        "highlights": {"type": "array", "items": {"type": "string"}},
                        "recommended_for_fans_of": {"type": "array", "items": {"type": "string"}},
                        "notable_facts": {"type": "array", "items": {"type": "string"}}
                    }
                },
                temperature=0.5
            )

            if not response.success:
                raise MusicIntelligenceError(
                    f"Error generando biografía: {response.error}"
                )

            result = json.loads(response.text)
            logger.info(f"Generated bio for artist: {artist.name}")
            return result

        finally:
            session.close()

    def generate_album_summary(
        self,
        album_id: int,
        language: str = "español"
    ) -> Dict[str, Any]:
        """
        Generar resumen de un álbum.

        Args:
            album_id: ID del álbum
            language: Idioma para la respuesta

        Returns:
            Dict con el resumen estructurado
        """
        if not self.is_available():
            raise OllamaConnectionError("Ollama no está disponible")

        album = self._get_album_by_id(album_id)
        if not album:
            raise ValueError(f"Álbum con ID {album_id} no encontrado")

        session = get_session()
        try:
            # Get tracks
            tracks = session.exec(
                select(Track)
                .where(Track.album_id == album_id)
                .order_by(Track.popularity.desc())
            ).all()

            highlight_names = [t.name for t in tracks[:3]]

            prompt = ALBUM_SUMMARY_PROMPT.format(
                album_name=album.name,
                artist_name=album.artist,
                release_date=album.release_date,
                total_tracks=album.total_tracks,
                genres="N/A",  # Could add genre lookup
                highlight_tracks=format_list(highlight_names),
                popularity=album.popularity,
                language=language
            )

            response = self.ollama.generate_structured(
                prompt=prompt,
                system_prompt=AUDIO2_SYSTEM_PROMPT,
                response_schema={
                    "type": "object",
                    "properties": {
                        "album": {"type": "string"},
                        "artist": {"type": "string"},
                        "summary": {"type": "string"},
                        "key_tracks": {"type": "array", "items": {"type": "string"}},
                        "mood": {"type": "string"},
                        "verdict": {"type": "string"}
                    }
                },
                temperature=0.5
            )

            if not response.success:
                raise MusicIntelligenceError(
                    f"Error generando resumen: {response.error}"
                )

            result = json.loads(response.text)
            logger.info(f"Generated summary for album: {album.name}")
            return result

        finally:
            session.close()

    def semantic_search(
        self,
        user_id: int,
        query: str,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Búsqueda semántica de canciones basada en descripción natural.

        Args:
            user_id: ID del usuario
            query: Descripción natural (ej: "música para un día triste")
            limit: Número máximo de resultados

        Returns:
            Dict con canciones coincidentes
        """
        if not self.is_available():
            raise OllamaConnectionError("Ollama no está disponible")

        # Get all user tracks for context
        session = get_session()
        try:
            # Get all user tracks (could be optimized with pagination)
            all_tracks = session.exec(
                select(Track)
                .limit(200)  # Limit for performance
            ).all()

            # Get user context
            fav_artists = self._get_user_favorite_artists(user_id, limit=3)
            fav_genres = self._get_user_genres(user_id)[:3]

            # Build library summary
            library_summary = f"""
Biblioteca del usuario:
- Total de canciones: {len(all_tracks)}
- Artistas favoritos: {format_list([a.name for a in fav_artists])}
- Géneros principales: {format_list(fav_genres)}
"""

            # Create tracks info for context
            tracks_info = [self._track_to_info(t, session) for t in all_tracks]
            tracks_json = json.dumps(
                [{"id": t.id, "name": t.name, "artist": t.artist, "genres": t.genres}
                 for t in tracks_info],
                ensure_ascii=False
            )

            full_prompt = f"""{SEMANTIC_SEARCH_PROMPT.format(
                library_summary=library_summary,
                query=query
            )}

Canciones disponibles en JSON:
{tracks_json}

Debes seleccionar las mejores coincidencias de entre las canciones disponibles.
"""

            response = self.ollama.generate_structured(
                prompt=full_prompt,
                system_prompt=AUDIO2_SYSTEM_PROMPT,
                response_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "interpretation": {"type": "string"},
                        "matches": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "integer"},
                                    "title": {"type": "string"},
                                    "artist": {"type": "string"},
                                    "match_score": {"type": "number"},
                                    "match_reason": {"type": "string"}
                                }
                            }
                        },
                        "suggested_mood_tags": {"type": "array", "items": {"type": "string"}}
                    }
                },
                temperature=0.3
            )

            if not response.success:
                raise MusicIntelligenceError(
                    f"Error en búsqueda semántica: {response.error}"
                )

            result = json.loads(response.text)
            logger.info(f"Semantic search for '{query}': {len(result.get('matches', []))} matches")
            return result

        finally:
            session.close()

    def get_recommendations(
        self,
        user_id: int,
        num_recommendations: int = 10
    ) -> Dict[str, Any]:
        """
        Obtener recomendaciones personalizadas.

        Args:
            user_id: ID del usuario
            num_recommendations: Número de recomendaciones

        Returns:
            Dict con recomendaciones estructuradas
        """
        if not self.is_available():
            raise OllamaConnectionError("Ollama no está disponible")

        # Extract user data
        top_artists = self._get_user_favorite_artists(user_id, limit=10)
        top_genres = self._get_user_genres(user_id)[:5]
        top_tracks = self._get_user_top_tracks(user_id, limit=15)

        # Get play history summary
        session = get_session()
        try:
            recent_history = session.exec(
                select(PlayHistory)
                .where(PlayHistory.user_id == user_id)
                .order_by(PlayHistory.played_at.desc())
                .limit(50)
            ).all()

            # Analyze time patterns
            hour_distribution = Counter([h.played_at.hour for h in recent_history])
            day_distribution = Counter([h.played_at.strftime("%A") for h in recent_history])

            play_history_summary = f"""
Período reciente (últimas 50 reproducciones):
- Total: {len(recent_history)} reproducciones
- Por hora del día: {dict(hour_distribution)}
- Por día: {dict(day_distribution)}
"""

            prompt = PERSONAL_RECOMMENDATIONS_PROMPT.format(
                top_artists=format_list([a.name for a in top_artists]),
                top_genres=format_list(top_genres),
                rated_tracks=format_list([f"{t.name} - {t.artist}" for t in top_tracks[:5]]),
                skipped_tracks="Ninguno",  # Could implement skip tracking
                hidden_artists="Ninguno",  # Could add hidden artist check
                play_history_summary=play_history_summary,
                num_recommendations=num_recommendations
            )

            response = self.ollama.generate_structured(
                prompt=prompt,
                system_prompt=AUDIO2_SYSTEM_PROMPT,
                response_schema={
                    "type": "object",
                    "properties": {
                        "recommendations": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "type": {"type": "string"},
                                    "id": {"type": "integer"},
                                    "name": {"type": "string"},
                                    "artist": {"type": "string"},
                                    "reason": {"type": "string"},
                                    "confidence": {"type": "number"},
                                    "based_on": {"type": "string"}
                                }
                            }
                        },
                        "insights": {"type": "array", "items": {"type": "string"}}
                    }
                },
                temperature=0.7
            )

            if not response.success:
                raise MusicIntelligenceError(
                    f"Error generando recomendaciones: {response.error}"
                )

            result = json.loads(response.text)
            logger.info(f"Generated {len(result.get('recommendations', []))} recommendations")
            return result

        finally:
            session.close()

    def get_user_insights(
        self,
        user_id: int,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Analizar patrones de escucha del usuario.

        Args:
            user_id: ID del usuario
            days: Período de análisis en días

        Returns:
            Dict con insights estructurados
        """
        if not self.is_available():
            raise OllamaConnectionError("Ollama no está disponible")

        session = get_session()
        try:
            since = datetime.utcnow() - timedelta(days=days)

            # Get all data for analysis
            plays = session.exec(
                select(PlayHistory)
                .where(PlayHistory.user_id == user_id)
                .where(PlayHistory.played_at >= since)
            ).all()

            if not plays:
                raise InsufficientDataError(
                    f"No hay suficientes datos para analizar (solo {len(plays)} reproducciones)"
                )

            # Calculate statistics
            total_plays = len(plays)

            # Get unique tracks
            track_ids = list(set([p.track_id for p in plays]))

            # Time analysis
            hours = [p.played_at.hour for p in plays]
            days_of_week = [p.played_at.strftime("%A") for p in plays]
            hour_dist = Counter(hours)
            day_dist = Counter(days_of_week)

            # Peak hours
            peak_hours = sorted(hour_dist.items(), key=lambda x: x[1], reverse=True)[:3]
            peak_hours_str = ", ".join([f"{h}:00" for h, _ in peak_hours])

            # Most played days
            peak_days = sorted(day_dist.items(), key=lambda x: x[1], reverse=True)[:3]
            peak_days_str = ", ".join([d for d, _ in peak_days])

            # Top tracks
            track_plays = Counter([p.track_id for p in plays])
            top_track_ids = [t for t, _ in track_plays.most_common(5)]
            top_tracks_data = session.exec(
                select(Track).where(Track.id.in_(top_track_ids))
            ).all()
            top_tracks_map = {t.id: t for t in top_tracks_data}
            top_tracks_str = ", ".join([
                f"{top_tracks_map[tid].name}" for tid in top_track_ids if tid in top_tracks_map
            ])

            # Genre distribution from artists
            artists_in_plays = session.exec(
                select(Track.artist_id).where(Track.id.in_(track_ids))
            ).all()
            artist_ids = list(set(artists_in_plays))
            artists = session.exec(
                select(Artist).where(Artist.id.in_(artist_ids))
            ).all()

            all_genres = []
            for artist in artists:
                all_genres.extend(self._parse_genres(artist.genres))

            genre_dist = Counter(all_genres)
            genre_dist_str = dict(genre_dist.most_common(10))

            # Calculate total listening time (estimated)
            avg_track_length = 240000  # 4 minutes default
            total_minutes = (total_plays * avg_track_length) / 60000

            prompt = USER_INSIGHTS_PROMPT.format(
                period=f"últimos {days} días",
                total_plays=total_plays,
                genre_distribution=json.dumps(genre_dist_str),
                top_artists=format_list([a.name for a in artists[:5]]),
                top_tracks=top_tracks_str,
                time_distribution=peak_hours_str,
                day_distribution=peak_days_str,
                mood_tags="No disponible"  # Could add mood tag analysis
            )

            response = self.ollama.generate_structured(
                prompt=prompt,
                system_prompt=AUDIO2_SYSTEM_PROMPT,
                response_schema={
                    "type": "object",
                    "properties": {
                        "period": {"type": "string"},
                        "summary": {"type": "string"},
                        "statistics": {
                            "type": "object",
                            "properties": {
                                "total_listening_time_hours": {"type": "number"},
                                "average_session_length": {"type": "string"},
                                "genres_explored": {"type": "integer"},
                                "new_artists_discovered": {"type": "integer"}
                            }
                        },
                        "patterns": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "pattern": {"type": "string"},
                                    "evidence": {"type": "string"},
                                    "suggestion": {"type": "string"}
                                }
                            }
                        },
                        "trends": {
                            "type": "object",
                            "properties": {
                                "rising_genres": {"type": "array", "items": {"type": "string"}},
                                "declining_genres": {"type": "array", "items": {"type": "string"}},
                                "new_interests": {"type": "array", "items": {"type": "string"}}
                            }
                        },
                        "achievements": {"type": "array", "items": {"type": "string"}},
                        "recommendations_for_improvement": {"type": "array", "items": {"type": "string"}}
                    }
                },
                temperature=0.5
            )

            if not response.success:
                raise MusicIntelligenceError(
                    f"Error generando insights: {response.error}"
                )

            result = json.loads(response.text)
            result["statistics"]["total_listening_time_hours"] = round(total_minutes / 60, 1)

            logger.info(f"Generated insights for user {user_id}, period: {days} days")
            return result

        finally:
            session.close()


# Instance global del servicio
music_intelligence = MusicIntelligenceService()


def get_service_status() -> Dict[str, Any]:
    """
    Obtener estado del servicio de inteligencia musical.

    Returns:
        Dict con estado de salud
    """
    ollama_status = check_ollama_health()

    return {
        "available": ollama_status["available"],
        "ollama": ollama_status,
        "service": "music_intelligence"
    }
