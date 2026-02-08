# Tests de Operaciones de Playlist

Este documento describe los tests creados para verificar el funcionamiento correcto de las operaciones CRUD de tracks en playlists.

## Archivos de Tests

### Backend (Python/FastAPI)

**Archivo:** `tests/test_playlist_operations.py`

Contiene tests para:
- **TestPlaylistTrackRemoval**: Eliminación de tracks de playlists
- **TestPlaylistTrackAddition**: Inserción de tracks a playlists  
- **TestPlaylistIntegration**: Flujos completos (add + remove)

#### Ejecutar tests backend:

```bash
# Desde la raíz del proyecto
pytest tests/test_playlist_operations.py -v

# Con cobertura
pytest tests/test_playlist_operations.py --cov=app.api.playlists --cov-report=html

# Solo tests de eliminación
pytest tests/test_playlist_operations.py::TestPlaylistTrackRemoval -v

# Solo tests de inserción
pytest tests/test_playlist_operations.py::TestPlaylistTrackAddition -v
```

### Frontend (React/TypeScript)

**Archivo:** `frontend/src/hooks/usePlaylistOperations.test.ts`

Contiene tests para:
- **usePlaylistTrackRemoval**: Hook de eliminación
- **usePlaylistTrackAddition**: Hook de inserción
- **Funciones standalone**: Para uso fuera de hooks

#### Ejecutar tests frontend:

```bash
# Desde el directorio frontend
cd frontend

# Ejecutar todos los tests
npm test

# Ejecutar solo tests de playlists
npm test usePlaylistOperations

# Ejecutar en modo watch (para desarrollo)
npm test -- --watch

# Con cobertura
npm test -- --coverage
```

## Tests Incluidos

### Backend

#### Eliminación de Tracks

✅ `test_remove_track_success`
- Elimina un track existente
- Verifica respuesta exitosa
- Confirma eliminación en BD

✅ `test_remove_track_not_found`
- Intenta eliminar track inexistente
- Verifica error 404

✅ `test_remove_track_playlist_not_found`
- Intenta eliminar de playlist inexistente
- Verifica error 404

✅ `test_remove_track_and_verify_other_tracks_remain`
- Elimina un track de varios
- Verifica que los demás permanecen

#### Inserción de Tracks

✅ `test_add_track_success`
- Añade un track nuevo
- Verifica respuesta exitosa
- Confirma inserción en BD

✅ `test_add_track_already_exists`
- Intenta añadir track duplicado
- Verifica mensaje "already_exists"

✅ `test_add_track_playlist_not_found`
- Intenta añadir a playlist inexistente
- Verifica error 404

✅ `test_add_track_track_not_found`
- Intenta añadir track inexistente
- Verifica error 404

#### Integración

✅ `test_add_then_remove_track`
- Flujo completo: añade y luego elimina
- Verifica estado final correcto

✅ `test_playlist_tracks_endpoint_returns_correct_data`
- Verifica endpoint GET /playlists/id/{id}/tracks
- Confirma estructura de datos correcta

### Frontend

#### usePlaylistTrackRemoval

✅ `debe eliminar un track exitosamente y retornar los tracks actualizados`
- Verifica eliminación correcta
- Confirma recarga de tracks

✅ `debe manejar error cuando el track no existe`
- Maneja caso "not_found"

✅ `debe recargar tracks incluso cuando hay error`
- Mantiene sincronización aunque falle

#### usePlaylistTrackAddition

✅ `debe añadir un track exitosamente`
- Verifica inserción correcta
- Confirma recarga de tracks

✅ `debe detectar cuando el track ya existe`
- Maneja caso "already_exists"

✅ `debe manejar error 404 como track ya existente`
- Interpreta error 404 como duplicado

#### Operaciones en Batch

✅ `debe añadir múltiples tracks y contar correctamente`
- Añade 3 tracks, detecta 1 duplicado
- Verifica conteos correctos

✅ `debe manejar errores individuales sin detener el batch`
- Un error no detiene el proceso
- Continúa con los demás tracks

#### Funciones Standalone

✅ `debe funcionar fuera de hooks`
- Verifica uso sin React

## Escenarios de Prueba Manual

Además de los tests automatizados, prueba estos escenarios manualmente:

### Test 1: Eliminación Exitosa
1. Abrir una playlist con 3 canciones
2. Eliminar la segunda canción
3. Ver mensaje: "Canción eliminada correctamente"
4. Recargar página (F5)
5. ✅ Solo deben quedar 2 canciones

### Test 2: Sincronización UI-BD
1. Eliminar canción desde página Playlists
2. Verificar que se actualiza la UI inmediatamente
3. Abrir el modal "Añadir a Playlist"
4. Seleccionar la misma playlist
5. ✅ La canción eliminada NO debe aparecer

### Test 3: Eliminación desde Cola
1. Cargar una playlist en la cola
2. Eliminar canción desde "Cola Actual"
3. Ver mensaje: "Canción eliminada de la cola y de la lista"
4. Recargar la playlist
5. ✅ La canción NO debe volver a aparecer

### Test 4: Inserción y Verificación
1. Añadir canción a playlist
2. Ver mensaje de éxito
3. Abrir la playlist
4. ✅ La canción debe aparecer inmediatamente

### Test 5: Duplicados
1. Intentar añadir canción que ya está en playlist
2. Ver mensaje: "La canción ya estaba en la lista"
3. ✅ No debe crear duplicados en BD

## Debugging

Si un test falla:

### Backend
```python
# Activar logging detallado
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Frontend
```typescript
// En el hook, activar logs
console.log('Eliminando track:', playlistId, trackId);
console.log('Respuesta:', response);
```

## Mantenimiento

Al agregar nuevos features:

1. **Backend**: Agregar test en `test_playlist_operations.py`
2. **Frontend**: Agregar test en `usePlaylistOperations.test.ts`
3. **Integración**: Agregar escenario en sección "Escenarios de Prueba Manual"

## Notas

- Los tests usan base de datos de prueba (no afectan datos reales)
- Los tests frontend usan mocks (no requieren backend corriendo)
- Se recomienda ejecutar tests antes de cada commit
- CI/CD debe ejecutar tests automáticamente

---

**¿Problemas con los tests?** Verifica:
1. Base de datos PostgreSQL está corriendo
2. Backend está en modo desarrollo
3. Dependencias instaladas (`pip install -r requirements-dev.txt`)
4. Node modules actualizados (`npm install` en frontend/)
