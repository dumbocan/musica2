#!/usr/bin/env python3
"""
Añade índices críticos a PostgreSQL para mejorar el rendimiento de las consultas más lentas.
Resuelve problemas de performance identificados en el análisis de la base de datos.
"""

import os
import asyncio
from pathlib import Path
import sys

# Añadir el directorio del proyecto al path de Python
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.db import get_session, create_db_and_tables
from app.core.config import settings
from sqlalchemy import text, inspect
from sqlmodel import SQLModel

class DatabaseIndexer:
    def __init__(self):
        self.critical_indexes = [
            {
                "name": "idx_track_spotify_id",
                "sql": "CREATE INDEX CONCURRENTLY idx_track_spotify_id ON track(spotify_id);",
                "description": "Optimizar búsquedas por Spotify ID en tracks",
                "tables": ["track"],
                "impact": "ALTO - Afecta /tracks/overview, búsqueda de tracks"
            },
            {
                "name": "idx_track_name_trgm", 
                "sql": "CREATE INDEX CONCURRENTLY idx_track_name_trgm ON track USING gin(name gin_trgm_ops);",
                "description": "Búsqueda de texto completo en nombres de tracks",
                "tables": ["track"],
                "impact": "ALTO - Mejora búsquedas en frontend"
            },
            {
                "name": "idx_artist_name_trgm",
                "sql": "CREATE INDEX CONCURRENTLY idx_artist_name_trgm ON artist USING gin(name gin_trgm_ops);",
                "description": "Búsqueda de texto completo en nombres de artistas", 
                "tables": ["artist"],
                "impact": "ALTO - Mejora búsqueda de artistas"
            },
            {
                "name": "idx_youtubedownload_spotify_track_id",
                "sql": "CREATE INDEX CONCURRENTLY idx_youtubedownload_spotify_track_id ON youtubedownload(spotify_track_id);",
                "description": "Optimizar uniones con YouTube downloads",
                "tables": ["youtubedownload"],
                "impact": "ALTO - Afecta tracks/overview y YouTube endpoints"
            },
            {
                "name": "idx_playhistory_user_played_at_desc",
                "sql": "CREATE INDEX CONCURRENTLY idx_playhistory_user_played_at_desc ON playhistory(user_id, played_at DESC);",
                "description": "Historial de reproducción por usuario y fecha",
                "tables": ["playhistory"],
                "impact": "MEDIO - Mejora most-played y recent-plays"
            },
            {
                "name": "idx_track_artist_album",
                "sql": "CREATE INDEX CONCURRENTLY idx_track_artist_album ON track(artist_id, album_id);",
                "description": "Consulta de tracks con artista y álbum",
                "tables": ["track", "album"],
                "impact": "MEDIO - Mejora álbumes y discografía"
            },
            {
                "name": "idx_track_popularity_desc",
                "sql": "CREATE INDEX CONCURRENTLY idx_track_popularity_desc ON track(popularity DESC, id ASC);",
                "description": "Tracks ordenados por popularidad",
                "tables": ["track"],
                "impact": "BAJO - Mejora ordenamiento por popularidad"
            },
            {
                "name": "idx_userfavorite_user_target",
                "sql": "CREATE INDEX CONCURRENTLY idx_userfavorite_user_target ON userfavorite(user_id, target_type, target_id);",
                "description": "Búsqueda de favoritos por usuario",
                "tables": ["userfavorite"],
                "impact": "BAJO - Mejora endpoints de favoritos"
            }
        ]
        
    def check_existing_indexes(self, session) -> set:
        """Verifica qué índices ya existen."""
        inspector = inspect(session.bind)
        existing_indexes = set()
        
        for table_name in inspector.get_table_names():
            indexes = inspector.get_indexes(table_name)
            for index in indexes:
                if index['name']:
                    existing_indexes.add(index['name'])
        
        return existing_indexes
    
    def get_missing_indexes(self, session) -> list:
        """Filtra índices que no existen aún."""
        existing = self.check_existing_indexes(session)
        missing = []
        
        for index in self.critical_indexes:
            if index['name'] not in existing:
                missing.append(index)
        
        return missing
    
    def create_index(self, session, index_info) -> bool:
        """Crea un índice específico."""
        try:
            print(f"📝 Creando índice: {index_info['name']}")
            print(f"   📄 Descripción: {index_info['description']}")
            print(f"   📊 Impacto: {index_info['impact']}")
            
            session.execute(text(index_info['sql']))
            session.commit()
            
            print(f"✅ Índice {index_info['name']} creado exitosamente")
            return True
            
        except Exception as e:
            print(f"❌ Error creando índice {index_info['name']}: {e}")
            session.rollback()
            return False
    
    def analyze_query_performance(self, session):
        """Analiza el rendimiento de queries críticas."""
        queries_analysis = [
            {
                "name": "tracks_overview_count",
                "sql": """
                EXPLAIN ANALYZE 
                SELECT COUNT(t.id), 
                       COUNT(DISTINCT t.id) FILTER (WHERE yd.youtube_video_id IS NOT NULL),
                       COUNT(DISTINCT t.id) FILTER (WHERE yd.download_path IS NOT NULL)
                FROM track t
                JOIN artist a ON a.id = t.artist_id  
                LEFT JOIN youtubedownload yd ON yd.spotify_track_id = t.spotify_id
                """,
                "description": "Query principal de /tracks/overview"
            },
            {
                "name": "track_search_by_name",
                "sql": """
                EXPLAIN ANALYZE
                SELECT t.id, t.name, a.name as artist_name
                FROM track t
                JOIN artist a ON a.id = t.artist_id
                WHERE t.name ILIKE '%test%'
                ORDER BY t.popularity DESC
                LIMIT 20
                """,
                "description": "Búsqueda de tracks por nombre"
            }
        ]
        
        print("\n📊 Análisis de rendimiento de queries críticas:")
        print("=" * 80)
        
        for query in queries_analysis:
            print(f"\n🔍 Analizando: {query['description']}")
            try:
                result = session.execute(text(query['sql'])).fetchall()
                for row in result:
                    print(f"   {row[0]}")
                print("-" * 40)
            except Exception as e:
                print(f"❌ Error analizando query: {e}")
    
    def create_missing_indexes(self, session):
        """Crea todos los índices faltantes."""
        missing = self.get_missing_indexes(session)
        
        if not missing:
            print("✅ Todos los índices críticos ya existen")
            return True
        
        print(f"\n📋 Se encontraron {len(missing)} índices faltantes:")
        print("=" * 80)
        
        success_count = 0
        for index in missing:
            if self.create_index(session, index):
                success_count += 1
        
        print(f"\n🎉 Se crearon {success_count}/{len(missing)} índices exitosamente")
        return success_count == len(missing)
    
    def generate_index_report(self, session):
        """Genera un reporte completo del estado de los índices."""
        existing = self.check_existing_indexes(session)
        missing = self.get_missing_indexes(session)
        
        report = ["📊 REPORT: ESTADO DE ÍNDICES CRÍTICOS"]
        report.append("=" * 80)
        report.append(f"\n📈 Índices existentes: {len(existing)}")
        report.append(f"📉 Índices faltantes: {len(missing)}")
        
        if missing:
            report.append("\n🚨 ÍNDICES FALTANTES (Impacto en rendimiento):")
            for index in missing:
                report.append(f"\n❌ {index['name']}")
                report.append(f"   📄 {index['description']}")
                report.append(f"   📊 {index['impact']}")
                report.append(f"   🛠️  SQL: {index['sql']}")
        
        return "\n".join(report)

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Gestión de índices críticos para PostgreSQL")
    parser.add_argument("--check", action="store_true", help="Verificar estado actual de índices")
    parser.add_argument("--create", action="store_true", help="Crear índices faltantes")
    parser.add_argument("--analyze", action="store_true", help="Analizar rendimiento de queries críticas")
    parser.add_argument("--report", action="store_true", help="Generar reporte completo")
    
    args = parser.parse_args()
    
    if not any([args.check, args.create, args.analyze, args.report]):
        print("Uso: python add_development_indexes.py --check|--create|--analyze|--report")
        return
    
    print("🔍 Conectando a la base de datos...")
    print(f"📁 Database URL: {settings.DATABASE_URL.split('@')[0] if '@' in settings.DATABASE_URL else 'configured'}")
    
    try:
        indexer = DatabaseIndexer()
        
        with get_session() as session:
            if args.check:
                print("\n🔍 Verificando índices existentes...")
                missing = indexer.get_missing_indexes(session)
                if not missing:
                    print("✅ Todos los índices críticos ya existen")
                else:
                    print(f"❌ Faltan {len(missing)} índices críticos")
                    for index in missing:
                        print(f"   - {index['name']}: {index['description']}")
            
            elif args.create:
                print("\n🛠️  Creando índices faltantes...")
                success = indexer.create_missing_indexes(session)
                if success:
                    print("\n🎉 Todos los índices críticos están ahora creados")
                else:
                    print("\n⚠️  Algunos índices no pudieron crearse (ver errores arriba)")
            
            elif args.analyze:
                print("\n📊 Analizando rendimiento de queries...")
                indexer.analyze_query_performance(session)
            
            elif args.report:
                print("\n📋 Generando reporte completo...")
                report = indexer.generate_index_report(session)
                print("\n" + report)
                
                # Guardar reporte
                with open("database_indexes_report.txt", "w", encoding="utf-8") as f:
                    f.write(report)
                print("\n📄 Reporte guardado en: database_indexes_report.txt")
    
    except Exception as e:
        print(f"❌ Error conectando a la base de datos: {e}")
        print("💡 Asegúrate de que PostgreSQL esté corriendo y la DATABASE_URL sea correcta")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())