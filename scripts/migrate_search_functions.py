#!/usr/bin/env python3
"""
Mueve automáticamente la lógica desde search.py a los módulos separados.
Divide orchestrated_search, search_artist_profile y search_tracks_quick.
"""

from pathlib import Path
import sys
from typing import List

# Añadir el directorio del proyecto al path de Python
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class SearchMigrator:
    def __init__(self):
        self.root = Path(".")
        self.app_dir = self.root / "app" / "api"
        self.source_file = self.app_dir / "search.py"
        self.target_dir = self.app_dir / "search"

    def extract_function_with_dependencies(
        self,
        func_name: str,
        start_line: int,
        target_file: Path,
        module_name: str
    ) -> bool:
        """Extrae una función y sus dependencias del archivo original."""
        try:
            print(f"🔄 Extrayendo {func_name} (línea {start_line})...")

            with open(self.source_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Encontrar el inicio y fin de la función
            func_start = start_line - 1  # 0-based
            func_lines = []
            brace_count = 0
            in_function = False

            for i in range(func_start, len(lines)):
                line = lines[i]

                # Detectar el inicio de la función si no lo hemos encontrado
                if not in_function and f"def {func_name}(" in line:
                    in_function = True

                if in_function:
                    func_lines.append(line)

                    # Contar llaves para detectar el fin de la función
                    brace_count += line.count('{') - line.count('}')

                    # Si hemos cerrado todas las llaves, la función termina
                    if brace_count <= 0 and line.strip():
                        break

            if not func_lines:
                print(f"❌ No se encontró la función {func_name}")
                return False

            # Extraer imports necesarios
            imports_needed = self._extract_needed_imports(func_lines)

            # Escribir en el archivo destino
            with open(target_file, 'w', encoding='utf-8') as f:
                # Escribir imports
                f.write(f'"""{module_name} endpoints module.\n\n')
                f.write(f'"""Extracted from search.py - Function: {func_name}\n')
                f.write('"""\n\n')

                for imp in imports_needed:
                    f.write(f'{imp}\n')

                f.write('\nfrom sqlmodel.ext.asyncio.session import AsyncSession\n')
                f.write('from ..core.db import get_session, SessionDep\n')
                f.write('from ..models.base import Artist, Album, Track\n')
                f.write('from ..core.config import settings\n')
                f.write('from ..core.lastfm import lastfm_client\n')
                f.write('from ..core.image_proxy import proxy_image_list\n')
                f.write('\n')

                # Escribir la función con indentación ajustada
                for i, line in enumerate(func_lines):
                    # Ajustar imports relativos
                    if line.strip().startswith(('from .', 'import')):
                        continue  # Omitimos los imports locales, los agregamos arriba

                    # Escribir la línea
                    f.write(line)

            print(f"✅ {func_name} movida a {target_file.name}")
            return True

        except Exception as e:
            print(f"❌ Error moviendo {func_name}: {e}")
            return False

    def _extract_needed_imports(self, func_lines: List[str]) -> List[str]:
        """Extrae los imports necesarios de las líneas de la función."""
        imports_needed = set()

        # Imports que sabemos que son necesarios basados en el análisis del código
        base_imports = {
            'import asyncio',
            'import json',
            'import logging',
            'import time',
            'import ast',
            'import difflib',
            'from datetime import timedelta',
            'from typing import Optional',
            'from fastapi import APIRouter, HTTPException, Query, Depends, Request',
            'from sqlmodel import select, and_, desc, or_, func',
            'from sqlalchemy import desc, or_, func'
        }

        # Buscar imports en las líneas de la función
        for line in func_lines:
            line_stripped = line.strip()

            for import_line in base_imports:
                if import_line in line_stripped:
                    imports_needed.add(import_line)

        return sorted(list(imports_needed))

    def update_functions_in_module(self, module_file: Path, function_code: str):
        """Actualiza las funciones TODO con código real."""
        try:
            with open(module_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Reemplazar el TODO placeholder con el código real
            updated_content = content.replace('    # TODO: Implement search_orchestrated logic', function_code)

            with open(module_file, 'w', encoding='utf-8') as f:
                f.write(updated_content)

            print(f"✅ Actualizado: {module_file.name}")
            return True

        except Exception as e:
            print(f"❌ Error actualizando {module_file.name}: {e}")
            return False

    def move_orchestrated_function(self) -> bool:
        """Mueve la función orchestrated_search al módulo correspondiente."""
        # Línea aproximada donde empieza orchestrated_search
        orchestrated_start = 846  # Basado en el análisis anterior

        # Extraer la función
        with open(self.source_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        func_lines = []
        in_function = False
        brace_count = 0

        for i in range(orchestrated_start - 1, len(lines)):
            line = lines[i]

            if not in_function and "async def orchestrated_search(" in line:
                in_function = True
                # Incluir el decorador @router.get también
                if i > 0 and "@router.get" in lines[i - 1]:
                    func_lines.append(lines[i - 1])

            if in_function:
                func_lines.append(line)
                brace_count += line.count('{') - line.count('}')

                if brace_count <= 0 and line.strip():
                    break

        # Crear la función reemplazando el TODO
        function_code = ''.join(func_lines)
        return self.update_functions_in_module(
            self.target_dir / "orchestrated.py",
            function_code
        )

    def move_artist_profile_function(self) -> bool:
        """Mueve la función search_artist_profile al módulo correspondiente."""
        artist_profile_start = 1162  # Basado en el análisis anterior

        # Extraer la función
        with open(self.source_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        func_lines = []
        in_function = False
        brace_count = 0

        for i in range(artist_profile_start - 1, len(lines)):
            line = lines[i]

            if not in_function and "async def search_artist_profile(" in line:
                in_function = True
                # Incluir el decorador @router.get también
                if i > 0 and "@router.get" in lines[i - 1]:
                    func_lines.append(lines[i - 1])

            if in_function:
                func_lines.append(line)
                brace_count += line.count('{') - line.count('}')

                if brace_count <= 0 and line.strip():
                    break

        # Crear la función reemplazando el TODO
        function_code = ''.join(func_lines)
        return self.update_functions_in_module(
            self.target_dir / "artist_profile.py",
            function_code
        )

    def move_tracks_quick_function(self) -> bool:
        """Mueve la función search_tracks_quick al módulo correspondiente."""
        tracks_quick_start = 1562  # Basado en el análisis anterior

        # Extraer la función
        with open(self.source_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        func_lines = []
        in_function = False
        brace_count = 0

        for i in range(tracks_quick_start - 1, len(lines)):
            line = lines[i]

            if not in_function and "async def search_tracks_quick(" in line:
                in_function = True
                # Incluir el decorador @router.get también
                if i > 0 and "@router.get" in lines[i - 1]:
                    func_lines.append(lines[i - 1])

            if in_function:
                func_lines.append(line)
                brace_count += line.count('{') - line.count('}')

                if brace_count <= 0 and line.strip():
                    break

        # Crear la función reemplazando el TODO
        function_code = ''.join(func_lines)
        return self.update_functions_in_module(
            self.target_dir / "tracks_quick.py",
            function_code
        )

    def backup_original_file(self) -> bool:
        """Crea un backup del archivo original."""
        try:
            backup_file = self.source_file.with_suffix('.py.backup')

            with open(self.source_file, 'r', encoding='utf-8') as f:
                content = f.read()

            with open(backup_file, 'w', encoding='utf-8') as f:
                f.write(content)

            print(f"✅ Backup creado: {backup_file.name}")
            return True

        except Exception as e:
            print(f"❌ Error creando backup: {e}")
            return False

    def execute_migration(self) -> bool:
        """Ejecuta la migración completa."""
        print("🔄 Iniciando migración de search.py a módulos separados...")

        # 1. Crear backup del archivo original
        if not self.backup_original_file():
            return False

        # 2. Mover las tres funciones principales
        migrations = [
            ("orchestrated_search", self.move_orchestrated_function),
            ("search_artist_profile", self.move_artist_profile_function),
            ("search_tracks_quick", self.move_tracks_quick_function)
        ]

        success_count = 0
        for func_name, migration_func in migrations:
            print(f"\n📁 Migrando {func_name}...")
            if migration_func():
                success_count += 1
            else:
                print(f"❌ Falló migración de {func_name}")

        print("\n📊 Resultados:")
        print(f"   ✅ Funciones migradas: {success_count}/3")
        print("   📄 Backup: search.py.backup")

        if success_count == 3:
            print("\n🎉 ¡Migración completada exitosamente!")
            print("\n📋 Siguientes pasos:")
            print("   1. Probar los nuevos endpoints:")
            print("      http://localhost:8000/search/orchestrated/orchestrated/")
            print("      http://localhost:8000/search/artist-profile/artist-profile/")
            print("      http://localhost:8000/search/tracks-quick/tracks-quick/")
            print("   2. Verificar que funcionen correctamente")
            print("   3. Actualizar el frontend si es necesario")
            return True
        else:
            print("\n❌ La migración no se completó exitosamente")
            return False


def main():
    migrator = SearchMigrator()

    print("🔧 Migrador Automático de Search.py")
    print("=" * 50)

    # Verificar que existen los archivos necesarios
    if not migrator.source_file.exists():
        print(f"❌ No se encontró: {migrator.source_file}")
        return 1

    if not migrator.target_dir.exists():
        print(f"❌ No se encontró el directorio: {migrator.target_dir}")
        return 1

    # Ejecutar la migración
    success = migrator.execute_migration()

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
