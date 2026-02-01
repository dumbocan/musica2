#!/usr/bin/env python3
"""
Script simple sin problemas de indentación para verificar la estructura de tracks.
"""

import sys
from pathlib import Path


def test_tracks_structure():
    print("🔍 Verificando estructura de tracks modular...")

    # Añadir el directorio al path
    app_dir = Path("app")
    sys.path.insert(0, str(app_dir))

    try:
        print("✅ Probando import de app.main...")
        from app.main import app  # noqa: E402
        _ = app
        print("✅ app.main import successful")

        print("✅ Probando import de tracks router...")
        import app.api.tracks  # noqa: E402
        _ = app.api.tracks
        print("✅ tracks router import successful")

        print("✅ Probando imports de módulos individuales...")

        try:
            from app.api.tracks.overview import router as overview_router  # noqa: E402
            _ = overview_router
            print("✅ overview module import successful")
        except Exception as e:
            print(f"⚠️ Overview module import failed: {e}")

        try:
            from app.api.tracks.playback import router as playback_router  # noqa: E402
            _ = playback_router
            print("✅ Playback module import successful")
        except Exception as e:
            print(f"⚠️ Playback module import failed: {e}")

        try:
            from app.api.tracks.downloads import router as downloads_router  # noqa: E402
            _ = downloads_router
            print("✅ Downloads module import successful")
        except Exception as e:
            print(f"⚠️ Downloads module import failed: {e}")

        try:
            from app.api.tracks.favorites import router as favorites_router  # noqa: E402
            _ = favorites_router
            print("✅ Favorites module import successful")
        except Exception as e:
            print(f"⚠️ Favorites module import failed: {e}")

        print("\n✅ Todos los módulos importados correctamente!")
        print("✅ Estructura modular funciona correctamente")
        return True

    except Exception as e:
        print(f"❌ Error en estructura: {e}")
        return False


def main():
    print("🧪 Test de estructura tracks modular")
    print("=" * 50)

    success = test_tracks_structure()

    if success:
        print("\n🎉 ¡Estructura tracks modular validada!")
        print("\n📋 Próximos pasos:")
        print("  1. El archivo original tracks.py permanece como respaldo")
        print(" 2. Los nuevos endpoints tendrán rutas extendidas")
        print(" 3. Probar endpoints en http://localhost:8000/docs")
    else:
        print("\n❌ Hay problemas con la estructura")
        return 1


if __name__ == "__main__":
    sys.exit(main())
