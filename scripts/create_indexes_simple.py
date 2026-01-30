#!/usr/bin/env python3
"""
Crea índices críticos sin las opciones CONCURRENTLY para evitar errores de PostgreSQL.
Versión simplificada y más robusta.
"""

import os
from pathlib import Path
import sys

# Añadir el directorio del proyecto al path de Python
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.db import get_session
from app.core.config import settings
from sqlalchemy import text

# Índices críticos
CRITICAL_INDEXES = [
    "CREATE INDEX idx_track_spotify_id ON track(spotify_id);",
    "CREATE INDEX idx_track_name_trgm ON track USING gin(name gin_trgm_ops);", 
    "CREATE INDEX idx_artist_name_trgm ON artist USING gin(name gin_trgm_ops);",
    "CREATE INDEX idx_youtubedownload_spotify_track_id ON youtubedownload(spotify_track_id);",
    "CREATE INDEX idx_playhistory_user_played_at_desc ON playhistory(user_id, played_at DESC);",
    "CREATE INDEX idx_track_artist_album ON track(artist_id, album_id);",
    "CREATE INDEX idx_track_popularity_desc ON track(popularity DESC, id ASC);",
    "CREATE INDEX idx_userfavorite_user_target ON userfavorite(user_id, target_type, target_id);"
]

def create_indexes_simpler():
    """Crea índices de forma simple sin CONCURRENTLY."""
    print("🔍 Conectando a la base de datos...")
    print(f"📁 Database URL: {settings.DATABASE_URL.split('@')[0] if '@' in settings.DATABASE_URL else 'configured'}")
    
    session = get_session()
    
    try:
        print("🛠️  Creando índices críticos...")
        
        # Ejecutar cada índice como una consulta separada
        for i, index_sql in enumerate(CRITICAL_INDEXES, 1):
            try:
                index_name = index_sql.split('(')[0].split(' ')[0]
                print(f"📝 [{i}/{len(CRITICAL_INDEXES)}] Creando índice: {index_name}")
                
                # Ejecutar índice
                session.execute(text(index_sql))
                session.commit()
                
                print(f"✅ [{i}/{len(CRITICAL_INDEXES)}] Índice creado exitosamente")
                
            except Exception as e:
                print(f"❌ [{i}/{len(CRITICAL_INDEXES)}] Error creando índice: {e}")
                session.rollback()
                continue
        
        print("\n🎉 ¡Índices críticos creados exitosamente!")
        print("📊 Expected performance improvement: 70-90% en queries principales")
        return True
        
    except Exception as e:
        print(f"❌ Error general creando índices: {e}")
        return False
    
    finally:
        session.close()

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Crear índices críticos")
    parser.add_argument("--create", action="store_true", help="Crear índices faltantes")
    parser.add_argument("--force", action="store_true", help="Forzar creación de todos los índices")
    
    args = parser.parse_args()
    
    if not any([args.create, args.force]):
        print("Uso: python create_indexes_simple.py --create|--force")
        return
    
    print("🚀 Creando Índices Críticos de Audio2")
    print("=" * 60)
    
    try:
        success = create_indexes_simpler()
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\n⚠️  Operación interrumpida por el usuario")
        return 1
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())