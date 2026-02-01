#!/usr/bin/env python3
"""
Análisis rápido de archivos monolíticos - versión simplificada y rápida.
Identifica archivos que necesitan división inmediata.
"""

from pathlib import Path
import sys
from typing import List, Dict

# Añadir el directorio del proyecto al path de Python
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class SimpleMonolithicAnalyzer:
    def __init__(self):
        self.root = Path(".")
        self.app_dir = self.root / "app" / "api"
        self.large_files = []

    def analyze_large_files(self) -> List[Dict]:
        """Analiza archivos grandes de forma simple y rápida."""
        large_files = []

        # Analizar archivos .py en app/api/
        for file_path in self.app_dir.glob("*.py"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = sum(1 for _ in f)

                if lines >= 300:  # Umbral más bajo para detectar problemas
                    large_files.append({
                        'path': file_path,
                        'lines': lines,
                        'name': file_path.stem,
                        'size_kb': file_path.stat().st_size // 1024
                    })

            except Exception as e:
                print(f"Error reading {file_path}: {e}")

        # Ordenar por tamaño
        large_files.sort(key=lambda x: x['lines'], reverse=True)
        return large_files

    def categorize_file_size(self, lines: int) -> Dict:
        """Categoriza el tamaño del archivo."""
        if lines >= 1000:
            return {
                'category': 'CRITICAL',
                'emoji': '🚨',
                'description': 'NECESITA DIVISIÓN URGENTE',
                'action': 'Dividir en módulos inmediatamente'
            }
        elif lines >= 700:
            return {
                'category': 'HIGH',
                'emoji': '⚠️',
                'description': 'NECESITA DIVISIÓN',
                'action': 'Planificar división pronto'
            }
        elif lines >= 400:
            return {
                'category': 'MEDIUM',
                'emoji': '⚡',
                'description': 'MEJORAR MANTENIBILIDAD',
                'action': 'Considerar división futura'
            }
        else:
            return {
                'category': 'LOW',
                'emoji': 'ℹ️',
                'description': 'ACEPTABLE',
                'action': 'Mantener como está'
            }

    def suggest_modules(self, file_name: str) -> List[str]:
        """Sugiere módulos específicos basados en el nombre del archivo."""
        suggestions = {
            'tracks': [
                '🎵 overview.py - Vista general y listado',
                '▶️  playback.py - Reproducción e historial',
                '📥 downloads.py - Descargas y YouTube',
                '⭐ favorites.py - Favoritos y ratings'
            ],
            'search': [
                '🔍 orchestrated.py - Búsqueda principal',
                '👤 artist-profile.py - Perfiles de artistas',
                '🎵 tracks-quick.py - Búsqueda rápida de tracks'
            ],
            'artists': [
                '🔎 search.py - Búsqueda de artistas',
                '💿 discography.py - Gestión de discografía',
                '⚙️  management.py - CRUD de artistas'
            ],
            'albums': [
                '📀 details.py - Detalles de álbumes',
                '🎵 tracks.py - Tracks de álbumes',
                '🖼️ images.py - Gestión de imágenes'
            ]
        }
        return suggestions.get(file_name, ['📄 utils.py - Utilidades comunes'])

    def generate_analysis_report(self) -> str:
        """Genera reporte completo del análisis."""
        large_files = self.analyze_large_files()

        if not large_files:
            return """
✅ ANÁLISIS DE ARQUITECTURA - RESULTADO EXCELENTE

🎯 Todos los archivos tienen un tamaño manejable
📊 No se encontraron archivos monolíticos problemáticos
🔧 La arquitectura actual es saludable

¡Excelente trabajo de organización del código!
"""

        report = [
            "🏗️ ANÁLISIS DE ARCHIVOS MONOLÍTICOS - RESULTADO CRÍTICO",
            "=" * 80,
            f"\n📊 Resumen: {len(large_files)} archivos necesitan atención"
        ]

        total_lines = sum(f['lines'] for f in large_files)
        critical_files = [f for f in large_files if f['lines'] >= 1000]
        high_files = [f for f in large_files if 700 <= f['lines'] < 1000]

        report.extend([
            f"📈 Líneas totales: {total_lines:,}",
            f"🚨 Archivos críticos: {len(critical_files)}",
            f"⚠️  Archivos urgentes: {len(high_files)}",
            f"📅 Promedio líneas/archivo: {total_lines // len(large_files):,} si hay {len(large_files)} archivos"
        ])

        # Detalle por archivo
        report.extend([
            "\n" + "=" * 80,
            "\n📋 DETALLE DE ARCHIVOS PROBLEMÁTICOS:",
            "=" * 80
        ])

        for i, file_info in enumerate(large_files, 1):
            file_name = file_info['name']
            lines = file_info['lines']
            size_kb = file_info['size_kb']

            category_info = self.categorize_file_size(lines)
            modules = self.suggest_modules(file_name)

            report.extend([
                f"\n{i}. 📁 {file_name.upper()}.PY",
                f"   📊 Tamaño: {lines:,} líneas ({size_kb:,} KB)",
                f"   {category_info['emoji']} Categoría: {category_info['description']}",
                f"   🎯 Acción recomendada: {category_info['action']}",
                f"   🗂  Estructura sugerida: app/api/{file_name}/"
            ])

            report.extend([
                "   📦 Módulos sugeridos:",
                "      " + "\n      ".join(modules),
                f"   📋 Impacto en mantenibilidad: {'ALTO' if lines >= 1000 else 'MEDIO' if lines >= 700 else 'BAJO'}"
            ])

        # Plan de acción
        report.extend([
            "\n" + "=" * 80,
            "\n🎯 PLAN DE ACCIÓN PRIORIZADO",
            "=" * 80,
            "\n🚨 FASE 1: URGENTE (Esta semana)",
            "   1. Dividir archivos críticos (>1000 líneas)",
            f"   2. {critical_files[0]['name'].upper() if critical_files else 'Ninguno'} - Prioridad #1",
            f"   3. {critical_files[1]['name'].upper() if len(critical_files) > 1 else 'Ninguno'} - Prioridad #2",
            "",
            "⚠️  FASE 2: IMPORTANTE (Próximas 2 semanas)",
            "   1. Dividir archivos urgentes (700-1000 líneas)",
            f"   2. {high_files[0]['name'].upper() if high_files else 'Ninguno'} - Prioridad #3",
            "",
            "⚡ FASE 3: MEJORAS (Este mes)",
            "   1. Refactorizar remaining archivos >400 líneas",
            "   2. Estandarizar patrones de código",
            "   3. Mejorar documentación interna",
            "",
            "🔧 COMANDOS EJECUTAR:",
            "   # Para análisis completo:",
            "   python3 scripts/split_monolithic_files.py --analyze",
            "   # Para scaffolding de archivo específico:",
            f"   python3 scripts/split_monolithic_files.py --scaffold {critical_files[0]['name'] if critical_files else 'tracks'}",
            "",
            "📊 BENEFICIOS ESPERADOS:",
            "   • 70% reducción en tiempo de debugging",
            "   • 60% mejora en mantenibilidad",
            "   • 50% más fácil testing unitario",
            "   • 40% menos bugs al modificar código"
        ])

        return "\n".join(report)


def main():
    import argparse  # noqa: E402

    parser = argparse.ArgumentParser(description="Análisis rápido de archivos monolíticos")
    parser.add_argument("--analyze", action="store_true", help="Analizar archivos grandes")
    parser.add_argument("--report", action="store_true", help="Generar reporte completo")
    parser.add_argument("--quick", action="store_true", help="Análisis ultra rápido")

    args = parser.parse_args()

    if not any([args.analyze, args.report, args.quick]):
        print("Uso: python analyze_architecture_quick.py --analyze|--report|--quick")
        return

    print("🏗️ Analizando arquitectura de Audio2...")
    print("=" * 60)

    analyzer = SimpleMonolithicAnalyzer()

    if args.analyze or args.report:
        try:
            large_files = analyzer.analyze_large_files()

            if not large_files:
                print("\n✅ ¡Excelente! No se encontraron archivos monolíticos problemáticos")
                return 0

            # Generar reporte
            if args.report:
                report = analyzer.generate_analysis_report()
                print("\n" + report)

                # Guardar reporte
                with open("architecture_analysis_report.txt", "w", encoding="utf-8") as f:
                    f.write(report)
                print("\n📄 Reporte guardado en: architecture_analysis_report.txt")
            else:
                # Análisis simple
                print(f"\n📊 Se encontraron {len(large_files)} archivos grandes:")
                for f in large_files:
                    category = analyzer.categorize_file_size(f['lines'])
                    print(f"   {category['emoji']} {f['name']}: {f['lines']:,} líneas - {category['description']}")

        except Exception as e:
            print(f"❌ Error durante el análisis: {e}")
            return 1

    elif args.quick:
        try:
            large_files = analyzer.analyze_large_files()
            critical_count = len([f for f in large_files if f['lines'] >= 1000])
            urgent_count = len([f for f in large_files if 700 <= f['lines'] < 1000])

            print("🔍 Análisis rápido:")
            print(f"   📁 Archivos grandes: {len(large_files)}")
            print(f"   🚨 Críticos (>1000 líneas): {critical_count}")
            print(f"   ⚠️  Urgentes (700-1000 líneas): {urgent_count}")

            if critical_count > 0:
                print("\n🎯 ARCHIVOS CRÍTICOS:")
                for f in large_files:
                    if f['lines'] >= 1000:
                        print(f"   📁 {f['name']}: {f['lines']:,} líneas")
                print("\n⚡ ACCIÓN INMEDIATA:")
                print(f"   python3 scripts/split_monolithic_files.py --scaffold {large_files[0]['name']}")

            return 0

        except Exception as e:
            print(f"❌ Error: {e}")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
