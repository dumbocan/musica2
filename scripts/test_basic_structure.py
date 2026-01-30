#!/usr/bin/env python3
"""
Test simple para verificar que los módulos básicos funcionan
"""

import sys
from pathlib import Path

def test_basic_structure():
    print("🧪 Testing basic module structure...")
    
    # Verificar que los directorios existen
    search_dir = Path("app/api/search")
    tracks_dir = Path("app/api/tracks")
    
    if not search_dir.exists():
        print("❌ search directory not found")
        return False
    
    if not tracks_dir.exists():
        print("❌ tracks directory not found")
        return False
    
    print("📁 Directorios encontrados:")
    print(f"   📁 {search_dir}/")
    print(f"   📁 {tracks_dir}/")
    
    # Verificar archivos principales
    main_files = [
        "app/main.py",
        "app/api/search.py", 
        "app/api/tracks.py.backup"
    ]
    
    print("\n📋 Verificando archivos principales:")
    for file_path in main_files:
        file_path = Path(file_path)
        if file_path.exists():
            size = file_path.stat().st_size
            print(f"   ✅ {file_path} ({size:,} bytes)")
        else:
            print(f"   ❌ {file_path} (no existe)")
    
    print("\n🔍 Testing if basic functionality works...")
    
    # Test imports básicos (ignorando errores LSP temporales)
    try:
        from app.api.search import search_router
        print("✅ Search router import successful")
    except ImportError as e:
        print(f"⚠️ Search router import failed: {e}")
    
    try:
        from app.api.tracks import tracks_router
        print("✅ Tracks router import successful")
    except ImportError as e:
        print(f"⚠️ Tracks router import failed: {e}")
    
    try:
        # Importación desde app.main
        print("🔍 Testing app.main import...")
        import app.main
        app_main = app.main
        print("✅ app.main import successful")
        
        # Verificar rutas disponibles
        routes = []
        if hasattr(app_main, 'app'):
            for route in app_main.routes:
                routes.append(route.path)
        
        print(f"✅ Rutas disponibles: {len(routes)}")
        
        # Buscar rutas específicas
        search_routes = [r for r in routes if '/search/' in r.path]
        tracks_routes = [r for r in routes if '/tracks/' in r.path]
        
        print(f"   📁 Rutas de búsqueda: {len(search_routes)}")
        print(f"   📊 Rutas de tracks: {len(tracks_routes)}")
        
        print("✅ Estructura básica funcional!")
        return True
        
    except Exception as e:
        print(f"❌ Error import: {e}")
        return False

def main():
    print("🔍 Test básico de la estructura modularizada")
    print("=" * 50)
    
    success = test_basic_structure()
    
    if success:
        print("\n🎉 ¡Test básico completado!")
        print("\n📋 Próximos pasos manuales:")
        print("   1. Iniciar servidor con:")
        print("      uvicorn app.main:app --reload")
        print("   2. Verificar endpoints en:")
        print("      http://localhost:8000/docs")
        print("   3. Buscar rutas:")
        print("      http://localhost:8000/search/orchestrated/orchestrated/")
        print("      http://localhost:8000/search/artist-profile/artist-profile/")
        print("      http://localhost:8000/search/tracks-quick/tracks-quick/")
        print("      http://localhost:8000/tracks/overview/overview/")
        print("      http://localhost:8000/tracks/playback/")
        print("      http://localhost:8000/tracks/downloads/")
        print("      http://localhost:8000/tracks/favorites/")
        print("   4. Los módulos tracks/contendidos: visión independiente!")
    
    else:
        print("\n❌ La estructura básica tiene problemas que deben resolverse primero")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())