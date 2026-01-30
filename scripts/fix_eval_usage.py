#!/usr/bin/env python3
"""
Busca y reemplaza todas las ocurrencias peligrosas de eval() en el códigobase.
Este script soluciona la vulnerabilidad CRÍTICA de RCE.
"""

import os
import re
import ast
from pathlib import Path
from typing import List, Tuple

class EvalFixer:
    def __init__(self, root_dir: str = "."):
        self.root = Path(root_dir)
        self.python_files = []
        self.issues_found = []
        
    def find_python_files(self) -> List[Path]:
        """Encuentra todos los archivos Python relevantes."""
        patterns = [
            "**/*.py",
            "**/app/**/*.py",
            "**/scripts/**/*.py"
        ]
        
        files = []
        for pattern in patterns:
            files.extend(self.root.glob(pattern))
        
        # Excluir directorios no deseados
        excluded_dirs = {"venv", "__pycache__", ".git", "node_modules"}
        filtered_files = []
        for file in files:
            if not any(excluded in str(file) for excluded in excluded_dirs):
                filtered_files.append(file)
        
        self.python_files = sorted(set(filtered_files))
        return self.python_files
    
    def scan_for_eval(self) -> List[Tuple[Path, int, str]]:
        """Escanea en busca de eval() peligroso."""
        eval_patterns = [
            r'eval\s*\(',  # eval(
            r'\.eval\s*\(',  # .eval(
            r'eval\s*\(',  # eval con diferentes espaciados
        ]
        
        issues = []
        
        for file_path in self.python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')
                    
                    for line_num, line in enumerate(lines, 1):
                        for pattern in eval_patterns:
                            if re.search(pattern, line):
                                issues.append((file_path, line_num, line.strip()))
                                
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
        
        return issues
    
    def suggest_fix(self, original_line: str) -> str:
        """Sugiere el reemplazo seguro para eval()."""
        # Detectar patrones comunes
        if "json.loads" in original_line:
            return original_line  # Ya está arreglado
        
        if "ast.literal_eval" in original_line:
            return original_line  # Ya está arreglado
        
        # Sugerir reemplazo basado en contexto
        if "genres" in original_line.lower():
            return original_line.replace("eval(", "json.loads(")
        
        if "images" in original_line.lower():
            return original_line.replace("eval(", "json.loads(")
        
        # Reemplazo genérico
        return original_line.replace("eval(", "json.loads(")
    
    def generate_report(self, issues: List[Tuple[Path, int, str]]) -> str:
        """Genera un reporte detallado de los problemas encontrados."""
        if not issues:
            return "✅ No se encontraron usos peligrosos de eval()"
        
        report = ["🚨 CRITICAL: Usos peligrosos de eval() encontrados\n"]
        report.append("=" * 80)
        
        for file_path, line_num, line_content in issues:
            rel_path = file_path.relative_to(self.root)
            suggested_fix = self.suggest_fix(line_content)
            
            report.append(f"\n📁 Archivo: {rel_path}:{line_num}")
            report.append(f"❌ Línea original: {line_content}")
            report.append(f"✅ Sugerencia:    {suggested_fix}")
            report.append("-" * 40)
        
        report.append(f"\n📊 Resumen: {len(issues)} usos peligrosos de eval() encontrados")
        report.append("⚠️  Prioridad: CRÍTICA - Aplicar inmediatamente")
        
        return "\n".join(report)
    
    def apply_fixes(self, issues: List[Tuple[Path, int, str]], dry_run: bool = True) -> None:
        """Aplica los arreglos automáticamente."""
        if dry_run:
            print("\n🔍 MODO DRY RUN - No se realizarán cambios")
            return
        
        print("\n🔧 Aplicando arreglos...")
        
        fixed_files = set()
        
        for file_path, line_num, original_line in issues:
            if file_path in fixed_files:
                continue  # Ya arreglado este archivo
                
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                # Reemplazar la línea específica
                fixed_line = self.suggest_fix(original_line)
                lines[line_num - 1] = fixed_line + '\n'
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.writelines(lines)
                
                fixed_files.add(file_path)
                rel_path = file_path.relative_to(self.root)
                print(f"✅ Arreglado: {rel_path}:{line_num}")
                
            except Exception as e:
                rel_path = file_path.relative_to(self.root)
                print(f"❌ Error arreglando {rel_path}:{line_num}: {e}")
        
        if fixed_files:
            print(f"\n🎉 Se arreglaron {len(fixed_files)} archivos exitosamente")
        else:
            print("\nℹ️  No se realizaron arreglos")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Busca y arregla usos peligrosos de eval()")
    parser.add_argument("--scan", action="store_true", help="Solo escanear, no arreglar")
    parser.add_argument("--fix", action="store_true", help="Aplicar arreglos automáticamente")
    parser.add_argument("--root", default=".", help="Directorio raíz del proyecto")
    
    args = parser.parse_args()
    
    if not args.scan and not args.fix:
        print("Uso: python fix_eval_usage.py --scan|--fix [--root /ruta/del/proyecto]")
        return
    
    print("🔍 Buscando usos peligrosos de eval()...")
    fixer = EvalFixer(args.root)
    
    # Encontrar archivos Python
    files = fixer.find_python_files()
    print(f"📁 Analizando {len(files)} archivos Python...")
    
    # Escanear problemas
    issues = fixer.scan_for_eval()
    
    # Generar reporte
    report = fixer.generate_report(issues)
    print("\n" + report)
    
    # Guardar reporte en archivo
    with open("eval_security_report.txt", "w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"\n📄 Reporte guardado en: eval_security_report.txt")
    
    # Aplicar arreglos si se solicita
    if args.fix and issues:
        print("\n⚠️  ESTÁS A PUNTO DE MODIFICAR ARCHIVOS DE CÓDIGO")
        print("   Asegúrate de tener backup del repositorio")
        confirm = input("   ¿Continuar con el arregloo? (s/N): ")
        
        if confirm.lower() in ['s', 'si', 'yes', 'y']:
            fixer.apply_fixes(issues, dry_run=False)
        else:
            print("❌ Operación cancelada")
    elif args.fix:
        print("\nℹ️  No se encontraron problemas para arreglar")

if __name__ == "__main__":
    main()