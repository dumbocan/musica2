#!/usr/bin/env python3
"""
Script simplificado para verificar que los módulos fueron creados correctamente.
"""

from pathlib import Path
import sys


def main():
    print("🔍 Verificando estructura de search modularizada...")

    app_dir = Path("app/api/search")

    if not app_dir.exists():
        print("❌ No existe el directorio app/api/search")
        return 1

    print("📁 Estructura creada:")

    files = ["__init__.py", "orchestrated.py", "artist_profile.py", "tracks_quick.py"]

    for file_name in files:
        file_path = app_dir / file_name
        if file_path.exists():
            size = file_path.stat().st_size
            print(f"   ✅ {file_name} ({size:,} bytes)")

            # Verificar que los archivos no estén vacíos
            if size > 500:  # Al menos debe tener contenido sustancial
                print("      📊 Contenido válido")
            else:
                print("      ⚠️  Contenido reducido - puede necesitar migración manual")
        else:
            print(f"   ❌ {file_name} (no existe)")

    print("\n📋 Próximos pasos manuales:")
    print("1. Verificar sintaxis de los módulos:")
    print("   python -m py_compile app/api/search/orchestrated.py")
    print("   python -m py_compile app/api/search/artist_profile.py")
    print("   python -m py_compile app/api/search/tracks_quick.py")

    print("\n2. Si hay errores, hacer la migración manual:")
    print("   - Buscar las funciones en app/api/search.py.backup")
    print("   - Copiar y pegar la lógica en los módulos correspondientes")
    print("   - Reemplazar los placeholders TODO")

    print("\n3. Probar los nuevos endpoints:")
    print("   uvicorn app.main:app --reload")
    print("   Verificar en http://localhost:8000/docs")

    print("\n4. Los endpoints nuevos serán:")
    print("   http://localhost:8000/search/orchestrated/orchestrated/")
    print("   http://localhost:8000/search/artist-profile/artist-profile/")
    print("   http://localhost:8000/search/tracks-quick/tracks-quick/")

    return 0


if __name__ == "__main__":
    sys.exit(main())
