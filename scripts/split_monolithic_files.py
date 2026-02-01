#!/usr/bin/env python3
"""
Divide archivos monolíticos en módulos más pequeños y manejables.
Resuelve el problema de archivos con 1500+ líneas que violan SRP.
"""

import re
from pathlib import Path
from typing import List, Dict, Optional
import sys

# Añadir el directorio del proyecto al path de Python
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class MonolithicFileSplitter:
    def __init__(self, root_dir: str = "."):
        self.root = Path(root_dir)
        self.app_dir = self.root / "app" / "api"
        self.large_files = []
        self.file_analysis = []

    def find_large_files(self, min_lines: int = 500) -> List[Dict]:
        """Encuentra archivos Python demasiado grandes."""
        large_files = []

        for file_path in self.app_dir.glob("*.py"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    line_count = sum(1 for _ in f)
                    if line_count >= min_lines:
                        large_files.append({
                            'path': file_path,
                            'lines': line_count,
                            'name': file_path.stem
                        })
            except Exception as e:
                print(f"Error reading {file_path}: {e}")

        self.large_files = sorted(large_files, key=lambda x: x['lines'], reverse=True)
        return self.large_files

    def analyze_file_structure(self, file_path: Path) -> Dict:
        """Analiza la estructura de un archivo Python."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
        except Exception as e:
            return {'error': str(e)}

        analysis = {
            'total_lines': len(lines),
            'imports': [],
            'router_decorators': [],
            'function_defs': [],
            'class_defs': [],
            'async_functions': []
        }

        for i, line in enumerate(lines, 1):
            line = line.strip()

            # Detectar imports
            if line.startswith('from ') or line.startswith('import '):
                analysis['imports'].append((i, line))

            # Detectar decoradores de router
            if '@router.' in line or '@app.' in line:
                analysis['router_decorators'].append((i, line))

            # Detectar definiciones de función
            func_match = re.match(r'^(async\s+)?def\s+(\w+)', line)
            if func_match:
                is_async = bool(func_match.group(1))
                func_name = func_match.group(2)
                analysis['function_defs'].append((i, func_name, is_async))
                if is_async:
                    analysis['async_functions'].append((i, func_name))

            # Detectar clases
            class_match = re.match(r'^class\s+(\w+)', line)
            if class_match:
                class_name = class_match.group(1)
                analysis['class_defs'].append((i, class_name))

        return analysis

    def suggest_modules_for_file(self, file_analysis: Dict, file_name: str) -> List[Dict]:
        """Sugiere cómo dividir un archivo en módulos."""
        suggestions = []

        # Análisis específico por archivo
        if file_name == 'tracks':
            suggestions.extend([
                {
                    'module': 'overview',
                    'functions': ['get_tracks_overview', 'get_recently_added_tracks'],
                    'description': 'Endpoints para vista general de tracks'
                },
                {
                    'module': 'playback',
                    'functions': ['record_track_play', 'get_most_played_tracks', 'get_recent_play_history'],
                    'description': 'Endpoints de reproducción e historial'
                },
                {
                    'module': 'favorites',
                    'functions': ['get_track_recommendations', 'resolve_tracks'],
                    'description': 'Gestión de favoritos y recomendaciones'
                },
                {
                    'module': 'downloads',
                    'functions': ['get_track_chart_stats'],
                    'description': 'Endpoints relacionados con charts y estadísticas'
                }
            ])

        elif file_name == 'search':
            suggestions.extend([
                {
                    'module': 'orchestrated',
                    'functions': ['search_orchestrated'],
                    'description': 'Búsqueda orquestada principal'
                },
                {
                    'module': 'artist_profile',
                    'functions': ['search_artist_profile'],
                    'description': 'Búsqueda y perfil de artistas'
                },
                {
                    'module': 'tracks_quick',
                    'functions': ['search_tracks_quick'],
                    'description': 'Búsqueda rápida de tracks'
                }
            ])

        elif file_name == 'artists':
            suggestions.extend([
                {
                    'module': 'search',
                    'functions': ['search_artists', 'search_artists_auto_download'],
                    'description': 'Búsqueda de artistas'
                },
                {
                    'module': 'discography',
                    'functions': ['get_artist_albums', 'get_full_discography'],
                    'description': 'Gestión de discografía'
                },
                {
                    'module': 'management',
                    'functions': ['save_artist_to_db', 'sync_artist_discography', 'delete_artist_end'],
                    'description': 'CRUD de artistas'
                }
            ])

        # Sugerencias genéricas basadas en funciones encontradas
        if len(file_analysis.get('function_defs', [])) > 15:
            suggestions.append({
                'module': 'utils',
                'functions': [],
                'description': 'Funciones utilitarias compartidas'
            })

        return suggestions

    def generate_split_plan(self, file_info: Dict) -> str:
        """Genera un plan detallado para dividir un archivo."""
        file_name = file_info['name']
        analysis = file_info.get('analysis', {})
        suggestions = file_info.get('suggestions', [])

        plan = [
            f"📋 PLAN DE DIVISIÓN: {file_name.upper()}.PY",
            "=" * 80,
            "\n📊 Estado Actual:",
            f"   • Líneas totales: {file_info['lines']}",
            f"   • Funciones: {len(analysis.get('function_defs', []))}",
            f"   • Clases: {len(analysis.get('class_defs', []))}",
            f"   • Endpoints: {len(analysis.get('router_decorators', []))}",
            f"   • Funciones async: {len(analysis.get('async_functions', []))}"
        ]

        if suggestions:
            plan.append("\n🗂  Módulos Sugeridos:")
            for i, suggestion in enumerate(suggestions, 1):
                plan.append(f"   {i}. {suggestion['module']}/")
                plan.append(f"      📄 {suggestion['description']}")
                if suggestion.get('functions'):
                    plan.append(f"      🔧 Funciones: {', '.join(suggestion['functions'])}")
                plan.append("")

        plan.append("\n🛠️  Acciones Recomendadas:")
        plan.append("   1. Crear directorio: app/api/{file_name}/")
        plan.append("   2. Mover cada grupo de funciones a su módulo")
        plan.append("   3. Crear __init__.py con imports consolidados")
        plan.append("   4. Actualizar app/main.py para importar nuevos routers")
        plan.append("   5. Probar que Todos los endpoints sigan funcionando")

        return "\n".join(plan)

    def create_module_template(self, module_info: Dict, parent_file: str) -> str:
        """Crea una plantilla para un nuevo módulo."""
        module_name = module_info['module']
        description = module_info['description']

        template = f'''"""
{module_name.title()} endpoints for {description.lower()}.

"""
import logging  # noqa: E402
from typing import List  # noqa: E402

from fastapi import APIRouter, Query, Path, HTTPException, Depends  # noqa: E402
from sqlmodel.ext.asyncio.session import AsyncSession  # noqa: E402

from ..core.db import get_session, SessionDep  # noqa: E402
from ..models.base import Track, Artist, Album  # noqa: E402

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/{parent_file}", tags=["{module_name}"])

'''

        # Añadir plantillas de funciones específicas
        if 'overview' in module_name:
            template += '''
@router.get("/overview")
async def get_tracks_overview(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    session: AsyncSession = Depends(SessionDep)
) -> dict:
    """Return tracks with artist, album, and cache status."""
    # TODO: Implementar lógica específica de overview
    pass
'''

        elif 'playback' in module_name:
            template += '''
@router.post("/play/{{track_id}}")
async def record_track_play(
    request: Request,
    track_id: int = Path(..., description="Track ID"),
    session: AsyncSession = Depends(SessionDep)
) -> dict:
    """Record a play for a track."""
    # TODO: Implementar lógica de reproducción
    pass
'''

        template += '\n'
        return template

    def analyze_all_files(self):
        """Analiza todos los archivos grandes encontrados."""
        self.large_files = self.find_large_files()

        if not self.large_files:
            print("✅ No se encontraron archivos monolíticos (>500 líneas)")
            return

        print(f"🔍 Analizando {len(self.large_files)} archivos monolíticos...")
        print("=" * 80)

        for file_info in self.large_files:
            file_path = file_info['path']
            analysis = self.analyze_file_structure(file_path)
            suggestions = self.suggest_modules_for_file(analysis, file_info['name'])

            self.file_analysis.append({
                'path': file_path,
                'info': file_info,
                'analysis': analysis,
                'suggestions': suggestions
            })

    def generate_report(self) -> str:
        """Genera un reporte completo del análisis."""
        if not self.file_analysis:
            return "✅ No se encontraron archivos monolíticos para analizar."

        report = [
            "📋 ANÁLISIS DE ARCHIVOS MONOLÍTICOS",
            "=" * 80,
            f"\n📊 Resumen: {len(self.file_analysis)} archivos necesitan refactorización"
        ]

        total_lines = sum(file['info']['lines'] for file in self.file_analysis)
        total_functions = sum(len(file['analysis'].get('function_defs', [])) for file in self.file_analysis)

        report.extend([
            f"📈 Líneas totales: {total_lines:,}",
            f"🔧 Funciones totales: {total_functions}",
            f"📅 Promedio líneas/archivo: {total_lines // len(self.file_analysis):,}"
        ])

        # Detalle por archivo
        for file_data in self.file_analysis:
            file_name = file_data['info']['name']
            lines = file_data['info']['lines']

            report.extend([
                "\n" + "=" * 60,
                f"\n📁 {file_name.upper()}.PY",
                f"📊 {lines:,} líneas",
                f"⚠️  {'NECESITA DIVISIÓN URGENTE' if lines > 1000 else 'NECESITA DIVISIÓN'}"
            ])

            # Plan de división
            plan = self.generate_split_plan({
                'name': file_name,
                'analysis': file_data['analysis'],
                'suggestions': file_data['suggestions'],
                'lines': lines
            })
            report.append(plan)

        # Recomendaciones generales
        report.extend([
            "\n" + "=" * 80,
            "\n🎯 RECOMENDACIONES GENERALES:",
            "\n1. 📂 CREAR ESTRUCTURA POR MÓDULOS:",
            "   app/api/tracks/",
            "   ├── __init__.py",
            "   ├── overview.py",
            "   ├── playback.py",
            "   ├── downloads.py",
            "   └── favorites.py",
            "\n2. 🔄 ACTUALIZAR IMPORTS:",
            "   app/main.py debe importar los nuevos routers",
            "   Cada módulo debe tener sus dependencias específicas",
            "\n3. 🧪 TESTING:",
            "   Probar cada módulo independientemente",
            "   Verificar que Todos los endpoints sigan accesibles",
            "\n4. 📖 DOCUMENTACIÓN:",
            "   Actualizar referencias a rutas antiguas",
            "   Documentar nueva estructura en README.md"
        ])

        return "\n".join(report)

    def create_split_scaffolding(self, target_file: Optional[str] = None):
        """Crea la estructura base para la división de archivos."""
        if not target_file and self.file_analysis:
            # Seleccionar el archivo más grande por defecto
            max_info = max(self.file_analysis, key=lambda x: x['info']['lines'])
            target_file = max_info['info']['name']

        target_data = None
        for file_data in self.file_analysis:
            if file_data['info']['name'] == target_file:
                target_data = file_data
                break

        if not target_data:
            print(f"❌ No se encontró el archivo: {target_file}")
            return

        file_name = target_data['info']['name']
        suggestions = target_data['suggestions']

        print(f"🏗️  Creando scaffolding para división de: {file_name}.py")

        # Crear directorio
        if isinstance(file_name, str):
            module_dir = self.app_dir / file_name
        else:
            module_dir = self.app_dir / str(file_name)
        module_dir.mkdir(exist_ok=True)

        # Crear __init__.py
        init_content = f'''"""
{file_name.title()} endpoints module.

This module contains {file_name}-related functionality split into
manageable, focused sub-modules.
"""

from fastapi import APIRouter  # noqa: E402

# Import all sub-routers
from .overview import router as overview_router  # noqa: E402
from .playback import router as playback_router  # noqa: E402
from .downloads import router as downloads_router  # noqa: E402
from .favorites import router as favorites_router  # noqa: E402

# Main router
router = APIRouter(prefix="/{file_name}", tags=["{file_name}"])

# Include all sub-routers
router.include_router(overview_router)
router.include_router(playback_router)
router.include_router(downloads_router)
router.include_router(favorites_router)

# Export main router for app/main.py
__all__ = ["router"]
'''

        with open(module_dir / "__init__.py", "w", encoding="utf-8") as f:
            f.write(init_content)

        # Crear archivos de módulos
        for suggestion in suggestions:
            module_path = module_dir / f"{suggestion['module']}.py"
            module_content = self.create_module_template(suggestion, file_name)

            with open(module_path, "w", encoding="utf-8") as f:
                f.write(module_content)

        print(f"✅ Estructura creada en: {module_dir}")
        print(f"📁 Módulos creados: {[s['module'] for s in suggestions]}")


def main():
    import argparse  # noqa: E402

    parser = argparse.ArgumentParser(description="Análisis y división de archivos monolíticos")
    parser.add_argument("--analyze", action="store_true", help="Analizar archivos monolíticos")
    parser.add_argument("--scaffold", help="Crear scaffolding para archivo específico")
    parser.add_argument("--report", action="store_true", help="Generar reporte completo")
    parser.add_argument("--root", default=".", help="Directorio raíz del proyecto")

    args = parser.parse_args()

    if not any([args.analyze, args.scaffold, args.report]):
        print("Uso: python split_monolithic_files.py --analyze|--scaffold FILE|--report")
        return

    splitter = MonolithicFileSplitter(args.root)

    if args.analyze or args.report:
        print("🔍 Analizando estructura de archivos...")
        splitter.analyze_all_files()

        if args.report:
            report = splitter.generate_report()
            print("\n" + report)

            # Guardar reporte
            with open("monolithic_files_analysis.txt", "w", encoding="utf-8") as f:
                f.write(report)
            print("\n📄 Reporte guardado en: monolithic_files_analysis.txt")

    elif args.scaffold:
        print("🏗️  Creando scaffolding para división...")
        splitter.create_split_scaffolding(args.scaffold)


if __name__ == "__main__":
    main()
