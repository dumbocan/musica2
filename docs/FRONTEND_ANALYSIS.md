# Análisis del Frontend Audio2 - Preparación para Migración Android

## Resumen Ejecutivo

El frontend de Audio2 es una aplicación React/TypeScript bien estructurada que sirve como base sólida para migración a Android. Sin embargo, requiere refactorización antes de la migración debido a:

1. **Componentes monolíticos** - Pages con 1000+ líneas
2. **Duplicación de lógica** - Especialmente en el reproductor
3. **Inconsistencias de estado** - Datos duplicados entre stores

---

## 1. Arquitectura Actual

### 1.1 Stack Tecnológico
```
Frontend: React 18 + TypeScript + Vite
Estado Global: Zustand (2 stores principales)
Routing: React Router v6
HTTP: Axios con interceptores
UI: Tailwind CSS + Radix UI
```

### 1.2 Estructura de Carpetas
```
frontend/src/
├── components/
│   ├── features/      # Componentes por dominio
│   ├── layout/        # Sidebar, AppShell
│   └── ui/            # Button, Input (base)
├── hooks/             # usePaginatedArtists, useFavorites
├── lib/               # api.ts (cliente HTTP)
├── pages/             # 10 páginas principales
├── store/             # Zustand stores (2 archivos)
├── types/             # Interfaces TypeScript
├── App.tsx            # Routing + AuthWrapper
└── main.tsx           # Entry point
```

---

## 2. Sistema de Reproducción (CRÍTICO)

### 2.1 Política de Reproducción DB-First

La política está implementada correctamente en `usePlayerStore.ts:189-298`:

```typescript
// Prioridad de reproducción (definida en README)
1. Archivo local (download_path) → reproducir directo
2. Video ID cacheado → stream desde cache local
3. Sin cache → buscar YouTube, guardar en BD, luego reproducir
```

### 2.2 Flujo de Reproducción Actual

```
User hace click en track
        ↓
PlayerFooter.tsx: playTrack()
        ↓
usePlayerStore.playByVideoId()
        ↓
[DB-First Check]
├─ ¿Tiene download_path? → usar archivo local
├─ ¿Tiene videoId? → usar stream/download
└─ ¿Nada? → buscar YouTube API → guardar en BD
        ↓
Playback: audio (m4a/mp3) o video (YouTube embed)
        ↓
Record play en BD (POST /tracks/play/{id})
```

### 2.3 Problemas Identificados en el Reproductor

| Problema | Archivo | Gravedad |
|----------|---------|----------|
| Lógica duplicada `getFormats()` | usePlayerStore.ts:96 + PlayerFooter.tsx:48 | Media |
| `rawTrack` es `unknown` | usePlayerStore.ts:44 | Alta |
| Memory leak potencial con event listeners | PlayerFooter.tsx | Baja |
| Lógica de upgrade a archivo local compleja | PlayerFooter.tsx:269-288 | Media |

### 2.4 Solución Propuesta: Single Source of Truth

Crear un servicio dedicado para reproducción:

```typescript
// services/playerService.ts
class PlayerService {
  // Unificar toda la lógica de reproducción aquí
  async play(track: Track): Promise<PlaybackResult> {
    // 1. Check local file
    if (track.download_path) {
      return this.playLocal(track.download_path);
    }
    // 2. Check cached video
    if (track.youtube_video_id) {
      return this.playYouTube(track.youtube_video_id);
    }
    // 3. Search and cache
    return this.searchAndCache(track);
  }

  async upgradeToLocal(): Promise<boolean> {
    // Upgrade de stream a archivo local
  }
}
```

---

## 3. Sistema de Datos DB-First

### 3.1 Implementación Actual en Frontend

```typescript
// TracksPage.tsx:407-476
const ensureYoutubeLink = useCallback(async (track: TrackOverview) => {
  if (track.youtube_video_id) return { videoId: track.youtube_video_id };
  if (track.local_file_exists) return { videoId: `local:${trackKey}` };
  // Solo busca en YouTube si no hay local
}, []);

// PlaylistsPage.tsx:106-107
if (track.download_path) return track;  // DB-first policy
```

### 3.2 Flujo de Datos DB-First

```
Frontend Request
      ↓
/tracks/overview (lee de PostgreSQL primero)
      ↓
¿Datos completos? → Sí → Return datos locales
      ↓ No
Consultar Spotify/Last.fm APIs
      ↓
Guardar en PostgreSQL
      ↓
Return datos enriquecidos
```

### 3.3 Backend - Refresco de Datos

Según el README, el backend maneja los refrescos:

```python
# app/core/maintenance.py
- Refresco diario de discografías (cada 24h)
- Backfill de albums/tracks faltantes
- Reparación de imágenes
- Validación de YouTube links
```

---

## 4. Componentes a Refactorizar

### 4.1 TracksPage (1054 líneas) → Dividir en:
```
components/TracksPage/
├── TrackList.tsx          # Lista virtualizada
├── TrackFilters.tsx       # Filtros (favorites, withLink, etc.)
├── TrackRow.tsx           # Fila individual
├── TrackGroup.tsx         # Agrupación de duplicados
└── TrackActions.tsx       # Menú contextual
```

### 4.2 SettingsPage (1460 líneas) → Dividir en:
```
components/SettingsPage/
├── MaintenancePanel.tsx   # Controles de mantenimiento
├── ServicesStatus.tsx     # Spotify/Last.fm/DB status
├── YoutubeSettings.tsx    # Fallback, quotas
├── ImageStats.tsx         # Cache de imágenes
└── LogsViewer.tsx         # Terminal/logs
```

### 4.3 PlayerFooter (602 líneas) → Dividir en:
```
components/Player/
├── AudioControls.tsx      # Play, pause, next, prev
├── ProgressBar.tsx        # Seek + current time
├── VolumeControl.tsx      # Volume mute
├── NowPlaying.tsx         # Track info
├── QueueDisplay.tsx       # Queue visual
└── YouTubeEmbed.tsx       # Video mode
```

---

## 5. Estado Global - Consolidación

### 5.1 Stores Actuales (problema: duplicación)

```typescript
// useApiStore.ts - Estado de datos + API
- artists, albums, tracks, playlists
- searchQuery, searchResults
- health, serviceStatus

// usePlayerStore.ts - Estado de reproducción
- nowPlaying, queue, currentIndex
- isPlaying, currentTime, duration
- audioEl, videoController
```

### 5.2 Propuesta: Separación clara

```typescript
// stores/
├── useDataStore.ts        # Solo datos (artists, albums, tracks)
├── usePlayerStore.ts      # Solo reproducción
├── useAuthStore.ts        # Solo auth (token, user)
└── useUiStore.ts          # Solo UI (sidebar, theme)
```

---

## 6. Preparación para Migración Android

### 6.1 Patrones a Mantener

| Patrón | Frontend Actual | Android Equivalent |
|--------|-----------------|-------------------|
| DB-First | `/tracks/overview` | Room DB + Retrofit |
| Estado global | Zustand stores | ViewModel + StateFlow |
| API Client | Axios interceptors | Retrofit interceptors |
| Componentes | React components | Jetpack Compose |
| Routing | React Router | Navigation Component |

### 6.2 Refactorizaciones Requeridas

#### Antes de migrar:
1. ✅ Extraer lógica de reproducción a servicio
2. ✅ Dividir pages grandes
3. ✅ Unificar sistema de caché
4. ✅ Tipado consistente

#### Después de migrar:
1. Traducir Zustand → ViewModel/StateFlow
2. Traducir Axios → Retrofit
3. Traducir React components → Jetpack Compose
4. Traducir Tailwind → Material 3

### 6.3 API Compatibility

Los endpoints actuales son RESTful y serán compatibles con Android:

```kotlin
// Android Retrofit interface
interface Audio2Api {
  @GET("/artists/")
  suspend fun getArtists(@Query("limit") limit: Int): List<Artist>

  @GET("/tracks/overview/")
  suspend fun getTracksOverview(
    @Query("limit") limit: Int,
    @Query("filter") filter: String
  ): TrackOverviewResponse

  @POST("/tracks/play/{id}")
  suspend fun recordPlay(@Path("id") trackId: Int)
}
```

---

## 7. Checklist de Refactorización

### Prioridad ALTA (Antes de migrar)
- [ ] Extraer `playByVideoId` a servicio dedicado
- [ ] Unificar `getFormats()` en un solo lugar
- [ ] Tipar `rawTrack` correctamente
- [ ] Dividir TracksPage (1000+ líneas)

### Prioridad MEDIA
- [ ] Dividir SettingsPage (1400+ líneas)
- [ ] Dividir PlayerFooter (600+ líneas)
- [ ] Implementar sistema de caché unificado
- [ ] Consolidar stores de Zustand

### Prioridad BAJA
- [ ] Optimizar re-renders con useMemo
- [ ] Implementar Error Boundaries
- [ ] Mejorar accesibilidad (buttons en lugar de divs)
- [ ] Agregar tests unitarios

---

## 8. Métricas Actuales

| Métrica | Valor |
|---------|-------|
| Total archivos TypeScript | ~120 |
| Líneas de código (pages) | ~5,500 |
| Stores Zustand | 2 |
| Componentes grandes (>500 líneas) | 3 |
| Duplicación de código | Moderada |
| Cobertura de tipos | 85% |

---

## 9. Conclusión

El frontend está bien diseñado para su propósito actual, pero **no está listo para migración directa a Android**. Las principales barreras son:

1. **Acoplamiento** - Lógica de reproducción mezclada con UI
2. **Componentes monolíticos** - Pages indivisibles
3. **Duplicación** - Múltiples fuentes de verdad

**Recomendación**: Inmediatamente después de refactorizar, crear un servidor API GraphQL que unifique el acceso a datos, facilitando la transición tanto web como mobile.

---

## 10. Archivos de Referencia

| Archivo | Propósito |
|---------|-----------|
| `usePlayerStore.ts` | Lógica de reproducción |
| `PlayerFooter.tsx` | UI del reproductor |
| `TracksPage.tsx` | Lista de tracks |
| `api.ts` | Cliente HTTP |
| `useApiStore.ts` | Estado de datos |
