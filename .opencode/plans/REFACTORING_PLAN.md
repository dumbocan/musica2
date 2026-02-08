# Plan de Refactorización Audio2

**Versión:** 1.0  
**Fecha:** 2024-02-08  
**Estado:** En planificación - FASE 1 pendiente  

---

## Resumen Ejecutivo

Este documento detalla el plan completo para refactorizar Audio2, enfocándose en:
1. Solucionar bug crítico de eliminación en playlists
2. Unificar sistema de tracks con funcionalidades de lists
3. Implementar búsqueda DB-First con expansión automática completa
4. Sistema de limpieza de datos no utilizados (6 meses)

---

## FASE 1: Arreglar BUG de Eliminación en Playlists

### Estado: 🔴 PENDIENTE (Prioridad #1)

### Descripción del Problema
Al eliminar una canción de una playlist, el frontend solo actualiza el estado local (UI) pero no verifica que realmente se eliminó de la base de datos. Al recargar la página, la canción vuelve a aparecer.

### Causa Raíz
1. Backend: Posible problema con `session.commit()` en `remove_track_from_playlist`
2. Frontend: No recarga la lista tras eliminar para verificar sincronización

### Archivos a Modificar

#### Backend
- `app/crud.py` línea 853: `remove_track_from_playlist()`
  - Agregar logging de éxito/error
  - Verificar que `session.commit()` ejecuta correctamente
  - Retornar información más detallada

#### Frontend  
- `frontend/src/pages/PlaylistsPage.tsx` línea 153-164: `handleRemoveTrack`
  - Recargar playlist desde servidor tras eliminar
  - Mejorar manejo de errores
  - Feedback visual al usuario

### Criterios de Éxito
- [ ] Al eliminar una canción, muestra mensaje de éxito
- [ ] Al recargar la página (F5), la canción NO vuelve a aparecer
- [ ] Si hay error en BD, el usuario ve mensaje de error claro
- [ ] La UI se sincroniza con el estado real de la BD

### Tiempo Estimado: 1.5 horas

---

## FASE 2: Unificar Lists y Tracks

### Estado: 🟡 PENDIENTE

### Descripción
Actualmente existen dos sistemas paralelos:
- **Tracks** (`/tracks/overview`): Lista paginada completa con búsqueda y filtros
- **Lists** (`/lists/overview`): Tarjetas curadas (favoritos, top año, descargados, etc.)

Lists es modal/emergente, Tracks es página completa. Pero hay duplicación de lógica.

### Solución
Extender `/tracks/overview` para incluir todas las funcionalidades de Lists:

#### Nuevos Parámetros para `/tracks/overview`

```
GET /tracks/overview
  ?filter=favorites          (ya existe)
  &filter=downloaded         (ya existe) 
  &filter=with-link          (ya existe)
  &filter=top-year           ← NUEVO: Mejores del último año
  &filter=genre-suggestions  ← NUEVO: Por géneros similares
  &filter=recently-played    ← NUEVO: Últimas reproducidas
  
  &sort=plays                ← NUEVO: Por número de reproducciones
  &sort=rating               ← NUEVO: Por valoración usuario
  &sort=recency              ← NUEVO: Por última reproducción
  &sort=added                ← NUEVO: Por fecha de adición
  
  &artist_id={id}            ← NUEVO: Discografía específica
```

### Archivos a Modificar

#### Backend
1. `app/api/tracks.py`:
   - Agregar funciones de lists.py (730 líneas)
   - Implementar nuevos filtros
   - Mantener formato de respuesta existente para compatibilidad

2. `app/api/lists.py`:
   - **ELIMINAR** tras migrar funcionalidad

3. `app/crud.py`:
   - Agregar funciones auxiliares para nuevos filtros

#### Frontend
1. `frontend/src/lib/api.ts`:
   - Actualizar llamadas para usar `/tracks/overview` en lugar de `/lists/overview`
   
2. `frontend/src/components/ListsModal.tsx` (renombrar desde ListsPage):
   - Usar nuevo endpoint unificado
   - Mantener UI de tarjetas pero con datos de tracks

### Criterios de Éxito
- [ ] `/tracks/overview` devuelve todas las listas curadas que tenía `/lists/overview`
- [ ] Lists modal funciona igual pero usa endpoint unificado
- [ ] Se elimina archivo `lists.py` sin perder funcionalidad
- [ ] Reducción de ~700 líneas de código duplicado

### Tiempo Estimado: 7 horas

---

## FASE 3: Búsqueda DB-First con Expansión Automática

### Estado: 🟢 PENDIENTE

### Descripción
Al buscar una canción, el sistema debe:
1. Buscar primero en BD local
2. Si no existe, buscar en APIs externas (Spotify, Last.fm)
3. Guardar automáticamente: artista + biografía + 10 artistas similares + discografía completa + imágenes
4. Todo debe quedar en BD para uso offline futuro
5. El usuario puede añadir a playlist/favoritos inmediatamente

### Arquitectura

```
Usuario busca "Imagine"
         ↓
1. ¿En BD local? 
   Sí → Devolver inmediatamente
   No → Continuar
         ↓
2. Buscar en Spotify API
   → Artista: John Lennon
   → Track: Imagine
   → Álbum: Imagine (1971)
         ↓
3. Guardar en BD (síncrono, rápido):
   - Artista principal
   - Track buscado
   - Álbum
         ↓
4. Devolver respuesta al usuario
   (El usuario ya puede usar la canción)
         ↓
5. Procesar en BACKGROUND:
   a) Buscar 10 artistas similares (Last.fm)
   b) Para cada artista similar:
      - Guardar artista
      - Descargar discografía completa
   c) Descargar imágenes
         ↓
6. Notificar progreso (opcional):
   "Guardando biblioteca... 3/10 artistas"
```

### Archivos Nuevos

1. `app/services/search_expansion.py`:
   - `expand_search_results(query, user_id)` - Orquestador principal
   - `save_artist_complete(artist_data)` - Guarda artista + metadatos
   - `save_discography(artist_id, spotify_id)` - Guarda todos los álbumes
   - `find_similar_artists(artist_name, limit=10)` - Usa Last.fm
   - `download_artist_images(artist_id)` - Guarda imágenes en storage

2. `app/core/background_tasks.py`:
   - Gestión de tareas asíncronas
   - Cola de procesamiento
   - Estado de progreso

3. `app/api/search.py` (modificar):
   - Nuevo endpoint: `POST /search/unified`
   - Acepta parámetro `?expand=true` para expansión completa
   - Retorna inmediatamente + task_id para seguimiento
   
4. `app/api/tasks.py` (nuevo):
   - `GET /tasks/{task_id}/status` - Ver progreso de expansión

### Archivos a Modificar

#### Backend
1. `app/models/base.py`:
   - Agregar campos de tracking: `last_accessed_at`, `access_count`
   - Agregar campo `expansion_status` para saber si un artista está completo

2. `app/api/tracks.py`:
   - Modificar endpoints de reproducción para actualizar `last_accessed_at`

3. `app/api/artists.py`:
   - Agregar endpoint `POST /artists/{id}/expand` - Fuerza expansión manual

#### Frontend
1. `frontend/src/pages/SearchPage.tsx`:
   - Nuevo flujo de búsqueda
   - Barra de progreso mientras expande
   - Botones habilitados inmediatamente (porque todo está en BD)

2. `frontend/src/lib/api.ts`:
   - Nueva función `searchUnified(query, expand=true)`
   - Polling de estado de expansión

### Criterios de Éxito
- [ ] Búsqueda devuelve resultados en < 2 segundos (desde BD)
- [ ] Si no está en BD, busca en APIs y guarda todo
- [ ] Usuario puede añadir a playlist inmediatamente
- [ ] Expansión completa sucede en background sin bloquear
- [ ] Las imágenes se descargan y se guardan en storage
- [ ] Biografías de Last.fm se guardan en BD

### Tiempo Estimado: 12 horas

---

## FASE 4: Sistema de Limpieza (Olvidar Datos)

### Estado: 🟢 PENDIENTE

### Descripción
Después de 6 meses sin acceder a un artista/canción, ofrecer al usuario la opción de eliminar esos datos para liberar espacio (imágenes y música descargada).

### Reglas de Negocio

**NO SE ELIMINA NUNCA:**
- Canciones marcadas como favoritas
- Canciones en playlists del usuario
- Canciones con más de 5 reproducciones
- Artistas favoritos

**SÍ SE PUEDE ELIMINAR:**
- Artistas no favoritos sin acceso en 6 meses
- Canciones no favoritas, no en playlists, con < 5 reproducciones
- Imágenes asociadas a entidades eliminadas
- Archivos de música descargada de tracks eliminados

**SIEMPRE PREGUNTAR ANTES:**
- Script interactivo que muestre qué se va a borrar
- Requerir confirmación explícita (escribir "ELIMINAR")
- Backup opcional antes de borrar

### Tracking de Uso

Cada operación actualiza `last_accessed_at`:

```python
# En creación:
artist.last_accessed_at = utc_now()

# En búsqueda:
if artist:
    artist.last_accessed_at = utc_now()
    artist.access_count += 1
    
# En reproducción:
track.last_accessed_at = utc_now()
track.access_count += 1
```

### Archivos Nuevos

1. `scripts/cleanup_unused_data.py`:
   ```python
   def find_unused_data(since_days=180):
       """Encuentra artistas/tracks sin uso en X días"""
       
   def calculate_storage_impact(artists, tracks):
       """Calcula MB a liberar en imágenes y música"""
       
   def interactive_cleanup():
       """Script interactivo con confirmación"""
       # Muestra lista detallada
       # Pide confirmación
       # Elimina con opción de backup
   ```

2. `app/core/cleanup_service.py`:
   - Lógica de negocio para determinar qué se puede borrar
   - Verificación de restricciones (favoritos, playlists, etc.)
   - Eliminación segura en orden correcto

3. `app/api/admin.py` (nuevo endpoint):
   - `GET /admin/cleanup/preview` - Ver qué se eliminaría
   - `POST /admin/cleanup/execute` - Ejecutar limpieza
   - Requiere autenticación de administrador

### Archivos a Modificar

#### Backend
1. `app/models/base.py`:
   - Agregar a Artist: `last_accessed_at`, `access_count`, `is_expansion_complete`
   - Agregar a Track: `last_accessed_at`, `access_count`
   - Agregar a Album: `last_accessed_at`

2. `app/api/tracks.py`:
   - Modificar `POST /tracks/play/{id}` para actualizar tracking

3. `app/api/artists.py`:
   - Modificar `GET /artists/{id}` para actualizar tracking

4. `app/api/search.py`:
   - Actualizar tracking cuando se busca y encuentra

#### Frontend
1. `frontend/src/pages/SettingsPage.tsx`:
   - Nueva sección "Mantenimiento"
   - Botón "Ver datos sin usar"
   - Botón "Limpiar biblioteca" (con confirmación)
   - Mostrar espacio estimado a liberar

### Criterios de Éxito
- [ ] Toda creación/búsqueda/reproducción actualiza `last_accessed_at`
- [ ] Script muestra claramente qué se eliminaría
- [ ] Requiere confirmación explícita antes de borrar
- [ ] NO elimina favoritos ni canciones en playlists
- [ ] Elimina imágenes asociadas de storage/images/
- [ ] Elimina archivos de música de downloads/ (opcional)
- [ ] Crea backup antes de eliminar (opcional)

### Tiempo Estimado: 6 horas

---

## Cronograma de Implementación

### Semana 1
- **Día 1-2:** FASE 1 - Fix bug playlists (1.5h)
- **Día 3-7:** FASE 2 - Unificar lists/tracks (7h)

### Semana 2
- **Día 1-5:** FASE 3 - Búsqueda DB-First (12h)

### Semana 3
- **Día 1-3:** FASE 4 - Sistema de limpieza (6h)
- **Día 4-5:** Testing y refinamiento

---

## Checklist de Pre-Implementación

Antes de empezar cada fase:

- [ ] Backend está corriendo (`uvicorn` activo)
- [ ] Frontend está corriendo (`npm run dev`)
- [ ] Base de datos accesible (PostgreSQL activo)
- [ ] Backup de base de datos creado (por seguridad)
- [ ] Rama de git creada para la fase (ej: `fix/playlist-deletion`)

---

## Notas Importantes

### Sobre Lists vs Tracks
- Lists es modal (ventana emergente)
- Tracks es página completa
- Ambos pueden coexistir pero usar el mismo endpoint backend
- La UI de tarjetas (Lists) consume datos de `/tracks/overview` con filtros especiales

### Sobre Expansión Automática
- Todo se guarda automáticamente para tener BD completa
- El objetivo es nunca depender de APIs externas
- La primera búsqueda tarda más (llena la BD)
- Búsquedas siguientes son instantáneas (desde BD)
- El usuario puede desactivar expansión si quiere (configurable)

### Sobre Limpieza
- Script interactivo, no automático
- Siempre protege datos importantes (favoritos, playlists)
- Pregunta antes de eliminar archivos de música descargada
- Opcional: comprimir en lugar de eliminar

---

## Próximos Pasos

1. **Aprobar este plan** (revisar y ajustar si es necesario)
2. **Empezar FASE 1** - Fix bug de eliminación en playlists
3. **Crear rama git** para FASE 1
4. **Implementar cambios**
5. **Testear** exhaustivamente
6. **Merge** y pasar a FASE 2

---

## Historial de Cambios

| Fecha | Versión | Cambios | Autor |
|-------|---------|---------|-------|
| 2024-02-08 | 1.0 | Creación inicial del plan | Claude |

---

**Fin del documento**
