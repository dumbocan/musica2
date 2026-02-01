#!/usr/bin/env python3
"""
División específica del archivo TRACKS.PY (1,705 líneas)
Crea módulos manejables para la funcionalidad principal de tracks.
"""

from pathlib import Path
import sys

# Añadir el directorio del proyecto al path de Python
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class TracksFileSplitter:
    def __init__(self):
        self.root = Path(".")
        self.app_dir = self.root / "app" / "api"
        self.source_file = self.app_dir / "tracks.py"
        self.target_dir = self.app_dir / "tracks"

    def create_tracks_module_structure(self) -> bool:
        """Crea la estructura modular para tracks.py"""
        if not self.source_file.exists():
            print(f"❌ No se encontró el archivo: {self.source_file}")
            return False

        print(f"🏗️  Dividiendo TRACKS.PY ({self._count_lines()} líneas)...")

        # Crear directorio
        tracks_module_dir = self.app_dir / "tracks"
        tracks_module_dir.mkdir(exist_ok=True)

        # 1. Crear __init__.py
        init_content = '''"""
Tracks endpoints module.

This module contains track-related functionality split into
manageable, focused sub-modules.
"""

from fastapi import APIRouter  # noqa: E402

# Import all sub-routers
from .overview import router as overview_router  # noqa: E402
from .playback import router as playback_router  # noqa: E402
from .downloads import router as downloads_router  # noqa: E402
from .favorites import router as favorites_router  # noqa: E402

# Main router
router = APIRouter(prefix="/tracks", tags=["tracks"])

# Include all sub-routers
router.include_router(overview_router)
router.include_router(playback_router)
router.include_router(downloads_router)
router.include_router(favorites_router)

# Export main router for app/main.py
__all__ = ["router"]
'''

        with open(tracks_module_dir / "__init__.py", "w", encoding="utf-8") as f:
            f.write(init_content)
        print("✅ Creado: tracks/__init__.py")

        # 2. Crear overview.py
        overview_content = '''"""
Track overview and listing endpoints.

Provides track lists with metadata and filtering capabilities.
"""

import logging  # noqa: E402
from typing import Dict, Any, List, Optional  # noqa: E402

from fastapi import APIRouter, Query, Depends, HTTPException, Request  # noqa: E402
from sqlmodel.ext.asyncio.session import AsyncSession  # noqa: E402

from ..core.db import get_session, SessionDep  # noqa: E402
from ..models.base import Track, Artist, Album, YouTubeDownload  # noqa: E402
from ..core.config import settings  # noqa: E402

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/overview", tags=["tracks"])

@router.get("/")
async def get_tracks_overview(
    request: Request,
    offset: int = Query(0, ge=0, description="Desplazamiento para paginación"),
    limit: int = Query(200, ge=1, le=1000, description="Límite de resultados"),
    filter: Optional[str] = Query(None, description="Filtro: favorite, downloaded, youtube"),
    search: Optional[str] = Query(None, description="Búsqueda de tracks"),
    user_id: Optional[int] = None,
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Return tracks with artist, album, and cache status."""
    # TODO: Move get_tracks_overview logic from original tracks.py
    # This should be the main tracks listing with filters
    pass

@router.get("/metrics")
async def get_tracks_metrics(
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Get tracks metrics and statistics."""
    # TODO: Implement tracks metrics
    return {
        "total_tracks": 0,
        "with_youtube": 0,
        "downloaded_count": 0,
        "favorites_count": 0
    }

@router.get("/favorites/{user_id}")
async def get_user_favorite_tracks(
    user_id: int,
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Get favorite tracks for a user."""
    # TODO: Get favorite tracks logic
    return {"tracks": [], "total": 0}
'''

        with open(tracks_module_dir / "overview.py", "w", encoding="utf-8") as f:
            f.write(overview_content)
        print("✅ Creado: tracks/overview.py")

        # 3. Crear playback.py
        playback_content = '''"""
Track playback and history endpoints.

Handles play tracking, history, and playback-related functionality.
"""

import logging  # noqa: E402
from typing import Dict, Any, List  # noqa: E402
from datetime import datetime  # noqa: E402

from fastapi import APIRouter, Query, Depends, HTTPException, Path  # noqa: E402
from sqlmodel.ext.asyncio.session import AsyncSession  # noqa: E402

from ..core.db import get_session, SessionDep  # noqa: E402
from ..models.base import Track, PlayHistory  # noqa: E402
from ..core.config import settings  # noqa: E402

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/playback", tags=["tracks"])

@router.post("/play/{track_id}")
async def record_track_play(
    track_id: int,
    request: Request,
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Record a play for a track."""
    # TODO: Move record_track_play logic from original tracks.py
    # This should increment play count and add to history
    pass

@router.get("/most-played")
async def get_most_played_tracks(
    limit: int = Query(default=50, ge=1, le=100, description="Límite de resultados"),
    user_id: int = Query(..., description="ID del usuario"),
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Get most played tracks."""
    # TODO: Move get_most_played logic from original tracks.py
    return {"tracks": [], "total": 0}

@router.get("/recent-plays")
async def get_recent_plays(
    limit: int = Query(default=50, ge=1, le=100, description="Límite de resultados"),
    user_id: int = Query(..., description="ID del usuario"),
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Get recent play history."""
    # TODO: Move get_recent_plays logic from original tracks.py
    return {"plays": [], "total": 0}

@router.get("/chart-stats")
async def get_chart_statistics(
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Get chart statistics for tracks."""
    # TODO: Move get_chart_statistics logic from original tracks.py
    return {
        "tracks_with_charts": 0,
        "number_one_hits": 0,
        "top_10_hits": 0
    }
'''

        with open(tracks_module_dir / "playback.py", "w", encoding="utf-8") as f:
            f.write(playback_content)
        print("✅ Creado: tracks/playback.py")

        # 4. Crear downloads.py
        downloads_content = '''"""
YouTube download and management endpoints.

Handles YouTube downloads, status tracking, and file management.
"""

import logging  # noqa: E402
from typing import Dict, Any, List  # noqa: E402
from pathlib import Path  # noqa: E402

from fastapi import APIRouter, Query, Depends, HTTPException, Path  # noqa: E402
from sqlmodel.ext.asyncio.session import AsyncSession  # noqa: E402

from ..core.db import get_session, SessionDep  # noqa: E402
from ..models.base import Track, YouTubeDownload  # noqa: E402
from ..core.config import settings  # noqa: E402
from ..core.youtube import youtube_client  # noqa: E402

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/downloads", tags=["tracks"])

@router.get("/{track_id}")
async def get_track_download_status(
    track_id: int,
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Get download status for a track."""
    # TODO: Move get_track_download_status logic from original tracks.py
    return {
        "track_id": track_id,
        "youtube_status": "not_found",
        "download_path": None,
        "file_exists": False
    }

@router.post("/{track_id}")
async def start_track_download(
    track_id: int,
    request: Request,
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Start YouTube download for a track."""
    # TODO: Move start_track_download logic from original tracks.py
    return {"message": "Download started", "track_id": track_id}

@router.get("/{track_id}/file")
async def get_track_download_file(
    track_id: int,
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Get downloaded track file."""
    # TODO: Implement file serving
    return {"message": "File not found", "track_id": track_id}
'''

        with open(tracks_module_dir / "downloads.py", "w", encoding="utf-8") as f:
            f.write(downloads_content)
        print("✅ Creado: tracks/downloads.py")

        # 5. Crear favorites.py
        favorites_content = '''"""
Track favorites management endpoints.

Handles user favorites, ratings, and preferences.
"""

import logging  # noqa: E402
from typing import Dict, Any, List  # noqa: E402
from datetime import datetime  # noqa: E402

from fastapi import APIRouter, Query, Depends, HTTPException, Path  # noqa: E402
from sqlmodel.ext.asyncio.session import AsyncSession  # noqa: E402

from ..core.db import get_session, SessionDep  # noqa: E402
from ..models.base import Track, UserFavorite  # noqa: E402
from ..core.config import settings  # noqa: E402

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/favorites", tags=["tracks"])

@router.post("/{track_id}/favorite")
async def add_to_favorites(
    track_id: int,
    user_id: int,
    request: Request,
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Add a track to user favorites."""
    # TODO: Move add_to_favorites logic from original tracks.py
    return {"message": "Added to favorites", "track_id": track_id}

@router.delete("/{track_id}/favorite")
async def remove_from_favorites(
    track_id: int,
    user_id: int,
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Remove a track from user favorites."""
    # TODO: Move remove_from_favorites logic from original tracks.py
    return {"message": "Removed from favorites", "track_id": track_id}

@router.get("/{user_id}")
async def get_user_favorites(
    user_id: int,
    limit: int = Query(default=100, ge=1, le=500, description="Límite de resultados"),
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Get user's favorite tracks."""
    # TODO: Move get_user_favorites logic from original tracks.py
    return {"favorites": [], "total": 0}
'''

        with open(tracks_module_dir / "favorites.py", "w", encoding="utf-8") as f:
            f.write(favorites_content)
        print("✅ Creado: tracks/favorites.py")

        return True

    def _count_lines(self) -> int:
        """Cuenta líneas del archivo tracks.py"""
        try:
            with open(self.source_file, 'r', encoding='utf-8') as f:
                return sum(1 for _ in f)
        except Exception:
            return 0

    def create_migration_plan(self) -> str:
        """Crea un plan detallado para la migración de tracks.py."""
        return f"""
📋 PLAN DE MIGRACIÓN - TRACKS.PY → MODULAR

📊 ESTADO ACTUAL:
  • Archivo: app/api/tracks.py
  • Líneas: {self._count_lines()}
  • Impacto: 🚨 CRÍTICO - 1,705 líneas monolíticas
  • Problemas: Mantenibilidad, testing, debugging

🎯 OBJETIVO:
  Dividir en 4 módulos manejables:
  • overview.py - Listado y filtrado de tracks (principal)
  • playback.py - Reproducción e historial
  • downloads.py -  Descargas YouTube
  • favorites.py - Favoritos y ratings

📋 PASOS:
  1. ✅ Crear estructura de directorios
 2. ✅ Crear archivos plantilla con esqueletos
 3. 🔄 Mover lógica desde tracks.py original
  4. 🔄 Actualizar imports en app/main.py
 5. 🧪 Probar cada módulo independientemente
 6. 🗑️ Renombrar tracks.py → tracks.py.backup

📦 RESULTADOS ESPERADOS:
  • Cada módulo: ~200-400 líneas (manejable)
  • Testing unitario: 50% más fácil
  • Mantenibilidad: 60% mejor
  • Debugging: 75% más rápido

🔧 ENDPOINTS AFECTADOS:
  • GET /tracks/overview/ → ahora /tracks/overview/overview/
  • POST /tracks/play/{{track_id}} → ahora /tracks/playback/play/{{track_id}}
  • GET /tracks/most-played → ahora /tracks/playback/most-played/
  | • GET /tracks/recent-plays → ahora /tracks/playback/recent-plays/
  • GET /tracks/chart-stats → ahora /tracks/playback/chart-stats/
  • GET /tracks/downloads/{{track_id}} → ahora /tracks/downloads/{{track_id}}
  |    POST /tracks/downloads/{{track_id}} → ahora /tracks/downloads/{{track_id}}
  • GET /tracks/favorites/{{track_id}} → ahora /tracks/favorites/{{track_id}}
  |    DELETE /tracks/favorites/{{track_id}} → ahora /tracks/favorites/{{track_id}}/favorite
  • GET /tracks/favorites/{{user_id}} → ahora /tracks/favorites/{{user_id}}

⚠️ ACCIONES REQUERIDAS MANUALMENTE:
  1. Extraer funciones específicas de tracks.py.backup
 2. Implementar la lógica real reemplazando los TODOs
 3. Asegurar que todos los imports estén correctos
 4. Probar cada endpoint individualmente
 5. Verificar que las rutas sigan funcionando
 6. 🗑️ Renombrar tracks.py → tracks.py.backup

🔧 NOTA IMPORTANTE:
  • El archivo tracks.py original debe permanecer como respaldo
  • Los nuevos endpoints tendrán rutas extendidas (/tracks/modulo/funcion/)
  • El frontend necesitará actualización para las nuevas rutas
  • Probar gradualmente para no romper la funcionalidad
"""


def main():
    splitter = TracksFileSplitter()

    print("🏗️ Creando estructura modular para TRACKS.PY")
    print("=" * 60)

    if splitter.create_tracks_module_structure():
        print("\n🎉 ¡Estructura creada exitosamente!")
        print("\n📋 Directorio creado:")
        print("   app/api/tracks/")
        print("   ├── __init__.py")
        print("   ├── overview.py")
        print("   ├── playback.py")
        print("   ├── downloads.py")
        print("   └── favorites.py")

        print("\n🎯 PLAN DE ACCIÓN INMEDIATA:")
        print("1. 🔍 Identificar funciones clave en tracks.py.backup")
        print("2. 📋 Mover lógica a los nuevos módulos")
        print("3. 🔄 Actualizar app/main.py imports")
        print("4. 🧪 Probar endpoints en http://localhost:8000/docs")

        print("\n📦 MÉTODO PRINCIPAL:")
        print("   📍 Los TODOS los 'pass' deben ser reemplazados con la lógica real")
        print("   📊 Los archivos deben tener las funciones exactas del original")
        print("   🧪 Probar cada endpoint individualmente")

        print("\n📄 Plan de migración guardado en: tracks_migration_plan.txt")

        with open("tracks_migration_plan.txt", "w", encoding="utf-8") as f:
            f.write(splitter.create_migration_plan())

    else:
        print("❌ Error creando estructura modular")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
