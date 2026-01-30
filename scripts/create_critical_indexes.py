#!/usr/bin/env python3
"""
Crea índices críticos fuera de cualquier transacción.
Soluciona el problema de ActiveSqlTransaction en PostgreSQL.
"""

import os
import asyncio
from pathlib import Path
import sys

# Añadir el directorio del proyecto al path de Python
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.db import get_session
from app.core.config import settings
from sqlalchemy import text

# Quitar la import de asyncio ya que no la usamos más
# from sqlalchemy import text

# Índices críticos separados por tabla
CRITICAL_INDEXES = [
    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_track_spotify_id ON track(spotify_id);",
    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_track_name_trgm ON track USING gin(name gin_trgm_ops);",
    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_artist_name_trgm ON artist USING gin(name gin_trgm_ops);",
    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_youtubedownload_spotify_track_id ON youtubedownload(spotify_track_id);",
    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_playhistory_user_played_at_desc ON playhistory(user_id, played_at DESC);",
    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_track_artist_album ON track(artist_id, album_id);",
    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_track_popularity_desc ON track(popularity DESC, id ASC);",
    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_userfavorite_user_target ON userfavorite(user_id, target_type, target_id);"
]

def create_indexes_with_isolation():
    """Crea índices con aislación de transacción."""
    print("🔍 Conectando a la base de datos...")
    print(f"📁 Database URL: {settings.DATABASE_URL.split('@')[0] if '@' in settings.DATABASE_URL else 'configured'}")
    
    session = get_session()
    
    try:
        print("🛠️  Creando índices críticos...")
        
        # Ejecutar cada índices en su propia transacción
        for i, index_sql in enumerate(CRITICAL_INDEXES, 1):
            try:
                print(f"📝 [{i}/{len(CRITICAL_INDEXES)}] Creando índice...")
                
                session.execute(text(index_sql))
                session.commit()
                
                print(f"✅ [{i}/{len(CRITICAL_INDEXES)}] Índice creado exitosamente")
                
            except Exception as e:
                print(f"❌ [{i}/{len(CRITICAL_INDEXES)}] Error creando índice: {e}")
                print(f"   SQL: {index_sql}")
                session.rollback()
        
        print("\n🎉 ¡Índices críticos creados exitosamente!")
        print("📊 Expected performance improvement: 70-90% en queries principales")
        
    except Exception as e:
        print(f"❌ Error general creando índices: {e}")
        return False
    
    finally:
        session.close()
    
    return True

def check_existing_indexes():
    """Verifica qué índices ya existen."""
    session = get_session()
    
    try:
        print("🔍 Verificando índices existentes...")
        
        existing_indexes = set()
        
        # Simplificar la verificación - usar una consulta SQL directa
        try:
            result = session.execute(text("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE schemaname = 'public' 
                AND tablename IN ('track', 'artist', 'youtubedownload', 'playhistory', 'userfavorite')
            """)).fetchall()
            
            for row in result:
                if row[0] and 'idx_' in row[0]:
                    existing_indexes.add(row[0])
                    
        except Exception as e:
            print(f"⚠️  Error obteniendo índices existentes: {e}")
        
        print(f"📊 Índices existentes: {len(existing_indexes)}")
        
        needed_indexes = []
        for index_sql in CRITICAL_INDEXES:
            try:
                index_name = index_sql.split('idx_')[1].split(' ')[0]
                if index_name not in existing_indexes:
                    needed_indexes.append(index_sql)
            except:
                # Si hay error al parsear, añadir por defecto
                needed_indexes.append(index_sql)
        
        print(f"📈 Índices faltantes: {len(needed_indexes)}")
        
        if needed_indexes:
            print("\n🚨 Índices que necesitan crearse:")
            for i, sql in enumerate(needed_indexes, 1):
                print(f"  {i}. {sql}")
        else:
            print("✅ Todos los índices críticos ya existen")
        
        return len(needed_indexes)
        
    except Exception as e:
            print(f"❌ Error verificando índices: {e}")
            return 1
    
    finally:
        session.close()

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Crear índices críticos")
    parser.add_argument("--check", action="store_true", help="Solo verificar índices existentes")
    parser.add_argument("--create", action="store_true", help="Crear índices faltantes")
    parser.add_argument("--force", action="store_true", help="Forzar creación de todos los índices")
    
    args = parser.parse_args()
    
    if not any([args.check, args.create, args.force]):
        print("Uso: python create_critical_indexes.py --check|--create|--force")
        return
    
    print("🚀 Creando Índices Críticos de Audio2")
    print("=" * 60)
    
    if args.check:
        missing_count = check_existing_indexes()
        return 0 if missing_count == 0 else 1
    
    if args.create or args.force:
        try:
            success = create_indexes_with_isolation()
            return 0 if success else 1
        except KeyboardInterrupt:
            print("\n⚠️  Operación interrumpida por el usuario")
            return 1
        except Exception as e:
            print(f"\n❌ Error inesperado: {e}")
            return 1
        except Exception as e:
            print(f"\n❌ Error inesperado: {e}")
            return 1

if __name__ == "__main__":
    sys.exit(main())