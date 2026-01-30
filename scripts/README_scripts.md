# Scripts de Desarrollo y Mantenimiento

Este directorio contiene scripts para facilitar el desarrollo y mantenimiento de Audio2.

## Scripts Disponibles

### dev_setup.py
Configura el entorno de desarrollo con datos de prueba.
```bash
# Configura BD de desarrollo y crea usuario de prueba
python scripts/dev_setup.py
```

### reset_dev_db.py
Limpia y reinicia la base de datos de desarrollo.
```bash
# CUIDADO: Borra todos los datos
python scripts/reset_dev_db.py
```

### add_development_indexes.py
Añade índices críticos para mejorar el rendimiento durante desarrollo.
```bash
# Añade índices sin bloquear la BD
python scripts/add_development_indexes.py
```

### fix_eval_usage.py
Busca y reemplaza todas las ocurrencias peligrosas de `eval()` en el código.
```bash
# Busca eval() en el códigobase
python scripts/fix_eval_usage.py --scan
# Aplica arreglos automáticamente
python scripts/fix_eval_usage.py --fix
```

### optimize_database_types.py
Migra campos de tipo `str` a `JSONB` para mejorar performance.
```bash
# Analiza qué campos necesitan migración
python scripts/optimize_database_types.py --analyze
# Aplica migración
python scripts/optimize_database_types.py --migrate
```

### split_monolithic_files.py
Divide archivos grandes en módulos más pequeños y manejables.
```bash
# Analiza archivos que necesitan división
python scripts/split_monolithic_files.py --analyze
# Realiza la división automática
python scripts/split_monolithic_files.py --split
```

### generate_error_handler.py
Genera sistema de manejo de errores centralizado.
```bash
# Crea excepciones personalizadas y handlers
python scripts/generate_error_handler.py
```

### setup_frontend_optimization.py
Optimiza la configuración del frontend para desarrollo.
```bash
# Configura vite.config.ts con optimizaciones
python scripts/setup_frontend_optimization.py
```

## Uso Recomendado

### Configuración Inicial de Desarrollo
```bash
# 1. Configurar entorno
python scripts/dev_setup.py

# 2. Optimizar BD
python scripts/add_development_indexes.py

# 3. Optimizar frontend
python scripts/setup_frontend_optimization.py
```

### Mantenimiento Periódico
```bash
# Semanalmente
python scripts/fix_eval_usage.py --scan
python scripts/optimize_database_types.py --analyze

# Mensualmente
python scripts/split_monolithic_files.py --analyze
```

## Notas Importantes

- Estos scripts están diseñados para **entorno de desarrollo**
- Siempre haz backup antes de ejecutar scripts destructivos
- Algunos scripts requieren que el servidor backend esté detenido
- Revisa el output de cada script para verificar que se ejecutó correctamente

## Scripts Futuros (Planificados)

- [ ] `backup_dev_data.py` - Backup automático de datos de desarrollo
- [ ] `monitor_performance.py` - Monitoreo de rendimiento en desarrollo
- [ ] `generate_test_fixtures.py` - Generación de datos de prueba realistas
- [ ] `validate_types.py` - Validación de tipos TypeScript/Python