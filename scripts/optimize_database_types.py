#!/usr/bin/env python3
"""
Migra campos de tipo str a JSONB para mejorar performance y flexibilidad.
Resuelve el problema de almacenar JSON como string en lugar de tipo nativo.
"""

import json
import ast
from pathlib import Path
import sys
from typing import Dict, List, Any

# Añadir el directorio del proyecto al path de Python
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.db import get_session  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.models.base import Artist, Album, Track, User  # noqa: E402
from sqlalchemy import text, inspect  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402


class DatabaseTypeMigrator:
    def __init__(self):
        self.json_fields = [
            {
                'model': Artist,
                'table': 'artist',
                'fields': [
                    {'name': 'genres', 'description': 'Géneros musicales del artista'},
                    {'name': 'images', 'description': 'Imágenes del artista (URLs)'}
                ]
            },
            {
                'model': Album,
                'table': 'album',
                'fields': [
                    {'name': 'images', 'description': 'Imágenes del álbum (portadas)'}
                ]
            },
            {
                'model': Track,
                'table': 'track',
                'fields': [
                    {'name': 'genres', 'description': 'Géneros de la pista (heredados)'},
                    {'name': 'images', 'description': 'Imágenes relacionadas con la pista'}
                ]
            },
            {
                'model': User,
                'table': 'user',
                'fields': [
                    {'name': 'favorite_genres', 'description': 'Géneros favoritos del usuario'}
                ]
            }
        ]

    def check_current_types(self) -> Dict[str, Dict]:
        """Verifica los tipos actuales de las columnas."""
        with get_session() as session:
            inspector = inspect(session.bind)
            current_types = {}

            for model_info in self.json_fields:
                table_name = model_info['table']
                table_columns = inspector.get_columns(table_name)

                current_types[table_name] = {}
                for field_info in model_info['fields']:
                    field_name = field_info['name']

                    for column in table_columns:
                        if column['name'] == field_name:
                            current_type = column['type']
                            current_types[table_name][field_name] = {
                                'current_type': str(current_type),
                                'is_jsonb': 'JSONB' in str(current_type).upper(),
                                'needs_migration': 'JSONB' not in str(current_type).upper()
                            }
                            break

            return current_types

    def analyze_json_content(self, model_class: SQLModel, field_name: str, sample_size: int = 100) -> Dict:
        """Analiza el contenido JSON para validar migración."""
        try:
            with get_session() as session:
                # Obtener muestra de datos
                records = session.exec(
                    text(f"SELECT {field_name} FROM {model_class.__tablename__} WHERE {field_name} IS NOT NULL LIMIT {sample_size}")
                ).fetchall()

                if not records:
                    return {'status': 'no_data', 'message': 'No hay datos para analizar'}

                analysis = {
                    'total_sampled': len(records),
                    'valid_json': 0,
                    'invalid_json': 0,
                    'null_values': 0,
                    'string_values': 0,
                    'examples': []
                }

                for record in records:
                    value = record[0]

                    if value is None:
                        analysis['null_values'] += 1
                        continue

                    if not isinstance(value, str):
                        # Ya es tipo nativo, probablemente ya migrado
                        analysis['valid_json'] += 1
                        if len(analysis['examples']) < 3:
                            analysis['examples'].append({
                                'type': 'already_native',
                                'value': value
                            })
                        continue

                    analysis['string_values'] += 1

                    # Intentar parsear como JSON
                    try:
                        json.loads(value)
                        analysis['valid_json'] += 1
                        if len(analysis['examples']) < 3:
                            analysis['examples'].append({
                                'type': 'valid_json',
                                'value': value
                            })
                    except json.JSONDecodeError:
                        # Intentar con ast.literal_eval (Python literal)
                        try:
                            parsed = ast.literal_eval(value)
                            if isinstance(parsed, (dict, list)):
                                analysis['valid_json'] += 1
                                if len(analysis['examples']) < 3:
                                    analysis['examples'].append({
                                        'type': 'valid_python_literal',
                                        'value': value
                                    })
                            else:
                                analysis['invalid_json'] += 1
                        except (ValueError, SyntaxError):
                            analysis['invalid_json'] += 1
                            if len(analysis['examples']) < 3:
                                analysis['examples'].append({
                                    'type': 'invalid',
                                    'value': value
                                })

                return analysis

        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def generate_migration_sql(self, table_name: str, field_name: str) -> List[str]:
        """Genera SQL para migrar un campo a JSONB."""
        sql_statements = [
            f"-- Migration for {table_name}.{field_name} to JSONB",
            "BEGIN;",
            "-- First, backup any invalid JSON data",
            f"CREATE TEMPORARY TABLE {table_name}_{field_name}_backup AS",
            f"SELECT id, {field_name} FROM {table_name} WHERE {field_name} IS NOT NULL;",
            "",
            "-- Update NULL values for invalid JSON",
            f"UPDATE {table_name} SET {field_name} = NULL WHERE {field_name} IS NOT NULL AND",
            "({FIELD} NOT LIKE '{%' AND {FIELD} NOT LIKE '[%' AND {FIELD} NOT LIKE '{%')".replace(
                "{FIELD}", field_name
            ),
            "",
            "-- Alter column type to JSONB",
            f"ALTER TABLE {table_name} ALTER COLUMN {field_name} TYPE JSONB",
            "USING CASE",
            "  WHEN {FIELD} LIKE '{%' THEN NULL".replace("{FIELD}", field_name),
            "  WHEN {FIELD} LIKE '[%]' OR {FIELD} LIKE '{%}' THEN {FIELD}::jsonb".replace(
                "{FIELD}", field_name
            ),
            "  ELSE NULL",
            "END;",
            "",
            "COMMIT;"
        ]
        return sql_statements

    def safe_json_parse(self, value: Any) -> Any:
        """Parseo seguro de JSON con múltiples fallbacks."""
        if value is None:
            return None

        if not isinstance(value, str):
            return value

        # Intentar JSON parse primero
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass

        # Intentar Python literal (para comillas simples)
        try:
            parsed = ast.literal_eval(value)
            if isinstance(parsed, (dict, list, str, int, float, bool)):
                return parsed
        except (ValueError, SyntaxError):
            pass

        # Si todo falla, retornar string original
        return value

    def migrate_field(self, model_class: SQLModel, field_name: str, dry_run: bool = True) -> Dict:
        """Migra un campo específico a JSONB."""
        result = {
            'table': model_class.__tablename__,
            'field': field_name,
            'dry_run': dry_run,
            'records_processed': 0,
            'records_updated': 0,
            'errors': []
        }

        try:
            with get_session() as session:
                # Obtener todos los registros que necesitan migración
                records = session.exec(
                    text(f"SELECT id, {field_name} FROM {model_class.__tablename__} WHERE {field_name} IS NOT NULL")
                ).fetchall()

                result['records_processed'] = len(records)

                if dry_run:
                    result['message'] = f"DRY RUN: Se procesarían {len(records)} registros"
                    return result

                print(f"🔄 Migrando {len(records)} registros de {model_class.__tablename__}.{field_name}")

                for record in records:
                    try:
                        record_id = record[0]
                        raw_value = record[1]

                        # Parseo seguro a JSON
                        parsed_value = self.safe_json_parse(raw_value)

                        # Actualizar solo si el valor es diferente
                        if parsed_value != raw_value:
                            session.exec(
                                text(f"UPDATE {model_class.__tablename__} SET {field_name} = :value WHERE id = :id"),
                                {"value": parsed_value, "id": record_id}
                            )
                            result['records_updated'] += 1

                    except Exception as e:
                        result['errors'].append({
                            'record_id': record[0],
                            'error': str(e)
                        })

                if result['records_updated'] > 0:
                    session.commit()
                    print(f"✅ Actualizados {result['records_updated']} registros")

        except Exception as e:
            result['errors'].append({'general_error': str(e)})

        return result

    def generate_analysis_report(self) -> str:
        """Genera un reporte completo del análisis de tipos."""
        current_types = self.check_current_types()

        report = [
            "📊 ANÁLISIS DE TIPOS DE BASE DE DATOS",
            "=" * 80,
            f"\n📁 Base de datos: {settings.DATABASE_URL.split('@')[0] if '@' in settings.DATABASE_URL else 'Configured'}"
        ]

        migration_needed = False

        for model_info in self.json_fields:
            table_name = model_info['table']
            table_types = current_types.get(table_name, {})

            report.extend([
                f"\n📋 TABLA: {table_name.upper()}",
                "-" * 40
            ])

            for field_info in model_info['fields']:
                field_name = field_info['name']
                field_desc = field_info['description']
                field_type = table_types.get(field_name, {})

                current_type_str = field_type.get('current_type', 'UNKNOWN')
                is_jsonb = field_type.get('is_jsonb', False)
                needs_migration = field_type.get('needs_migration', False)

                if needs_migration:
                    migration_needed = True

                report.extend([
                    f"\n📄 Campo: {field_name}",
                    f"📝 Descripción: {field_desc}",
                    f"📊 Tipo actual: {current_type_str}",
                    f"✅ Ya es JSONB: {'SÍ' if is_jsonb else 'NO'}",
                    f"🔄 Necesita migración: {'SÍ - URGENTE' if needs_migration else 'NO'}"
                ])

                # Análisis de contenido
                if not is_jsonb:
                    model_class = model_info['model']
                    analysis = self.analyze_json_content(model_class, field_name)

                    if analysis.get('status') == 'error':
                        report.append(f"⚠️  Error analizando contenido: {analysis['message']}")
                    else:
                        report.extend([
                            f"📈 Muestreo analizado: {analysis['total_sampled']} registros",
                            f"✅ JSON válido: {analysis['valid_json']}",
                            f"❌ JSON inválido: {analysis['invalid_json']}",
                            f"📄 Valores string: {analysis['string_values']}"
                        ])

                        if analysis.get('examples'):
                            report.append("\n📋 Ejemplos de valores:")
                            for example in analysis['examples'][:3]:
                                report.append("   [{}] {}".format(example["type"], example["value"]))

        report.extend([
            "\n" + "=" * 80,
            "\n🎯 RESUMEN:",
            f"{'⚠️  SE DETECTÓ MIGRACIÓN URGENTE' if migration_needed else '✅ Todos los campos ya son JSONB'}",
            f"📊 Total campos analizados: {sum(len(mi['fields']) for mi in self.json_fields)}",
            f"🔄 Campos que necesitan migración: {sum(1 for mi in self.json_fields for field in mi['fields'] if current_types.get(mi['table'], {}).get(field['name'], {}).get('needs_migration', False))}"
        ])

        return "\n".join(report)

    def execute_all_migrations(self, dry_run: bool = True) -> Dict:
        """Ejecuta todas las migraciones necesarias."""
        current_types = self.check_current_types()
        migration_results = []

        for model_info in self.json_fields:
            table_name = model_info['table']
            table_types = current_types.get(table_name, {})

            for field_info in model_info['fields']:
                field_name = field_info['name']
                field_type = table_types.get(field_name, {})

                if field_type.get('needs_migration', False):
                    print(f"\n🔄 Procesando migración: {table_name}.{field_name}")

                    model_class = model_info['model']
                    result = self.migrate_field(model_class, field_name, dry_run)
                    migration_results.append(result)

        return {
            'dry_run': dry_run,
            'migrations': migration_results,
            'total_fields': len(migration_results),
            'successful_migrations': len([m for m in migration_results if not m['errors']]),
            'total_records_processed': sum(m['records_processed'] for m in migration_results),
            'total_records_updated': sum(m['records_updated'] for m in migration_results)
        }


def main():
    import argparse  # noqa: E402

    parser = argparse.ArgumentParser(description="Migración de tipos str a JSONB para optimización")
    parser.add_argument("--analyze", action="store_true", help="Analizar tipos actuales sin migrar")
    parser.add_argument("--migrate", action="store_true", help="Ejecutar migración de datos")
    parser.add_argument("--dry-run", action="store_true", help="Simular migración sin aplicar cambios")
    parser.add_argument("--report", action="store_true", help="Generar reporte completo")
    parser.add_argument("--field", help="Migrar campo específico (tabla.campo)")

    args = parser.parse_args()

    if not any([args.analyze, args.migrate, args.report]):
        print("Uso: python optimize_database_types.py --analyze|--migrate|--report [--dry-run] [--field tabla.campo]")
        return

    print("🔍 Analizando configuración de base de datos...")
    migrator = DatabaseTypeMigrator()

    try:
        if args.report or args.analyze:
            print("\n📊 Generando análisis de tipos...")
            report = migrator.generate_analysis_report()
            print("\n" + report)

            if args.report:
                with open("database_types_analysis.txt", "w", encoding="utf-8") as f:
                    f.write(report)
                print("\n📄 Reporte guardado en: database_types_analysis.txt")

        elif args.migrate:
            print(f"\n🔄 {'SIMULANDO' if args.dry_run else 'EJECUTANDO'} migración de datos...")

            if args.field:
                # Migrar campo específico
                print(f"🎯 Campo objetivo: {args.field}")
                # TODO: Implementar migración específica
                print("⚠️  Migración específica por campo no implementada aún")
            else:
                # Migrar todos los campos necesarios
                results = migrator.execute_all_migrations(dry_run=args.dry_run)

                print(f"\n📊 RESULTADOS {'DE LA SIMULACIÓN' if args.dry_run else 'DE LA MIGRACIÓN'}:")
                print(f"   📁 Campos procesados: {results['total_fields']}")
                print(f"   📝 Migraciones exitosas: {results['successful_migrations']}")
                print(f"   📈 Registros procesados: {results['total_records_processed']}")
                print(f"   ✅ Registros actualizados: {results['total_records_updated']}")

                if results['dry_run']:
                    print("\n🔍 Este fue un DRY RUN. Para ejecutar la migración real:")
                    print("   python optimize_database_types.py --migrate")
                else:
                    print("\n🎉 ¡Migración completada!")

    except Exception as e:
        print(f"❌ Error durante la operación: {e}")
        print("💡 Asegúrate de que PostgreSQL esté corriendo y DATABASE_URL sea correcta")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
