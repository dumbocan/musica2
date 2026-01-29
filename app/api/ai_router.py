"""
AI Router - Endpoints para el sistema de inteligencia musical.

Endpoints disponibles:
- POST /ai/generate-playlist: Generar playlist basada en mood
- POST /ai/artist-bio: Generar biografía de artista
- POST /ai/album-summary: Generar resumen de álbum
- POST /ai/recommendations: Recomendaciones personalizadas
- POST /ai/semantic-search: Búsqueda semántica
- GET /ai/user-insights: Análisis de patrones de escucha
- GET /ai/health: Verificar estado del servicio
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import logging

from ..services.ollama_service import OllamaConnectionError, check_ollama_health
from ..services.music_intelligence import (
    music_intelligence,
    MusicIntelligenceError,
    InsufficientDataError
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["AI"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class PlaylistRequest(BaseModel):
    """Request para generación de playlist."""
    mood: str = Field(..., description="Mood o contexto de la playlist", example="fiesta")
    num_tracks: int = Field(default=20, ge=5, le=100, description="Número de canciones")
    language: str = Field(default="español", description="Idioma de la respuesta")


class PlaylistResponse(BaseModel):
    """Response de playlist generada."""
    success: bool
    playlist: Dict[str, Any]
    error: Optional[str] = None


class ArtistBioRequest(BaseModel):
    """Request para biografía de artista."""
    artist_id: int = Field(..., description="ID del artista")
    language: str = Field(default="español", description="Idioma de la respuesta")


class ArtistBioResponse(BaseModel):
    """Response de biografía de artista."""
    success: bool
    biography: Dict[str, Any]
    error: Optional[str] = None


class AlbumSummaryRequest(BaseModel):
    """Request para resumen de álbum."""
    album_id: int = Field(..., description="ID del álbum")
    language: str = Field(default="español", description="Idioma de la respuesta")


class AlbumSummaryResponse(BaseModel):
    """Response de resumen de álbum."""
    success: bool
    summary: Dict[str, Any]
    error: Optional[str] = None


class RecommendationsRequest(BaseModel):
    """Request para recomendaciones."""
    num_recommendations: int = Field(default=10, ge=1, le=50, description="Número de recomendaciones")


class RecommendationsResponse(BaseModel):
    """Response de recomendaciones."""
    success: bool
    recommendations: Dict[str, Any]
    error: Optional[str] = None


class SemanticSearchRequest(BaseModel):
    """Request para búsqueda semántica."""
    query: str = Field(..., description="Búsqueda en lenguaje natural", example="música para un día triste")
    limit: int = Field(default=10, ge=1, max=50, description="Número máximo de resultados")


class SemanticSearchResponse(BaseModel):
    """Response de búsqueda semántica."""
    success: bool
    results: Dict[str, Any]
    error: Optional[str] = None


class UserInsightsRequest(BaseModel):
    """Request para insights de usuario."""
    days: int = Field(default=30, ge=7, max=365, description="Período de análisis en días")


class UserInsightsResponse(BaseModel):
    """Response de insights de usuario."""
    success: bool
    insights: Dict[str, Any]
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Response de estado de salud."""
    available: bool
    ollama: Dict[str, Any]
    message: str


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/health", response_model=HealthResponse)
async def check_ai_health():
    """
    Verificar estado del servicio de IA.

    Returns:
        Estado de salud del servicio Ollama
    """
    status = check_ollama_health()

    if status["available"]:
        return HealthResponse(
            available=True,
            ollama=status,
            message="El servicio de IA está disponible y listo para usar"
        )
    else:
        return HealthResponse(
            available=False,
            ollama=status,
            message="El servicio de IA no está disponible. Verifica que Ollama esté corriendo."
        )


@router.post("/generate-playlist", response_model=PlaylistResponse)
async def generate_playlist(
    request: PlaylistRequest,
    user_id: int = Query(default=1, description="ID del usuario")
):
    """
    Generar una playlist inteligente basada en mood/contexto.

    El LLM analiza los favoritos, historial y preferencias del usuario
    para crear una playlist personalizada.

    Args:
        request: mood, número de canciones e idioma
        user_id: ID del usuario

    Returns:
        Playlist generada con canciones, razones y notas
    """
    try:
        # Check if AI service is available
        if not music_intelligence.is_available():
            raise HTTPException(
                status_code=503,
                detail="El servicio de IA no está disponible. Asegúrate de que Ollama esté corriendo en localhost:11434"
            )

        # Generate playlist
        playlist = music_intelligence.generate_playlist(
            user_id=user_id,
            mood=request.mood,
            num_tracks=request.num_tracks,
            language=request.language
        )

        return PlaylistResponse(
            success=True,
            playlist=playlist
        )

    except OllamaConnectionError as e:
        logger.error(f"Ollama connection error: {e}")
        raise HTTPException(
            status_code=503,
            detail=str(e)
        )

    except InsufficientDataError as e:
        logger.warning(f"Insufficient data for playlist: {e}")
        return PlaylistResponse(
            success=False,
            playlist={},
            error=str(e)
        )

    except MusicIntelligenceError as e:
        logger.error(f"Music intelligence error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error generando playlist: {str(e)}"
        )

    except Exception as e:
        logger.exception(f"Unexpected error in generate_playlist: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )


@router.post("/artist-bio", response_model=ArtistBioResponse)
async def generate_artist_bio(request: ArtistBioRequest):
    """
    Generar biografía de un artista.

    El LLM crea una biografía atractiva basada en los datos
    disponibles del artista en la biblioteca.

    Args:
        request: ID del artista e idioma

    Returns:
        Biografía estructurada del artista
    """
    try:
        if not music_intelligence.is_available():
            raise HTTPException(
                status_code=503,
                detail="El servicio de IA no está disponible"
            )

        bio = music_intelligence.generate_artist_bio(
            artist_id=request.artist_id,
            language=request.language
        )

        return ArtistBioResponse(
            success=True,
            biography=bio
        )

    except ValueError as e:
        logger.warning(f"Artist not found: {e}")
        return ArtistBioResponse(
            success=False,
            biography={},
            error=str(e)
        )

    except (OllamaConnectionError, MusicIntelligenceError) as e:
        logger.error(f"Error generating artist bio: {e}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    except Exception as e:
        logger.exception(f"Unexpected error in artist_bio: {e}")
        raise HTTPException(status_code=500, detail="Error interno")


@router.post("/album-summary", response_model=AlbumSummaryResponse)
async def generate_album_summary(request: AlbumSummaryRequest):
    """
    Generar resumen de un álbum.

    Args:
        request: ID del álbum e idioma

    Returns:
        Resumen estructurado del álbum
    """
    try:
        if not music_intelligence.is_available():
            raise HTTPException(
                status_code=503,
                detail="El servicio de IA no está disponible"
            )

        summary = music_intelligence.generate_album_summary(
            album_id=request.album_id,
            language=request.language
        )

        return AlbumSummaryResponse(
            success=True,
            summary=summary
        )

    except ValueError as e:
        return AlbumSummaryResponse(
            success=False,
            summary={},
            error=str(e)
        )

    except (OllamaConnectionError, MusicIntelligenceError) as e:
        raise HTTPException(status_code=500, detail=str(e))

    except Exception as e:
        logger.exception(f"Unexpected error in album_summary: {e}")
        raise HTTPException(status_code=500, detail="Error interno")


@router.post("/recommendations", response_model=RecommendationsResponse)
async def get_recommendations(
    request: RecommendationsRequest,
    user_id: int = Query(default=1, description="ID del usuario")
):
    """
    Obtener recomendaciones personalizadas.

    El LLM analiza el historial y preferencias del usuario
    para sugerir canciones, artistas o álbumes relevantes.

    Args:
        request: Número de recomendaciones deseadas
        user_id: ID del usuario

    Returns:
        Recomendaciones personalizadas con justificaciones
    """
    try:
        if not music_intelligence.is_available():
            raise HTTPException(
                status_code=503,
                detail="El servicio de IA no está disponible"
            )

        recommendations = music_intelligence.get_recommendations(
            user_id=user_id,
            num_recommendations=request.num_recommendations
        )

        return RecommendationsResponse(
            success=True,
            recommendations=recommendations
        )

    except InsufficientDataError as e:
        return RecommendationsResponse(
            success=False,
            recommendations={},
            error=str(e)
        )

    except (OllamaConnectionError, MusicIntelligenceError) as e:
        raise HTTPException(status_code=500, detail=str(e))

    except Exception as e:
        logger.exception(f"Unexpected error in recommendations: {e}")
        raise HTTPException(status_code=500, detail="Error interno")


@router.post("/semantic-search", response_model=SemanticSearchResponse)
async def semantic_search(
    request: SemanticSearchRequest,
    user_id: int = Query(default=1, description="ID del usuario")
):
    """
    Búsqueda semántica de canciones.

    Permite buscar canciones usando lenguaje natural.
    El LLM interpreta la búsqueda y encuentra coincidencias relevantes.

    Examples:
    - "música para un día triste"
    - "canciones para entrenar"
    - "música relajante para dormir"
    - "rock clásico de los 80s"

    Args:
        request: Query en lenguaje natural
        user_id: ID del usuario

    Returns:
        Canciones coincidentes con puntuaciones de relevancia
    """
    try:
        if not music_intelligence.is_available():
            raise HTTPException(
                status_code=503,
                detail="El servicio de IA no está disponible"
            )

        results = music_intelligence.semantic_search(
            user_id=user_id,
            query=request.query,
            limit=request.limit
        )

        return SemanticSearchResponse(
            success=True,
            results=results
        )

    except (OllamaConnectionError, MusicIntelligenceError) as e:
        raise HTTPException(status_code=500, detail=str(e))

    except Exception as e:
        logger.exception(f"Unexpected error in semantic_search: {e}")
        raise HTTPException(status_code=500, detail="Error interno")


@router.get("/user-insights", response_model=UserInsightsResponse)
async def get_user_insights(
    days: int = Query(default=30, ge=7, max=365, description="Período de análisis"),
    user_id: int = Query(default=1, description="ID del usuario")
):
    """
    Obtener análisis de patrones de escucha.

    El LLM analiza el historial de reproducción del usuario
    y genera insights sobre sus hábitos musicales.

    Returns:
        Análisis con estadísticas, patrones, tendencias y logros
    """
    try:
        if not music_intelligence.is_available():
            raise HTTPException(
                status_code=503,
                detail="El servicio de IA no está disponible"
            )

        insights = music_intelligence.get_user_insights(
            user_id=user_id,
            days=days
        )

        return UserInsightsResponse(
            success=True,
            insights=insights
        )

    except InsufficientDataError as e:
        return UserInsightsResponse(
            success=False,
            insights={},
            error=str(e)
        )

    except (OllamaConnectionError, MusicIntelligenceError) as e:
        raise HTTPException(status_code=500, detail=str(e))

    except Exception as e:
        logger.exception(f"Unexpected error in user_insights: {e}")
        raise HTTPException(status_code=500, detail="Error interno")


# ============================================================================
# ENDPOINTS ADICIONALES
# ============================================================================

@router.get("/models")
async def list_available_models():
    """
    Listar modelos disponibles en Ollama.

    Returns:
        Lista de modelos descargados
    """
    try:
        from .ollama_service import ollama_client
        if not ollama_client.is_available():
            raise HTTPException(
                status_code=503,
                detail="Ollama no está disponible"
            )

        models = ollama_client.get_model_info()
        return {
            "available": True,
            "current_model": ollama_client.config.model,
            "model_info": models,
            "version": ollama_client.get_version()
        }

    except Exception as e:
        logger.error(f"Error listing models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create-playlist-from-ai")
async def create_playlist_from_ai(
    playlist_data: Dict[str, Any],
    user_id: int = Query(default=1, description="ID del usuario"),
    playlist_name: str = Query(default="AI Generated Playlist", description="Nombre de la playlist"),
    playlist_description: str = Query(default="", description="Descripción")
):
    """
    Crear una playlist real en la base de datos desde respuesta de AI.

    Este endpoint toma los IDs de canción de una respuesta de AI
    y los guarda como una playlist real en PostgreSQL.

    Args:
        playlist_data: Datos de playlist del AI (contiene 'tracks' con 'id')
        user_id: ID del usuario
        playlist_name: Nombre de la playlist
        playlist_description: Descripción

    Returns:
        Playlist creada con sus canciones
    """
    try:
        from ..crud import create_playlist, add_track_to_playlist

        # Extract track IDs from AI response
        tracks = playlist_data.get("tracks", [])
        if not tracks:
            raise HTTPException(
                status_code=400,
                detail="No se encontraron tracks en los datos proporcionados"
            )

        track_ids = []
        for track in tracks:
            if isinstance(track, dict) and "id" in track:
                track_ids.append(track["id"])
            elif isinstance(track, int):
                track_ids.append(track)

        if not track_ids:
            raise HTTPException(
                status_code=400,
                detail="No se pudieron extraer IDs de canciones"
            )

        # Create playlist
        playlist = create_playlist(
            name=playlist_name,
            description=playlist_description or f"Playlist generada por AI - {len(track_ids)} canciones",
            user_id=user_id
        )

        # Add tracks
        added_count = 0
        for track_id in track_ids:
            result = add_track_to_playlist(playlist.id, track_id)
            if result:
                added_count += 1

        return {
            "success": True,
            "playlist": {
                "id": playlist.id,
                "name": playlist.name,
                "description": playlist.description,
                "tracks_added": added_count,
                "total_tracks": len(track_ids)
            }
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.exception(f"Error creating playlist from AI: {e}")
        raise HTTPException(status_code=500, detail=str(e))
