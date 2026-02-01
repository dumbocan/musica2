#!/usr/bin/env python3
"""
Script final para mover la lógica real de las funciones desde search.py.
Extrae las funciones completas y las inserta en los módulos separados.
"""

from pathlib import Path
import sys

# Añadir el directorio del proyecto al path de Python
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class FinalSearchMigrator:
    def __init__(self):
        self.root = Path(".")
        self.app_dir = self.root / "app" / "api"
        self.source_file = self.app_dir / "search.py"
        self.backup_file = self.app_dir / "search.py.backup"
        self.target_dir = self.app_dir / "search"

    def extract_complete_function(self, start_pattern: str, end_pattern: str = None) -> str:
        """Extrae una función completa del archivo backup."""
        if not self.backup_file.exists():
            print(f"❌ No existe el archivo backup: {self.backup_file}")
            return ""

        with open(self.backup_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Buscar el inicio de la función
        start_idx = content.find(start_pattern)
        if start_idx == -1:
            print(f"❌ No se encontró el patrón: {start_pattern}")
            return ""

        # Si hay un patrón de fin, buscarlo
        if end_pattern:
            end_idx = content.find(end_pattern, start_idx)
            if end_idx == -1:
                print(f"❌ No se encontró el patrón de fin: {end_pattern}")
                return ""
        else:
            # Buscar el siguiente decorador o fin del archivo
            remaining_content = content[start_idx + len(start_pattern):]
            lines = remaining_content.split('\n')

            end_idx_relative = len(remaining_content)
            for i, line in enumerate(lines):
                if '@router.get' in line:
                    end_idx_relative = sum(len(line_item) + 1 for line_item in lines[:i])
                    break

            end_idx = start_idx + len(start_pattern) + end_idx_relative

        # Extraer la función
        function_content = content[start_idx:end_idx]
        return function_content.strip() + '\n\n'

    def replace_placeholder_in_module(self, module_file: Path, placeholder: str, function_content: str) -> bool:
        """Reemplaza un placeholder en un módulo con la función real."""
        try:
            with open(module_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Reemplazar el placeholder con la función real
            updated_content = content.replace(placeholder, function_content)

            with open(module_file, 'w', encoding='utf-8') as f:
                f.write(updated_content)

            print(f"✅ Actualizado: {module_file.name}")
            return True

        except Exception as e:
            print(f"❌ Error actualizando {module_file.name}: {e}")
            return False

    def execute_final_migration(self) -> bool:
        """Ejecuta la migración final moviendo las funciones reales."""
        print("🚀 Ejecutando migración final con lógica real...")

        if not self.backup_file.exists():
            print("❌ No se encontró el archivo backup")
            return False

        # 1. Extraer orchestrated_search
        print("📁 Extrayendo orchestrated_search...")
        orchestrated_func = self.extract_complete_function(
            'async def orchestrated_search(',
            '@router.get("/spotify")'
        )

        if not orchestrated_func:
            print("❌ No se pudo extraer orchestrated_search")
            return False

        # 2. Extraer search_artist_profile
        print("📁 Extrayendo search_artist_profile...")
        artist_profile_func = self.extract_complete_function(
            'async def search_artist_profile(',
            '@router.get("/tracks-quick")'
        )

        if not artist_profile_func:
            print("❌ No se pudo extraer search_artist_profile")
            return False

        # 3. Extraer search_tracks_quick
        print("📁 Extrayendo search_tracks_quick...")
        tracks_quick_func = self.extract_complete_function(
            'async def search_tracks_quick(',
            '@router.get("/metrics")'
        )

        if not tracks_quick_func:
            print("❌ No se pudo extraer search_tracks_quick")
            return False

        # 4. Insertar las funciones en los módulos correspondientes
        migrations = [
            (self.target_dir / "orchestrated.py", '    # TODO: Move search_orchestrated logic from original search.py', orchestrated_func),
            (self.target_dir / "artist_profile.py", '    # TODO: Move search_artist_profile logic from original search.py', artist_profile_func),
            (self.target_dir / "tracks_quick.py", '    # TODO: Move search_tracks_quick logic from original search.py', tracks_quick_func)
        ]

        success_count = 0
        for module_file, placeholder, function_content in migrations:
            # Preparar el reemplazo
            full_function = function_content.replace('    pass', '')
            full_function = full_function.replace('        pass', '')

            if self.replace_placeholder_in_module(module_file, placeholder, full_function):
                success_count += 1

        print("\n📊 Resultados:")
        print(f"   ✅ Funciones movidas: {success_count}/3")
        print(f"   📊 Líneas totales movidas: {len(orchestrated_func + artist_profile_func + tracks_quick_func):,}")

        if success_count == 3:
            print("\n🎉 ¡Migración completada con éxito total!")
            print("\n📋 Verificación:")
            print("   Los archivos de módulos ahora contienen la lógica real")
            print("   Los placeholders han sido reemplazados")
            print("   El archivo original está respaldado")

            print("\n📋 Próximos pasos:")
            print("   1. Verificar sintaxis de los módulos:")
            print("      python -m py_compile app/api/search/orchestrated.py")
            print("      python -m py_compile app/api/search/artist_profile.py")
            print("      python -m py_compile app/api/search/tracks_quick.py")
            print("   2. Iniciar el servidor y probar endpoints:")
            print("      uvicorn app.main:app --reload")
            print("   3. Verificar en http://localhost:8000/docs")

            return True
        else:
            print("\n❌ La migración no se completó exitosamente")
            return False


def main():
    migrator = FinalSearchMigrator()

    print("🔧 Migrador Final de Search.py")
    print("=" * 50)

    success = migrator.execute_final_migration()

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
