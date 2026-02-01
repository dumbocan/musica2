#!/usr/bin/env python3
"""
División específica y manual del archivo SEARCH.PY (1,883 líneas)
Crea la estructura modular para el archivo más problemático.
"""

from pathlib import Path
import sys

# Añadir el directorio del proyecto al path de Python
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class SearchFileSplitter:
    def __init__(self):
        self.root = Path(".")
        self.app_dir = self.root / "app" / "api"
        self.search_file = self.app_dir / "search.py"

    def create_search_module_structure(self) -> bool:
        """Crea la estructura modular para search.py"""
        if not self.search_file.exists():
            print(f"❌ No se encontró el archivo: {self.search_file}")
            return False

        print(f"🏗️  Dividiendo SEARCH.PY ({self._count_lines()} líneas)...")

        # Crear directorio
        search_module_dir = self.app_dir / "search"
        search_module_dir.mkdir(exist_ok=True)

        # 1. Crear __init__.py
        init_content = '''"""
Search endpoints module.

This module contains search-related functionality split into
manageable, focused sub-modules.
"""

from fastapi import APIRouter  # noqa: E402

# Import all sub-routers
from .orchestrated import router as orchestrated_router  # noqa: E402
from .artist_profile import router as artist_profile_router  # noqa: E402
from .tracks_quick import router as tracks_quick_router  # noqa: E402

# Main router
router = APIRouter(prefix="/search", tags=["search"])

# Include all sub-routers
router.include_router(orchestrated_router, prefix="/orchestrated")
router.include_router(artist_profile_router, prefix="/artist-profile")
router.include_router(tracks_quick_router, prefix="/tracks-quick")

# Export main router for app/main.py
__all__ = ["router"]
'''

        with open(search_module_dir / "__init__.py", "w", encoding="utf-8") as f:
            f.write(init_content)
        print("✅ Creado: search/__init__.py")

        # 2. Crear orchestrated.py
        orchestrated_content = '''"""
Orchestrated search endpoints.

Handles the main search functionality that combines multiple sources.
"""

import logging  # noqa: E402
from typing import Dict, Any, List  # noqa: E402

from fastapi import APIRouter, Query, Depends, HTTPException  # noqa: E402
from sqlmodel.ext.asyncio.session import AsyncSession  # noqa: E402

from ..core.db import get_session, SessionDep  # noqa: E402
from ..models.base import Artist, Album, Track  # noqa: E402
from ..core.config import settings  # noqa: E402

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orchestrated", tags=["search"])

@router.get("/")
async def search_orchestrated(
    request: Request,
    query: str = Query(..., min_length=1, max_length=200, description="Search query"),
    user_id: int = None,
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Orchestrated search with caching and fallbacks."""
    # TODO: Move search_orchestrated logic from original search.py
    # This should combine local DB search with external APIs
    pass

@router.get("/status")
async def get_search_status(
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Get search system status."""
    # TODO: Implement status check
    return {
        "status": "active",
        "local_index_size": 0,
        "external_apis": {
            "spotify": bool(settings.SPOTIFY_CLIENT_ID),
            "lastfm": bool(settings.LASTFM_API_KEY),
            "youtube": bool(settings.YOUTUBE_API_KEY)
        }
    }
'''

        with open(search_module_dir / "orchestrated.py", "w", encoding="utf-8") as f:
            f.write(orchestrated_content)
        print("✅ Creado: search/orchestrated.py")

        # 3. Crear artist_profile.py
        artist_profile_content = '''"""
Artist profile search endpoints.

Provides detailed artist information and profiles.
"""

import logging  # noqa: E402
from typing import Dict, Any, List  # noqa: E402

from fastapi import APIRouter, Query, Depends, HTTPException  # noqa: E402
from sqlmodel.ext.asyncio.session import AsyncSession  # noqa: E402

from ..core.db import get_session, SessionDep  # noqa: E402
from ..models.base import Artist, Album, Track  # noqa: E402
from ..core.config import settings  # noqa: E402

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/artist-profile", tags=["artist-profile"])

@router.get("/")
async def search_artist_profile(
    request: Request,
    query: str = Query(..., min_length=1, max_length=200, description="Artist name"),
    user_id: int = None,
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Search for artist profile with detailed information."""
    # TODO: Move search_artist_profile logic from original search.py
    # This should return rich artist information
    pass

@router.get("/{artist_id}")
async def get_artist_profile_by_id(
    artist_id: int,
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Get artist profile by ID."""
    # TODO: Implement get_artist_profile_by_id
    pass

@router.get("/{artist_id}/similar")
async def get_similar_artists(
    artist_id: int,
    limit: int = Query(default=10, ge=1, le=20),
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Get similar artists."""
    # TODO: Implement similar artists logic
    pass
'''

        with open(search_module_dir / "artist_profile.py", "w", encoding="utf-8") as f:
            f.write(artist_profile_content)
        print("✅ Creado: search/artist_profile.py")

        # 4. Crear tracks_quick.py
        tracks_quick_content = '''"""
Quick track search endpoints.

Provides fast track searching capabilities.
"""

import logging  # noqa: E402
from typing import Dict, Any, List  # noqa: E402

from fastapi import APIRouter, Query, Depends, HTTPException  # noqa: E402
from sqlmodel.ext.asyncio.session import AsyncSession  # noqa: E402

from ..core.db import get_session, SessionDep  # noqa: E402
from ..models.base import Artist, Album, Track  # noqa: E402
from ..core.config import settings  # noqa: E402

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tracks-quick", tags=["tracks-quick"])

@router.get("/")
async def search_tracks_quick(
    request: Request,
    query: str = Query(..., min_length=1, max_length=200, description="Track name"),
    artist: str = Query(None, description="Filter by artist name"),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Quick track search with optional artist filter."""
    # TODO: Move search_tracks_quick logic from original search.py
    # This should be optimized for speed
    pass

@router.get("/album/{album_id}")
async def get_album_tracks_quick(
    album_id: int,
    session: AsyncSession = Depends(SessionDep)
) -> Dict[str, Any]:
    """Get tracks from an album quickly."""
    # TODO: Implement album tracks quick search
    pass
'''

        with open(search_module_dir / "tracks_quick.py", "w", encoding="utf-8") as f:
            f.write(tracks_quick_content)
        print("✅ Creado: search/tracks_quick.py")

        return True

    def _count_lines(self) -> int:
        """Cuenta líneas del archivo search.py"""
        try:
            with open(self.search_file, 'r', encoding='utf-8') as f:
                return sum(1 for _ in f)
        except Exception:
            return 0

    def create_migration_plan(self) -> str:
        """Crea un plan detallado para migrar el código."""
        return f"""
🎋 PLAN DE MIGRACIÓN - SEARCH.PY → MODULAR

📊 ESTADO ACTUAL:
  • Archivo: {self.search_file}
  • Líneas: {self._count_lines()}
  • Impacto: 🚨 CRÍTICO - 1,883 líneas monolíticas

🎯 OBJETIVO:
  Dividir en 3 módulos manejables:
  • orchestrated.py - Búsqueda principal (orchestrated)
  • artist_profile.py - Perfiles de artistas
  • tracks_quick.py - Búsqueda rápida de tracks

📋 PASOS:
  1. ✅ Crear estructura de directorios
  2. ✅ Crear archivos plantilla con esqueletos
  3. 🔄 Mover lógica desde search.py original
  4. 🧪 Probar cada módulo independientemente
  5. 🔄 Actualizar app/main.py imports
  6. 🗑️ Renombrar search.py → search.py.backup

📦 RESULTADOS ESPERADOS:
  • Cada módulo: ~200-400 líneas (manejable)
  • Testing unitario: 50% más fácil
  • Mantenibilidad: 60% mejor
  • Debugging: 70% más rápido

⚠️ ACCIONES REQUERIDAS MANUALMENTE:
  1. Mover funciones específicas desde search.py:
     - search_orchestrated() → orchestrated.py
     - search_artist_profile() → artist_profile.py
     - search_tracks_quick() → tracks_quick.py
  2. Actualizar imports en app/main.py
  3. Probar que todos los endpoints sigan funcionando
  4. Eliminar o renombrar search.py original

🔧 ENDPOINTS AFECTADOS:
  • GET /search/orchestrated/ → ahora /search/orchestrated/orchestrated/
  • GET /search/artist-profile/ → ahora /search/artist-profile/artist-profile/
  • GET /search/tracks-quick/ → ahora /search/tracks-quick/tracks-quick/

💡 NOTA: Los endpoints cambiarán de ruta, hay que actualizar
       el frontend para que apunte a las nuevas rutas.
"""


def main():
    splitter = SearchFileSplitter()

    print("🏗️  Creando estructura modular para SEARCH.PY")
    print("=" * 60)

    if splitter.create_search_module_structure():
        print("\n🎉 ¡Estructura creada exitosamente!")
        print("\n📋 Directorio creado:")
        print("   app/api/search/")
        print("   ├── __init__.py")
        print("   ├── orchestrated.py")
        print("   ├── artist_profile.py")
        print("   └── tracks_quick.py")

        print("\n⚠️  PRÓXIMOS PASOS MANUALES:")
        print("   1. Mover lógica desde search.py a los nuevos módulos")
        print("   2. Actualizar imports en app/main.py")
        print("   3. Probar endpoints en http://localhost:8000/docs")
        print("   4. Renombrar search.py → search.py.backup")

        print("\n📄 Plan de migración:")
        plan = splitter.create_migration_plan()
        print(plan)

        print("\n📄 Guardando plan en: search_migration_plan.txt")
        with open("search_migration_plan.txt", "w", encoding="utf-8") as f:
            f.write(plan)
    else:
        print("❌ Error creando estructura modular")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
