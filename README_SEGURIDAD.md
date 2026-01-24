# Audio2 - Security Audit & Improvements

## Resumen del Proyecto

Audio2 es una aplicación personal de streaming de música construida con:
- **Backend**: FastAPI (Python) + PostgreSQL
- **Frontend**: React/TypeScript + Vite
- **Integraciones**: Spotify, Last.fm, YouTube Data API

## Auditoría de Seguridad (Enero 2025)

### Problemas Críticos Encontrados

| Prioridad | Problema | Estado | Archivo |
|-----------|----------|--------|---------|
| CRÍTICO | Credenciales expuestas en .env | ⏳ Pendiente | `.env` |
| ALTO | user_id por defecto = 1 sin auth | ⏳ Pendiente | `app/api/tracks.py` |
| ALTO | Sin rate limiting en auth | ⏳ Pendiente | `app/main.py` |
| MEDIUM | JWT token expira en 24h | ⏳ Pendiente | `app/core/security.py` |
| MEDIUM | Sin validación size en imágenes | ⏳ Pendiente | `app/api/images.py` |
| LOW | Bug en optional chaining | ⏳ Pendiente | `frontend/src/components/AuthWrapper.tsx` |
| LOW | Múltiples sesiones por request | ⏳ Pendiente | `app/api/tracks.py` |

## Historial de Commits

| Commit | Descripción |
|--------|-------------|
| `abac834` | Snapshot inicial antes de correcciones de seguridad |
| `86d90cc` | Snapshot anterior (referencia de restauración) |
| `24d49f6` | feat: simplify playlist controls |
| `a42c22e` | feat: add shuffle toggle |

## Tareas Planificadas

### Fase 1: Seguridad Crítica
- [ ] Rotar credenciales expuestas en .env
- [ ] Corregir user_id por defecto en tracks.py
- [ ] Agregar rate limiting a auth endpoints

### Fase 2: Mejoras Medias
- [ ] Validar tamaño en proxy de imágenes
- [ ] Reducir JWT token expiration
- [ ] Agregar índices de base de datos

### Fase 3: Correcciones Menores
- [ ] Corregir bug en AuthWrapper.tsx
- [ ] Mejorar manejo de sesiones

## Advertencia

Este documento se creó para mantener un registro de los cambios realizados durante la auditoría de seguridad. Si el código queda en un estado inservible:
1. Consultar `AGENTS.md` para entender el flujo de trabajo
2. El commit `86d90cc` contiene un estado funcional conocido
3. Las credenciales expuestas deben ser rotadas manualmente

## Documentación Relacionada

- `CLAUDE.md` - Guidelines para Claude Code
- `AGENTS.md` - Registro completo de decisiones y hallazgos
- `DEBUG_INSTRUCTIONS.md` - Instrucciones de debug
- `NEW_TOKEN_INSTRUCTIONS.md` - Instrucciones para nuevas credenciales
