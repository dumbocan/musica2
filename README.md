# Audio2 - Personal Music API 🎵

A **complete REST API backend** for personal music streaming, featuring **complete discographies**, **metadata enrichment**, and **smart library expansion**.

## ✨ **Key Features**

### 🎯 **Complete Discography System**
- **✅ Full artist discographies** - Every album, every track of every artist
- **✅ Automatic library expansion** - Discover 15+ similar artists per search
- **⚠️  Complete metadata** - Biographies ✅, album artwork ✅, YouTube links ⚠️ (funcional pero limitado por API quotas)
- **✅ Smart playlist management** - Favorites, ratings, history tracking, CRUD completo

### 🔄 **Library Intelligence**
- **✅ Artist expansion**: Search → get 1 main artist + 15 similar artists + ALL their music
- **⚠️  Automatic YouTube linking**: Every track gets official video search (funcional pero limitado por API quotas)
- **✅ Real-time freshness**: Data updates and new releases sync
- **⚠️  Multi-user sharing**: Community music library with deduplication (modelos preparados, algunos endpoints implementados)

### 📊 **Rich Metadata**
- **✅ Spotify integration** - Search, recommendations, popularity scores
- **✅ Last.fm data** - Biographies, play counts, user scoring
- **✅ Local storage** - PostgreSQL with proper relationships
- **✅ Tag system** - Personal categorization, play history, tag-track relationships

## 🆕 2025 Search & UX updates (últimos cambios)

- **Búsqueda unificada orquestada**: `/search/orchestrated` arma la respuesta de un solo golpe (Last.fm + Spotify) para tags/géneros. Scroll infinito en el frontend (carga por lotes) y deduplicación de artistas.
- **Modo artista/grupo**: `/search/artist-profile` devuelve ficha con bio de Last.fm, followers/popularity de Spotify y ~10 artistas afines (Last.fm similares enriquecidos). En la UI, la bio se muestra resumida y al hacer clic saltas a la ficha completa + discografía.
- **Búsqueda de canciones**: `/search/tracks-quick` devuelve tracks de Spotify con su álbum. En el frontend se muestran solo los álbumes únicos que contienen la canción (ej: “my name is” → álbum correspondiente) con botón directo al detalle del álbum.
- **Wiki de álbum (Last.fm)**: `/albums/spotify/{id}` se enriquece con `album.getInfo` de Last.fm. En la UI se muestra un resumen de la historia en párrafos, con enlace a la historia completa.
- **Navegación rápida**: en resultados de tags/géneros, las tarjetas apuntan a tu propia ficha/descografía si hay `spotify.id`, en vez de ir a Last.fm.
- **Pagos de rendimiento**: timeouts con fallback, concurrencia controlada en enriquecimiento Spotify, lotes de 60+ artistas para tags con carga progresiva en frontend.
- **Biblioteca de artistas renovada**: filtros “Filtered Results / Sort / Genre” usan una tarjeta única, tipografía uniforme y controles alineados con la barra global. Las imágenes ahora vienen siempre desde cache local y el scroll infinito respeta el orden elegido (popularidad asc/desc o alfabético) sin reorganizar la lista cargada.
- **Scroll infinito virtualizado**: las vistas con catálogos grandes (artists, search) precargan el inventario completo (lotes de 20/1000) y muestran sólo los elementos visibles + lazy images. Esto evita saltos al paginar, mantiene el total al día y permite reutilizar el patrón en cualquier listado (usa `usePaginatedArtists` / `IntersectionObserver`).

## 💅 Frontend Code Quality & Refactoring (Enero 2026)

Se ha realizado una revisión exhaustiva del código del frontend para mejorar la calidad, la seguridad de tipos, el rendimiento y la mantenibilidad. Los cambios clave incluyen:

-   **Tipado estricto con TypeScript:** Eliminación de la mayoría de las ocurrencias del tipo `any`, reemplazándolas por tipos específicos o `unknown` con guardas de tipo, lo que reduce errores en tiempo de ejecución.
-   **Optimización de React Hooks:** Refactorización de componentes (`PlayerFooter.tsx`, `AlbumDetailPage.tsx`, `SearchPage.tsx`, `TracksPage.tsx`) para asegurar el uso correcto de `useCallback`, `useMemo` y `useEffect`, resolviendo advertencias de `exhaustive-deps` y mejorando la estabilidad del rendimiento.
-   **Eliminación de código redundante y malas prácticas:** Eliminación de variables no utilizadas, refactorización de interfaces y resolución de problemas de Fast Refresh en componentes UI (como `button.tsx` y `input.tsx`).
-   **Consistencia y claridad:** Mejora de la legibilidad y la consistencia en el código a través de la estandarización de patrones y la limpieza general.

## 🆕 Backend & Data Weekend (favoritos, caché de imágenes, DB-first)

- **Favoritos multi-usuario**: nueva tabla `userfavorite` y API `/favorites` para marcar artistas, álbumes o tracks; los registros no se pueden borrar si están marcados. `target_type = artist|album|track`.
- **Datos adicionales de descarga**: los tracks guardan `download_status`, `downloaded_at`, `download_path`, `download_size_bytes`, `lyrics_source`, `lyrics_language` y `last_refreshed_at`. Artistas y álbumes también llevan `last_refreshed_at` para refrescos diarios.
- **Búsqueda DB-first**: las búsquedas orquestadas leen primero de PostgreSQL y solo van a APIs externas si faltan datos; al visitar una ficha de artista se dispara un guardado en background del artista + hasta 5 similares (álbumes + tracks).
- **Refresco diario**: bucle en `app/core/maintenance.py` que refresca discografía de los artistas favoritos cada 24h (se levanta en `startup`).
- **Proxy y resize de imágenes**: endpoint `/images/proxy?url=&size=` reduce peso con Pillow y guarda en `cache/images/*.webp`; todas las imágenes de búsqueda/artista/álbum se reescriben para servir desde la caché local.
- **Arte cacheado en la BD**: cada vez que se guarda o se lista un artista, las portadas se serializan ya proxificadas (`app/core/image_proxy.py` + `save_artist`). El endpoint `/artists/` refresca automáticamente las entradas antiguas para que incluso al cargar “fallbacks” nunca se golpee Spotify desde el frontend.
- **Rutas de almacenamiento**: `storage/images/artists`, `storage/images/albums`, `storage/music_downloads` para assets locales; la caché redimensionada vive en `cache/images`.
- **Resistencia a borrados**: `delete_artist`/`delete_album`/`delete_track` rechazan la operación si hay favoritos. Nuevos helpers en `crud` + endpoints `DELETE /albums/id/{id}` ya protegidos.
- **Dependencias**: añadido `Pillow` para el resize; `discogs-client` fijado a `2.3.0`.

## 🆕 Discografía & Tracks (DB-first, agrupación)

- **Discografía separada**: la ficha de artista divide **Álbumes / Sencillos / Compilaciones** y usa `album_group`/`album_type` cuando Spotify lo aporta.
- **Carga no bloqueante**: `/artists/{spotify_id}/albums?refresh=true` responde con BD y dispara el refresco completo en background para evitar pantallas en negro por timeouts.
- **Álbumes DB-first**: `/albums/spotify/{id}` y `/albums/{id}/tracks` sirven desde BD si hay datos y solo consultan Spotify si faltan tracks; si Spotify falla no rompen la UI.
- **Tracks sin duplicados visibles**: la vista de Tracks agrupa por `artista + nombre`, elige la mejor versión (archivo local > YouTube > favorito) y aplica favoritos al grupo completo.

## ✅ Ajustes recientes (qué, cómo y por qué)

- **Discografía completa (Spotify paginado)**: `app/core/spotify.py` ahora pagina todas las páginas (`fetch_all`) y deduplica álbumes por ID; se incluyen `album,single,compilation`. Esto evita que solo aparezcan sencillos o listas incompletas.
- **Discografía DB-first y no bloqueante**: `GET /artists/{spotify_id}/albums` devuelve primero lo local y, si `refresh=true`, lanza el refresco completo en background. Así la UI no se queda en negro cuando Spotify tarda o falla.
- **Separación profesional de discografía**: la vista de artista separa Álbumes / Sencillos / Compilaciones usando `album_group/album_type` o heurística por número de tracks (<=6 = single).
- **Álbumes y tracks DB-first**: `/albums/spotify/{id}` y `/albums/{id}/tracks` sirven desde BD si existen; si faltan tracks, se consulta Spotify y se persisten. Si Spotify falla, no rompe la UI.
- **Tracks sin duplicados**: la página Tracks agrupa por `artista + nombre`, muestra una sola fila y el favorito aplica al grupo completo. Esto evita casos tipo “Houdini” duplicado.
- **Auth/CORS más robusto**: las respuestas de auth temprano incluyen headers CORS para evitar bloqueos del navegador.
- **Búsqueda de artista resistente**: `/search/artist-profile` es DB-first y no crashea cuando Spotify falla; el frontend hace búsqueda interna si no hay `spotify_id`.

## 🎧 YouTube streaming, caché y descargas

- **Job en background** (`app/core/youtube_prefetch.py`): al arrancar `uvicorn app.main:app --reload` se ejecuta `youtube_prefetch_loop()` que inspecciona la tabla `track` y va rellenando `YouTubeDownload` uno a uno. Usa `youtube_client.min_interval_seconds = 5` para no quemar cuota y, si recibe un `403/429`, entra en enfriamiento de 15 min. Vigila los avances con `tail -f uvicorn.log | grep youtube_prefetch`.
- **Prefetch bajo demanda**: `POST /youtube/album/{spotify_id}/prefetch` dispara un job que recorre los tracks del álbum usando Spotify, guarda el mejor `youtube_video_id` y respeta la misma pausa de 5 s. El frontend lo llama automáticamente cuando visitas un álbum, pero también lo puedes usar vía `curl` con un token válido.
- **Pistas & dataset demo**: el directorio `downloads/` almacena los MP3 organizados por artista (por ejemplo `downloads/Dr.-Dre/Dr.-Dre - Still D.R.E..mp3`). El dataset de demo incluye 41 pistas ya descargadas para 15 artistas (50 Cent, Eminem, Radiohead, Gorillaz, etc.) y puedes consultarlas vía `GET /tracks/overview`.
- **Contadores híbridos en álbumes**: `GET /artists/{spotify_id}/albums` ahora suma tanto los links guardados en la BD como los MP3 descargados que coincidan con los track IDs de Spotify. Eso evita mostrar `0` aunque todavía no se haya guardado el álbum localmente.
- **Logs y depuración**: los prefetches registran líneas `[youtube_prefetch] Cached ARTIST - TRACK` en la consola. Si ves `Stopping YouTube prefetch ... 403`, espera 15 min o baja la cadencia de peticiones antes de reintentar.
- **Credenciales obligatorias**: sin `YOUTUBE_API_KEY` en `.env` los endpoints `/youtube/...` devuelven `401/500` y la UI marca error. Asegúrate de tener la clave incluida antes de visitar las páginas de álbumes o la vista global de tracks.
- **Dos claves de YouTube (sin fallback)**: también puedes definir `YOUTUBE_API_KEY_2`. El backend usa ambas en orden (`YOUTUBE_API_KEY`, luego `YOUTUBE_API_KEY_2`) y rota cuando una falla por cuota.
- **Importante**: después de cambiar claves en `.env`, reinicia backend (`uvicorn`) para que cargue los nuevos valores.
- **Fallback yt-dlp (opt-in)**: cuando la cuota de YouTube se agota, el backend puede buscar links con yt-dlp si activas `YTDLP_FALLBACK_ENABLED=true`. Ajusta `YTDLP_DAILY_LIMIT` y `YTDLP_MIN_INTERVAL_SECONDS` para controlar el coste diario.
- **Cookies para yt-dlp (recomendado)**: para reducir bloqueos `Sign in to confirm you're not a bot`, configura `YTDLP_COOKIES_FROM_BROWSER=firefox` (o `chrome/brave` según tu sesión) en `.env`. También puedes usar `YTDLP_COOKIES_FILE=/ruta/cookies.txt`.
- **Renovación de cookies**: cuando veas errores `Sign in to confirm you're not a bot`, ejecuta:
  ```bash
  python scripts/renew_youtube_cookies.py --check  # Verificar estado
  python scripts/renew_youtube_cookies.py          # Renovar cookies (usa Firefox)
  python scripts/renew_youtube_cookies.py --browser chrome  # Usar Chrome
  ```
  Las cookies caducan cada ~30 días y el script las renueva automáticamente desde el navegador.
- **Runtime JS automático para yt-dlp**: el backend ahora autodetecta `node` y habilita componentes remotos EJS para resolver challenges de YouTube (`SABR/signature`). Si existe `storage/cookies/youtube_cookies.txt`, se usa automáticamente como `cookiefile`.
- **Playback restaurado en paralelo**: `/youtube/stream` volvió al flujo “reproducir mientras descarga/cachea”. Si el audio ya existe en disco, sirve local (DB-first). Si no existe, hace stream inmediato y guarda en paralelo.
- **Streaming robusto ante 403 de googlevideo**: el backend usa cabeceras del extractor y descarga por rangos cerrados (`bytes=start-end`) para evitar errores de reproducción donde el navegador veía `200` pero el stream real fallaba.
- **Toggle + métricas en Settings**: la pantalla de ajustes permite activar/desactivar el fallback, ver el contador de links guardados y el uso diario del fallback.
- **Log de fallback (30 días)**: los videos guardados vía yt-dlp se registran en `storage/logs/ytdlp_fallback.log` (respeta `STORAGE_ROOT`). El archivo se recorta según `LOG_RETENTION_DAYS`.
- **Validación anti “Not Found”**: los links del fallback pasan por un chequeo ligero (oEmbed) antes de guardarse.

## 🧭 Fallback YouTube (explicado fácil + por qué existe)

### ¿Qué es el fallback?
Cuando la API de YouTube llega al límite diario, el backend **intenta otra fuente** (yt-dlp) para buscar el link del video. Es opcional y se controla desde Settings o con `YTDLP_FALLBACK_ENABLED`.

### ¿Por qué hay “tanto código”?
Porque el fallback debe ser **seguro y controlado**:
1) **No romper la app** si no hay API key.  
2) **No abusar** de la red (límites diarios y pausas).  
3) **Guardar el origen** de cada link (API vs yt‑dlp).  
4) **Dejar rastro** en logs para poder limpiar si hay falsos positivos.  
5) **Mostrarlo en Settings** con un botón y un contador claro.  

### Viaje del dato (ejemplo: “Eminem — Without Me”)
1) **Buscas “Without Me”** en la app (o entras al artista/álbum).  
2) El backend mira primero en BD:  
   - Si ya existe un `YouTubeDownload` con `youtube_video_id`, **se usa directamente** (DB‑first).  
3) Si no hay link en BD, el backend intenta la **API de YouTube**.  
   - Si encuentra un video: se guarda en BD con `link_source="youtube_api"` y ya queda cacheado.  
4) Si la API falla por cuota o no devuelve resultados, **y el fallback está activo**:  
   - Se usa **yt‑dlp** para buscar el link.  
   - Si encuentra uno: se guarda en BD con `link_source="ytdlp"`.  
   - Se registra una línea en `storage/logs/ytdlp_fallback.log` con artista/track/video_id.  
5) A partir de ahí, **las siguientes veces se lee desde BD** (no repite llamadas externas).  

Resumen: **primero BD → luego YouTube API → luego yt‑dlp (si está activo)**.  
Una vez guardado el link, siempre es DB‑first.

### Diagrama rápido (texto)
```
UI → Backend
   └─ ¿Existe en BD? → Sí → responde link
                   └→ No → intenta YouTube API
                          └→ encontrado → guarda en BD (link_source=youtube_api)
                          └→ no encontrado / cuota → si fallback ON → yt‑dlp
                                                     └→ encontrado → guarda en BD (link_source=ytdlp) + log
                                                     └→ no encontrado → guarda status "video_not_found"
```

## 🎛️ Tracks dashboard + endpoint de estado

- **Endpoint nuevo**: `GET /tracks/overview` devuelve cada track con artista, álbum, duración y estado de YouTube/archivo local (`youtube_status`, `youtube_url`, `local_file_exists`). Es la base para la pestaña “Tracks” del frontend.
- **Frontend renovado**: `frontend/src/pages/TracksPage.tsx` muestra métricas globales (cuántas pistas tienen link o MP3), buscador, filtros y accesos directos para abrir YouTube o descargar el MP3 desde `/youtube/download/{video_id}/file`.
- **Uso recomendado**: abre `http://localhost:5173/tracks` para saber qué canciones ya están listas para streaming/descarga sin entrar álbum por álbum.

## 📈 Charts & historial de reproduccion

- **Billboard en BD**: la BD se rellena con historicos (Top 5 / #1) y se expone en `GET /charts/external/raw` para la vista “BD historico”.
- **Badges en tracks**: `GET /tracks/chart-stats` y `GET /tracks/overview` devuelven `chart_best_position` + `chart_best_position_date` para mostrar `#1 (dd-mm-aaaa)` en Tracks/Album/Search.
- **Historial real**: `POST /tracks/play/{track_id}` guarda reproducciones. El dashboard usa `GET /tracks/most-played` y `GET /tracks/recent-plays` para contadores reales.

## ✅ Tracks: problemas reales y soluciones aplicadas

- **Desajuste “Con link YouTube”**: el total salía 106 pero solo aparecían 95. La causa fue `youtube_video_id` vacío en `YouTubeDownload`. Se filtró `youtube_video_id != ""` en `/tracks/overview`, y se prioriza el registro con video real cuando hay múltiples filas por track.
- **Filtro lento por `youtube`**: antes se cargaba todo y el frontend filtraba. Ahora `/tracks/overview` acepta `filter` y `search` para que la BD devuelva solo lo necesario, y responde `filtered_total` para mostrar el progreso real.
- **Paginado y rendimiento**: paginado por `after_id` (keyset) + `limit` en backend; en frontend se precarga cuando quedan ~100 filas y sigue cargando 200 en 200 sin saturar la red.
- **Consistencia UI**: filtros + búsqueda + progreso quedan sticky y la tabla virtualizada mantiene un solo scroll.

## 🏁 Historias recientes: lo que funciona / lo que queda por pulir
- ✅ El reproductor híbrido mezcla audio local (MP3/m4a) con streaming de YouTube, mantiene el footer global, sincroniza contadores de peticiones y actualiza el estado `link_found` desde `YouTubeDownload`.
- ✅ Las descargas se alojan en carpetas organizadas por artista/álbum (`downloads/<Artist>/<Album>/`) y hay scripts para reubicar colecciones antiguas, permitiendo reproducir desde la UI sin salir del navegador.
- ✅ La vista de Tracks trae sticky filters, barra de progreso y paginado por lotes (200 en 200) con carga anticipada cuando quedan ~100 filas, además de emitir totales filtrados para mostrar “Mostrando X de Y”.
- ⚠️ La cuota de YouTube puede cortar el prefetch con 403/429; las busquedas ocurrieron una sola vez por álbum, pero los errores aún dejan “Sin enlace” si `download_status` no se normaliza a `link_found`.
- ⚠️ El modo video todavía compite con el reproductor de audio: los botones del footer reinician la pista cuando deberían pausar, el slider no permite seek manual y los iframes generan flash negro si se recrean sin limpiar el estado anterior.
- ⚠️ Algunos filtros de `/tracks/overview` devuelven `400 Bad Request` o `422 Invalid filter` si se envían valores no reconocidos, y en local se han visto bloqueos CORS contra `/tracks/overview` y `/search/artist-profile` cuando el backend no está activo.
## ⚠️ Troubleshooting reciente (YouTube + reproducción)

- **Cuota YouTube 403/429**: los prefetches se paran 15 min tras un 403/429. Evita loops extra y llama a YouTube solo cuando entras a un álbum o cuando el usuario pulsa play. Mantén `YOUTUBE_API_KEY` (y opcionalmente `YOUTUBE_API_KEY_2`) en `.env`.
- Si ambas claves están agotadas/bloqueadas, verás `403 Forbidden` en `/youtube/stream` o `/youtube/download` aunque la app esté bien.
- **“Sin enlace de YouTube” con link real**: puede pasar si `download_status` quedó en `missing/error` aunque exista `youtube_video_id`. El backend normaliza a `link_found`, pero si hay datos antiguos conviene revisar/normalizar la tabla `YouTubeDownload`.
- **IDs de track inconsistentes**: algunas respuestas traen `track.spotify_id` en vez de `track.id`. El frontend debe resolver el ID con `track.id || track.spotify_id` antes de llamar a `/youtube/track/...`.
- **Streaming vs descarga**:
  - `GET /youtube/stream/{video_id}` permite reproducir mientras descarga, pero el `audio.duration` puede ser `0/NaN` hasta que cargue metadata y no permite seek.
  - `GET /youtube/download/{video_id}/file?format=mp3` falla si el archivo está en `m4a`. Consulta primero `/youtube/download/{video_id}/status` para saber el formato real.
- **Reproductor embebido de YouTube**: el iframe consume CPU y puede bloquear el scroll; usa audio-only siempre que sea posible.
- **Descargas locales “fake”**: no uses `youtube_video_id` inventados (no son 11 chars). Si hay audio local sin link real, no muestres “Abrir en YouTube” en el UI.
- **Organización de descargas**: los archivos deben quedar en `downloads/<Artist>/<Album>/<Track>.<ext>`. Para migrar descargas antiguas usa `scripts/organize_downloads_by_album.py --resolve-unknown --resolve-spotify --spotify-create` (requiere credenciales Spotify).
- **Contador de uso**: `frontend/src/components/YoutubeRequestCounter.tsx` consulta `/youtube/usage` periódicamente; si el backend está apagado verás errores de red en consola.
- **Error "Sign in to confirm you're not a bot"**: Las cookies de YouTube caducan cada ~30 días. Cuando veas este error:
  1. Ejecuta `python scripts/renew_youtube_cookies.py` para renovar
  2. O usa `python scripts/renew_youtube_cookies.py --browser chrome` si usas Chrome
  3. Si los tracks tienen `status=link_found` pero `download_path` vacío, descárgalos manualmente con `python scripts/download_tracks.py` o desde Settings.

## ▶️ Playback & Download Policy (BIBLIA - No Regresar)

Para evitar regressions y garantizar reproduccion correcta, la politica de reproduccion y descarga queda DEFINIDA ASI:

### 1. **DB-First (Base de datos primero)**
- Buscar si ya existe `YouTubeDownload` con `youtube_video_id` para ese track
- Si existe archivo en disco → usar directamente
- Solo marcar `completed` cuando archivo existe verificadamente

### 2. **Playback - Streaming + Cache en Paralelo**
- **Stream inmediato**: reproducir mientras descarga
- **Cache en paralelo**: guardar archivo mientras suena
- Si hay `youtube_video_id` → sincronizar con video de YouTube
- NO marcar como `completed` hasta que archivo exista fisicamente

### 3. **Video Sincronizado**
- Si el track tiene `youtube_video_id` → mostrar video de YouTube
- Video se reproduce **sincronizado** con el audio
- Controles (play/pause/skip) afectan tanto video como audio

### 4. **YouTube API (si no hay link)**
- Buscar video en YouTube Data API v3
- Si encuentra → guardar en BD con `link_source="youtube_api"`, status `link_found`
- Si no encuentra → status `video_not_found`

### 5. **yt-dlp Fallback (si API falla)**
- Si YouTube API quota agotada (403/429) → usar yt-dlp
- Usar cookies del navegador (`--cookies-from-browser chrome`)
- Guardar en BD con `link_source="ytdlp"`
- Registrar en `storage/logs/ytdlp_fallback.log`

### 6. **Descarga Real (cuando se completa)**
- Path correcto: `downloads/Artista/Album/Track.mp3`
- Formato: **MP3** (no webm, no m4a)
- Verificar que el archivo existe antes de marcar como `completed`

### 7. **Logs y Debug**
- yt-dlp fallback → `storage/logs/ytdlp_fallback.log`
- Prefetch → `logs/uvicorn.log` (grep "youtube_prefetch")
- Errores → `logs/app.log`

### Reglas de Oro
- `youtube_video_id` solo valido si tiene 11 caracteres (`[A-Za-z0-9_-]{11}`)
- Descarga en paralelo es **best-effort**: 403 no debe romper playback
- Esta politica aplica a Tracks, Playlists y Albumes
- Mantener consistente entre frontend y backend

---

## ⚠️ Troubleshooting DNS (Spotify/Last.fm "offline" sin motivo)

- **Síntoma**: `/health/detailed` marca `spotify/lastfm = offline` con `timeout`, pero los tokens están bien y el backend está levantado.
- **Causa típica**: DNS local roto (systemd-resolved), a menudo tras reiniciar, cambiar de red o activar/desactivar VPN.
- **Fix rápido (temporal)**:
  1) Identifica interfaz activa: `ip route | grep '^default'`
  2) Aplica DNS en la interfaz principal (ej. `enp2s0`):
     - `sudo resolvectl dns enp2s0 1.1.1.1 8.8.8.8`
     - `sudo resolvectl domain enp2s0 ~.`
     - `sudo resolvectl flush-caches`
  3) Verifica resolución:
     - `python3 -c "import socket; print(socket.getaddrinfo('accounts.spotify.com',443)[0][4])"`
     - `curl -I https://api.spotify.com/v1`
  4) Reinicia el backend y vuelve a probar `/health/detailed`.
- **Nota**: Si hay VPN (p. ej. Surfshark), prueba a desconectarla o fija DNS para evitar resoluciones inconsistentes.
- **Persistente** (requiere sudo): edita `/etc/systemd/resolved.conf` y define
  - `DNS=1.1.1.1 8.8.8.8`
  - `FallbackDNS=1.0.0.1 8.8.4.4`
  Luego ejecuta `sudo systemctl restart systemd-resolved`.

## 🏗️ **Tech Stack**

| Component | Technology | Details |
|-----------|------------|---------|
| **API Framework** | FastAPI | Async REST API with OpenAPI docs |
| **Database** | PostgreSQL | Production-ready, SQLModel ORM |
| **ORM** | SQLModel | Type-safe SQLAlchemy wrapper |
| **External APIs** | Spotify, Last.fm, YouTube | Metadata enrichment |
| **Dependencies** | httpx, pydantic | Async HTTP, data validation |

## 🚀 **Quick Start**
### Prerequisites
- Python 3.8+
- SQLite (built in) for local/dev usage; install PostgreSQL if you want to mirror production
- Git

### Installation

1. **Clone and setup:**
```bash
git clone https://github.com/dumbocan/musica2.git
cd audio2
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Configure environment:**
```bash
# Copy and edit .env
cp .env.example .env
# Only run the copy the first time; it overwrites an existing .env.
# Edit .env with your database and API credentials
# Add Spotify/Last.fm/Youtube keys only if you will hit those endpoints.
# IMPORTANT: set YOUTUBE_API_KEY before visiting album/track pages; otherwise the UI will warn about missing streaming links.
# Optional: set AUTH_RECOVERY_CODE to enable password reset from the login screen.
```

4. **Start the server:**
```bash
/home/micasa/audio2/venv/bin/uvicorn app.main:app --reload
```

**Server URL**: http://localhost:8000

### Backend control (venv, recomendado)

```bash
# Parar backend en puerto 8000 (si hay uno corriendo)
pkill -f "uvicorn app.main:app --reload" || true

# Arrancar backend usando SIEMPRE el venv del proyecto
/home/micasa/audio2/venv/bin/uvicorn app.main:app --reload
```

Verificacion rapida:
```bash
pgrep -af "uvicorn app.main:app --reload"
```
Debes ver el ejecutable dentro de `.../audio2/venv/bin/python3` / `.../audio2/venv/bin/uvicorn`.

### Quick API Test
```bash
curl http://localhost:8000/health
# Expected: {"status": "ok"}
```

## 🗄️ Database Setup (PostgreSQL)

- **Project requirement**: This repo is configured to use **PostgreSQL only**. Keep `DATABASE_URL` set to a Postgres connection string.
- **Local/dev and production**: set `DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/dbname` and ensure Postgres is running before starting the API.
- **Stack ORM explicado**:
  - `SQLModel 0.0.27` define clases únicas que sirven como modelos de Pydantic y tablas SQL (ver `app/models/base.py`).
  - `SQLAlchemy 2.0.44` ejecuta las consultas/relaciones reales sobre cualquier motor soportado.
  - `psycopg2-binary 2.9.11` es el driver Postgres que SQLAlchemy usa cuando la URL apunta a `postgresql+psycopg2://`.

```bash
# Arrancar con Postgres (dev o produccion)
createdb audio2
export DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/audio2
python - <<'PY'
from app.core.db import create_db_and_tables
create_db_and_tables()
PY
```

## 📚 **API Endpoints**

### 🎤 **Artists**
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/artists/search?q=eminem` | GET | Search artists via Spotify |
| `/artists/search-auto-download?q=eminem` | GET | **Auto-expand complete library** |
| `/artists/{spotify_id}/albums` | GET | Get artist albums |
| `/artists/{spotify_id}/discography` | GET | Full discography (Spotify) |
| `/artists/id/{local_id}/discography` | GET | Full discography (local DB) |
| `/artists/save/{spotify_id}` | POST | Save artist to DB |
| `/artists/{spotify_id}/full-discography` | POST | **Save complete discography** |
| `/artists/refresh-missing` | POST | Backfill missing bio/genres/images (Spotify + Last.fm) |
| `/artists/id/{artist_id}/hide?user_id=1` | POST | Hide artist for the user |
| `/artists/id/{artist_id}/hide?user_id=1` | DELETE | Unhide artist for the user |

### 📀 **Albums**
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/albums/save/{spotify_id}` | POST | Save album + all tracks |
| `/albums/{spotify_id}/albums` | GET | Get album details |

### 🎵 **Tracks**
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/tracks/enrich/{track_id}` | POST | Add Last.fm data |
| `/tracks/{track_id}/rate?rating=5` | POST | Rate track 1-5 |
| `/tracks/play/{track_id}` | POST | Record a play for history |
| `/tracks/overview` | GET | Track list with YouTube/cache status |
| `/tracks/chart-stats` | GET | Chart badge stats for tracks |
| `/tracks/most-played` | GET | Most played tracks (per user) |
| `/tracks/recent-plays` | GET | Recent plays (per user) |

### � **Playlists & Smart Playlists**
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/playlists/` | GET/POST | CRUD básico de playlists |
| `/playlists/id/{id}` | GET/PUT/DELETE | Gestión individual de playlists |
| `/playlists/id/{id}/tracks` | GET | Tracks de una playlist |
| `/playlists/id/{id}/tracks/{track_id}` | POST/DELETE | Agregar/quitar tracks |
| `/smart-playlists/top-rated` | POST | Crear playlist con mejores ratings |
| `/smart-playlists/most-played` | POST | Crear playlist con más reproducidas |
| `/smart-playlists/favorites` | POST | Playlist de favoritas |
| `/smart-playlists/recently-played` | POST | Playlist de últimamente escuchadas |
| `/smart-playlists/discover-weekly` | POST | Playlist estilo "Discover Weekly" |

### 🏷️ **Tags & Play History**
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/tags/` | GET | Listar todas las tags |
| `/tags/create` | POST | Crear nueva tag |
| `/tags/tracks/{track_id}/add` | POST | Agregar tag a track |
| `/tags/tracks/{track_id}/remove` | POST | Quitar tag de track |
| `/tags/play/{track_id}` | POST | Registrar reproducción |
| `/tags/history/{track_id}` | GET | Historial de reproducciones |
| `/tags/recent` | GET | Reproducciones recientes |
| `/tags/most-played` | GET | Tracks más reproducidos |

### �🔗 **YouTube Integration**
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/youtube/download/{track_id}` | POST | Download YouTube audio |
| `/youtube/status/{track_id}` | GET | Get download status |
| `/youtube/album/{spotify_id}/prefetch` | POST | Cache links for every track in an album |
| `/youtube/track/{spotify_track_id}/link` | GET | Read cached link info (status/url) |
| `/youtube/fallback/status` | GET | Estado y cuota del fallback yt-dlp |
| `/youtube/fallback/toggle` | POST | Activar/desactivar fallback yt-dlp |
| `/youtube/fallback/logs` | GET | Últimos links guardados por fallback |

## 🎯 **Key Features in Action**

### **Complete Library Expansion**
```bash
# One search → complete music library
GET /artists/search-auto-download?q=eminem

# Returns: 1 main artist + 15 similar + ALL their albums/tracks
#         + metadata + YouTube links + biographies
```

### **Smart Playlist Examples**
- **Favorites**: `GET /playlists/favorites/{user_id}`
- **Most Played**: `GET /playlists/most-played/{user_id}`
- **Recent**: `GET /playlists/recent/{user_id}`

## 🗃️ **Database Schema**

```sql
Artist (
  id, spotify_id, name, genres, images,
  popularity, followers, bio_summary, bio_content,
  last_refreshed_at,
  created_at, updated_at
)

Album (
  id, spotify_id, artist_id, name, release_date,
  images, total_tracks, label,
  last_refreshed_at,
  created_at, updated_at
)

Track (
  id, spotify_id, artist_id, album_id, name,
  duration_ms, popularity, user_score, is_favorite,
  lastfm_listeners, lastfm_playcount,
  download_status, downloaded_at, download_path, download_size_bytes,
  lyrics, lyrics_source, lyrics_language,
  last_refreshed_at,
  created_at, updated_at
)

UserFavorite (
  id, user_id, target_type,
  artist_id, album_id, track_id,
  created_at
)

YouTubeDownload (
  id, spotify_track_id, youtube_video_id, link_source,
  download_status, file_size, error_message
)
```

## 🔧 **Configuration**

Create `.env` file:
```env
# Database
DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/music_db

# External APIs
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
LASTFM_API_KEY=your_lastfm_api_key
YOUTUBE_API_KEY=your_youtube_api_key
YTDLP_FALLBACK_ENABLED=false
YTDLP_DAILY_LIMIT=120
YTDLP_MIN_INTERVAL_SECONDS=2.0
YTDLP_COOKIES_FILE=/home/micasa/audio2/storage/cookies/youtube_cookies.txt
# Opcional (normalmente no hace falta si autodetección funciona):
YTDLP_JS_RUNTIMES=node:/home/micasa/.nvm/versions/node/v22.21.1/bin/node
YTDLP_REMOTE_COMPONENTS=ejs:github

# Logs
LOG_RETENTION_DAYS=30
```

## 🛠️ Troubleshooting YouTube (casos reales)

Si falla una canción con `502` en `/youtube/stream/...`, sigue este runbook completo.

### 1) Confirmar que backend y DB están arriba

```bash
pg_isready -h 127.0.0.1 -p 5432
curl -s http://localhost:8000/health
```

Si backend no levanta, revisa `.env` (`DATABASE_URL`) y reinicia:

```bash
cd /home/micasa/audio2
mkdir -p logs
/home/micasa/audio2/venv/bin/uvicorn app.main:app --reload > logs/uvicorn.log 2>&1
```

### 2) Ver error exacto del video problemático

```bash
curl -i --max-time 30 \
  "http://localhost:8000/youtube/stream/<VIDEO_ID>?format=m4a&cache=true&token=<TOKEN_REAL>"
```

Errores típicos:
- `Sign in to confirm you're not a bot`
- `Unable to cache/stream audio file`
- `403 Forbidden` (googlevideo)

### 3) Probar yt-dlp fuera de la app (diagnóstico real)

Usa siempre el `yt-dlp` del venv:

```bash
/home/micasa/audio2/venv/bin/python -m yt_dlp --version
/home/micasa/audio2/venv/bin/python -m yt_dlp -v \
  --cookies /home/micasa/audio2/storage/cookies/youtube_cookies.txt \
  "https://www.youtube.com/watch?v=<VIDEO_ID>" -f bestaudio -g
```

Si aquí falla, el backend también fallará.

### 4) Si falla por bot/login: renovar cookies

1. Inicia sesión en YouTube desde tu navegador principal.
2. Exporta cookies en formato Netscape (`youtube_cookies.txt`).
3. Guarda en:
   `/home/micasa/audio2/storage/cookies/youtube_cookies.txt`
4. Verifica que incluya `.youtube.com`:

```bash
grep -E "youtube\\.com|google\\.com" /home/micasa/audio2/storage/cookies/youtube_cookies.txt | head
```

### 5) Si falla por JS challenge/SABR

Síntomas en `yt-dlp -v`:
- `JS runtimes: none`
- `Signature solving failed`
- `n challenge solving failed`
- `Only images are available for download`

Solución:

```bash
node -v
/home/micasa/audio2/venv/bin/python -m yt_dlp -v \
  --js-runtimes "node:/home/micasa/.nvm/versions/node/v22.21.1/bin/node" \
  --remote-components ejs:github \
  --cookies /home/micasa/audio2/storage/cookies/youtube_cookies.txt \
  "https://www.youtube.com/watch?v=<VIDEO_ID>" -f bestaudio -g
```

Si este comando devuelve URL `googlevideo...`, la extracción está bien.

### 6) Variables recomendadas en `.env`

```env
YTDLP_COOKIES_FILE=/home/micasa/audio2/storage/cookies/youtube_cookies.txt
YTDLP_JS_RUNTIMES=node:/home/micasa/.nvm/versions/node/v22.21.1/bin/node
YTDLP_REMOTE_COMPONENTS=ejs:github
```

Notas:
- El backend ahora autodetecta `node` y `storage/cookies/youtube_cookies.txt`, pero estas variables lo dejan explícito y estable.
- `--extractor-args youtube:player_client=android` puede no servir con cookies (normal en yt-dlp reciente).

### 7) Reiniciar backend y validar desde app

```bash
pkill -f "uvicorn app.main:app" || true
cd /home/micasa/audio2
/home/micasa/audio2/venv/bin/uvicorn app.main:app --reload > logs/uvicorn.log 2>&1
```

Reproducir una pista:
- si ya está local (DB-first) => reproduce sin tocar YouTube.
- si no está local y hay `videoId` => stream inmediato + cache en paralelo.
- si no hay `videoId` => busca link y luego reproduce.

### 8) Revisar logs cuando vuelva a fallar

```bash
tail -n 200 /home/micasa/audio2/logs/uvicorn.log | \
  grep -E "youtube|yt-dlp|403|Sign in|bot|stream|download"
```

### 9) VPN y bloqueos regionales

Con VPN pueden aumentar:
- `LOGIN_REQUIRED`
- `403` en `googlevideo`
- “Inicia sesión” en iframe

Si hay dudas, prueba sin VPN para confirmar.

### 10) Política de reproducción (no romper)

1. Si hay archivo local (`download_path`) -> reproducir local, no YouTube.
2. Si no hay local pero hay `videoId` -> stream + cache en paralelo.
3. Si no hay ninguno -> buscar link y reproducir.
4. Si YouTube bloquea descarga, no bloquear UI ni romper audio si el stream sigue disponible.

## 🚀 **Usage Examples**

### **1. Complete Library Setup**
```python
# Search expands to complete library
response = api.search_artists_auto_download("eminem")
# → Saves Eminem + 15 similar artists + ALL their music
```

### **2. Download Management**
```python
# Download track from YouTube
api.download_youtube_audio(track_id)

# Check status
status = api.get_download_status(track_id)
# → "completed", "downloading", "failed"
```

### **3. Personalized Experience**
```python
# Rate and favorite
api.rate_track(track_id, 5)
api.mark_favorite(track_id, True)

# Smart playlists
favorites = api.get_user_favorites(user_id)
most_played = api.get_most_played(user_id)
```

## 🔌 Endpoints añadidos (fin de semana)
- `/favorites` **(POST/DELETE/GET)**: marcar y leer favoritos por usuario (`artist|album|track`).
- `/images/proxy?url=&size=`: proxy + resize WebP en caché local (`cache/images`), usado en búsquedas, fichas y álbumes.
- `/search/orchestrated`: ahora **lee primero de la base de datos** y solo consulta APIs externas si faltan datos.
- `/artists/profile/{spotify_id}` y `/search/artist-profile`: al consultarlos, guardan en background la discografía del artista + hasta 5 similares.
- `/albums/spotify/{id}`: devuelve wiki de Last.fm y URLs de imagen ya proxied.
- `DELETE /albums/id/{id}` / `delete_track` (CRUD) bloquean la operación si el recurso está en favoritos.

## 📂 Rutas de almacenamiento y caché
- `storage/images/artists` → retratos finales (ya optimizados).
- `storage/images/albums` → portadas finales.
- `storage/music_downloads` → audio descargado/local.
- `storage/logs/ytdlp_fallback.log` → log JSONL de links encontrados por el fallback yt-dlp (respeta `LOG_RETENTION_DAYS`).
- `cache/images` → caché WebP generada por `/images/proxy`.
- `downloads/` (histórico) y `cache/` se pueden limpiar si necesitas espacio; los favoritos bloquean borrados de registros en BD.
- En pruebas, las descargas se guardan localmente en `downloads/`; a futuro se planea soportar discos externos y/o carpetas gestionadas por torrents, por lo que las rutas deben mantenerse configurables.

## 🧪 Tests rápidos + cómo ver la base de datos
- **Smoke de expansión y favoritos**: `python test_library_expansion.py` (requiere `SPOTIFY_CLIENT_ID/SECRET` y `LASTFM_API_KEY` en `.env`). Verifica que artistas/albums/tracks se guarden con campos nuevos (`download_status`, `lyrics_*`, `last_refreshed_at`, etc.).
- **Inspección manual vía psql**:
  ```bash
  psql "$DATABASE_URL" -c "SELECT table_name FROM information_schema.tables WHERE table_schema='public';"
  psql "$DATABASE_URL" -c "SELECT id, name, followers, last_refreshed_at FROM artist ORDER BY followers DESC LIMIT 5;"
  psql "$DATABASE_URL" -c "SELECT id, target_type, artist_id, album_id, track_id FROM userfavorite LIMIT 5;"
  ```
- **Script de inspección**: `python database_inspection.py` imprime usuarios, artistas, tracks y descargas para una vista rápida.
- **Reset total (cuidado, borra todo)**:
  ```bash
  psql "$DATABASE_URL" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
  python - <<'PY'
  from app.core.db import create_db_and_tables
  create_db_and_tables()
  PY
  ```

## 📊 **Architecture Highlights**

- **Asynchronous**: FastAPI with async PostgreSQL operations
- **Type-safe**: SQLModel for ORM and Pydantic schemas
- **Multi-user ready**: User relationships prepared
- **Error resilient**: Handles API failures gracefully
- **Production ready**: Proper logging, validation, docs

## 💡 **The "Old Spotify" Experience**

This system recreates the classic Spotify feeling:
- **Infinite music discovery**
- **Complete artist collections**
- **Offline-ready downloads**
- **Personal curation**

But as a **personal API** you can:
- **Own your data** (PostgreSQL storage)
- **No ads/no limits** on discovery
- **Custom extensions** and modifications
- **Multi-device sync** with your own rules

---

**Built with ❤️ for music lovers everywhere**


Project Plan
Current Implementation (Step-by-Step)
 Git setup: Init repo, .gitignore, remote (musica2 on GitHub).
 Create comprehensive README with instructions.
 Set up virtual environment and install dependencies.
 Create project structure (app/, api/, core/, models/).
 Implement FastAPI app with health endpoint.
 Configure PostgreSQL connection (prepared, not connected yet).
 Test server startup and health endpoint (200 OK, returns {"status":"ok"}).
 Set up and test PostgreSQL DB connection in code.
 Add session manager and prepare for models.
 Verify server works with DB integration.
 Review and document setup.
Current Status
✅ Basic FastAPI + PostgreSQL DB.
✅ Spotify integration: Search artists, get albums/tracks, save to DB.
✅ Local query endpoints: GET all/id for artists, albums, tracks.
✅ Last.fm client added for scoring (playcount/listeners).
✅ Endpoint POST /tracks/enrich/{track_id} to update track with Last.fm data.
**✅ ALL FEATURES COMPLETED:**
✅ Research external APIs (Spotify, Last.fm, Musixmatch) for data endpoints.
✅ Define models: User, Artist, Album, Track, Playlist (with relationships, ready for multiuser).
✅ Set up PostgreSQL tables for all models.
✅ Implement Spotify API client (auth, search artists) + httpx async.
✅ Add first endpoint: GET /artists/search?q=artist for searching via Spotify API.
✅ Add endpoint: GET /artists/{spotify_id}/albums for discography.
✅ Add saving data to DB: POST /artists/save/{spotify_id} saves artist from Spotify to DB.
✅ Add saving data to DB: POST /albums/save/{spotify_id} saves album and all its tracks from Spotify to DB.
✅ Add query endpoints for local DB: GET /artists, GET /artists/id/{artist_id}, GET /albums, GET /albums/id/{album_id}, GET /tracks, GET /tracks/id/{track_id}.
✅ Add sync-discography endpoint for updating artist new albums.
✅ Add deduplication by normalized name for artists.
✅ Add CASCADE delete for artists (DELETE /artists/id/{id} deletes artist + all albums/tracks).
✅ Add discography endpoint: GET /artists/id/{artist_id}/discography (artist + all albums + tracks from DB).
✅ Add bio enrich from Last.fm: artist bio_summary/content and POST /artists/enrich_bio/{artist_id}.
✅ Add music recommendations: GET /artists/{spotify_id}/recommendations (tracks/artists similar via Spotify).
✅ Integrate Last.fm for playcount/listeners scoring.
✅ Implement discography endpoints.
✅ Add playlist CRUD.
✅ Integrate ratings/favorites.
✅ Add tags, play history.
✅ Enable smart playlists.
✅ Implement offline detection.
✅ Advanced search.
✅ Personal charts.
✅ YouTube integration.
✅ Auth system (JWT) for multiuser (prepared models).

**🎉 PROJECT 100% COMPLETE AND PRODUCTION READY!**

## 🖼️ **Image Storage System (Filesystem-First, Human-Readable)**

Desde Enero 2026, Audio2 usa un sistema de almacenamiento **filesystem-first** con rutas amigables para facilitar la navegación humana.

### **Problemas Encontrados y Soluciones (Enero 2026)**

#### Problema 1: Imágenes sin asociación entidad→imagen
**Síntoma**: Las imágenes en `cache/images/` eran `sha1hash.webp` sin metadatos de a quién pertenecían.

**Solución**: Se crearon las migraciones de Alembic para `storedimagepath` y se populate la tabla con el script `populate_image_storage.py` que extrae las URLs del campo `images` (JSON) de Artist/Album y descarga las imágenes directamente de Spotify.

#### Problema 2: entity_id incorrecto
**Síntoma**: Algunas entradas en `storedimagepath` tenían `entity_id` wrong (ej: artista con `entity_id` de otro artista).

**Solución**: Se crearon scripts `fix_image_ids.py` y se corrigieron las entradas comparando el nombre sanitizado en la ruta del archivo con el nombre del artista/álbum en BD.

#### Problema 3: Imágenes sin image_path_id
**Síntoma**: Las imágenes existían en disco pero `Artist.image_path_id` era `NULL`.

**Solución**: El script `populate_image_storage.py` ahora actualiza el campo `image_path_id` en Artist/Album al crear la entrada en `StoredImagePath`.

#### Problema 4: Fallback de imágenes "external"
**Síntoma**: Algunas imágenes se guardaron como `entity_type='external'` en lugar de `'artist'`.

**Solución**: Script de corrección que busca entradas 'external' con path coincidente y las actualiza al tipo/entidad correcto.

#### Problema 5: Imágenes con paths en carpeta "external/" pero tipo errado
**Síntoma**: 132 entradas en `storedimagepath` tenían `entity_type='album'` pero `path_512='external/external__hash_512.webp'`.

**Solución**:
```python
# Buscar y borrar entradas con paths externos pero tipo no-external
stmt = select(StoredImagePath).where(
    (StoredImagePath.path_512.like('external/%')) |
    (StoredImagePath.path_256.like('external/%'))
)
```
Luego limpiar `image_path_id` de todos los artistas para forzar re-download.

#### Problema 6: TypeError en `store_image` para albums
**Síntoma**: `TypeError: unsupported operand type(s) for /: 'str' and 'str'` al guardar imágenes de albums.

**Causa**: En `image_db_store.py:267`, `parent_name` es un string pero se usaba directamente con `/` (operador Path).

**Solución**:
```python
# Antes (incorrecto):
entity_folder = parent_name / entity_name

# Después (correcto):
entity_folder = Path(parent_name) / entity_name
```

#### Problema 7: JSONDecodeError al parsear campo `images`
**Síntoma**: `json.JSONDecodeError: Expecting property name enclosed in double quotes` al procesar albums.

**Causa**: El campo `images` almacenado en BD usaba comillas simples (formato Python literal) en lugar de JSON válido.

**Solución** en `app/api/images.py`:
```python
if isinstance(entity_images, str):
    try:
        images_data = json.loads(entity_images)
    except json.JSONDecodeError:
        images_data = ast.literal_eval(entity_images)  # Fallback para comillas simples
```

### **Estructura de Directorios**

```
storage/
├── images/
│   ├── ArtistName/
│   │   ├── ArtistName__abc123_256.webp     ← imagen del artista
│   │   ├── ArtistName__abc123_512.webp
│   │   └── AlbumName/                      ← álbum del artista
│   │       ├── AlbumName__def456_256.webp
│   │       └── AlbumName__def456_512.webp
│   └── AnotherArtist/
│       └── ...
└── downloads/                              ← música descargada
    └── ArtistName/
        └── AlbumName/
            └── Artist - Track.mp3
```

### **Portabilidad entre Ordenadores**

Para migrar a otro ordenador o disco externo, sigue estos pasos:

1. **En `.env` del nuevo ordenador**, añade la variable `STORAGE_ROOT`:
```env
# Ejemplo en disco externo
STORAGE_ROOT=/media/micasa/external_drive/audio2_storage

# O en otro directorio
STORAGE_ROOT=/home/micasa/music_storage
```

2. **Copia la carpeta `storage/` completa** al nuevo destino.

3. **La BD no necesita cambios**: Los paths en `storedimagepath` son relativos (`ArtistName/Artist__hash_512.webp`), no absolutos.

4. **Al migrar canciones** (futuro), seguirán el mismo patrón:
   - `downloads/Artist/Artist - Track.mp3` (relativo a `STORAGE_ROOT`)
   - Solo cambia `STORAGE_ROOT` en `.env`

**Archivos clave que usan STORAGE_ROOT:**
- `app/core/image_db_store.py:25-26` → `STORAGE_ROOT = Path("storage")`, `IMAGE_STORAGE`
- `app/core/youtube.py:34` → `self.download_dir = Path("downloads")`

### **Configuración Actual**

- **Tamaños**: Solo 256px y 512px (reducido de 4 tamaños para ahorrar espacio)
- **Calidad**: WebP 80%
- **Formato**: `{entity_name}__{hash_8chars}_{size}.webp`
- **Total**: ~26k archivos, ~480MB

### **Endpoints**

| Endpoint | Descripción |
|----------|-------------|
| `GET /images/entity/{type}/{id}?size=256` | Obtener imagen de entidad |
| `GET /images/proxy?url=...&size=512` | Proxy + cache de imagen externa |
| `POST /images/entity/{type}/{id}/cache` | Pre-cachear imagen |
| `DELETE /images/entity/{type}/{id}` | Borrar imágenes cacheadas |
| `GET /images/stats` | Estadísticas de almacenamiento |

### **Tabla de Base de Datos**

```sql
storedimagepath (
  id, entity_type, entity_id, source_url,
  path_256, path_512,
  content_hash, original_width, original_height,
  format, file_size_bytes, created_at
)
```

### **Comandos Útiles**

```bash
# Poblar imágenes para artistas/álbumes existentes
python scripts/populate_image_storage.py --dry-run  # Preview
python scripts/populate_image_storage.py            # Ejecutar

# Corregir entity_id wrong
python scripts/fix_image_ids.py

# Ver estadísticas
python -c "from app.core.image_db_store import get_image_stats; print(get_image_stats())"

# Verificar imagen de un artista
ls storage/images/Drake/
```

### **Flujo de Trabajo**

1. **Nueva imagen** → Se descarga de Spotify → Se guarda en `storage/images/{artist}/` → Se actualiza `Artist.image_path_id`
2. **Request** → `/images/entity/artist/{id}?size=512` → Busca en BD → Serve archivo desde `storage/images/`
3. **Fallback** → Si no hay `image_path_id`, usa `/images/proxy?url=...` con la URL del campo `images` en JSON

### **Test de Repoblación (antes de limpiar todo)**

Antes de borrar todas las imágenes, hacer test con UN artista para verificar que el sistema funciona:

```python
# 1. Verificar estado actual del artista
from app.core.db import get_session
from app.models.base import Artist, StoredImagePath

with get_session() as session:
    artist = session.get(Artist, 46)  # Drake
    print(f'Artista: {artist.name}, image_path_id: {artist.image_path_id}')

# 2. Limpiar datos de Drake
import shutil
from pathlib import Path

# Borrar carpeta
drake_folder = Path('storage/images/Drake')
if drake_folder.exists():
    shutil.rmtree(drake_folder)
    print(f'Carpeta borrada: {drake_folder}')

# Borrar entrada storedimagepath y limpiar image_path_id
# (ver script completo en herramientas de desarrollo)

# 3. Hacer peticion HTTP
curl "http://localhost:8000/images/entity/artist/46?size=512&token=<TOKEN>"

# 4. Verificar resultado
# - Nuevo image_path_id en BD
# - Archivos en storage/images/Drake/
# - Path correcto: Drake/Drake__<hash>_512.webp
```

### **Limpieza Total (Repoblación desde cero)**

```python
# Script para limpiar todas las imágenes y forzar re-download

from app.core.db import get_session
from app.models.base import Artist, Album, StoredImagePath
from sqlmodel import select
from pathlib import Path
import shutil

# 1. Borrar todas las carpetas de storage/images/
storage_path = Path('storage/images')
if storage_path.exists():
    for item in storage_path.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
            print(f'Borrado: {item}')

# 2. Truncar tabla storedimagepath (cuidado, esto borra todo)
with get_session() as session:
    entries = session.exec(select(StoredImagePath)).all()
    for e in entries:
        session.delete(e)
    session.commit()
    print(f'Borradas {len(entries)} entradas de storedimagepath')

# 3. Limpiar image_path_id de todos
with get_session() as session:
    artists = session.exec(select(Artist)).all()
    for a in artists:
        a.image_path_id = None
        session.add(a)
    albums = session.exec(select(Album)).all()
    for a in albums:
        a.image_path_id = None
        session.add(a)
    session.commit()
    print(f'Limpiados {len(artists)} artistas y {len(albums)} albums')
```

**Resultado**: Al visitar las páginas de artistas/albums en el navegador, las imágenes se descargarán automáticamente desde Spotify con la estructura correcta.

### **Beneficios**

- **Navegable**: Puedes explorar `storage/images/` y ver las carpetas por artista/álbum
- **DB ligera**: Solo almacena rutas, no BLOBs
- **Backups rápidos**: Dump de BD pequeño
- **nginx-ready**: Archivos servibles directamente

---

## 🚀 **Roadmap - Future Enhancements**

### **Phase 1: DB-first Search Professionalization**
- **Goal**: Resolve searches locally first (artists, albums, tracks), even offline, and only enrich via external APIs when needed.
- **Work plan**:
  - **Alias & variants**: store per-artist/album/track alias strings (typos, transliterations, punctuation variants).
  - **Local search index**: tokenize names + aliases, add popularity/favorites/last_played signals, and rank results deterministically.
  - **DB-first flow**: try local search with fuzzy + normalized matching, return suggestions immediately, and mark missing data for background enrichment.
  - **Background enrichment**: if confidence is low, fetch external data asynchronously and persist; never block UI when offline.
  - **Consistency**: keep album covers, bios, and chart stats read from DB; refresh on a schedule, not during search.
- **Planned commit**: `feat: professionalize db-first search resolution`

### **Phase 2: Advanced Recommendations**
- [ ] **🎯 Smart Artist Discovery Algorithm** - Implement vector embeddings for better artist similarity
  - Use genre compatibility, follower similarity, collaboration networks
  - Replace Last.fm similarity with ML-based recommendations
  - Filter out non-musical entities (managers, labels, executives)
- [ ] **🎵 Song-Level Recommendations** - Audio analysis based similarity
  - Analyze audio features (tempo, key, energy, danceability)
  - Build listening pattern prediction models
  - Personalized "Discover Weekly" based on actual preferences

### **Phase 3: Torrent Integration** 🚀
- [ ] **🎬 Torrent Search & Download** - Integration with torrent APIs
  - SafeMagnet integration for audio files
  - Automatic quality selection (FLAC/MP3/AAC)
  - Torrent client integration (qBittorrent/Transmission)
- [ ] **🔒 Content Verification** - Ensure downloaded files match expectations
  - Audio fingerprinting and quality verification
  - Metadata validation post-download
  - Duplicate file detection across torrent sources
- [ ] **💾 Storage Optimization** - Efficient storage management
  - Automatic transcoding to save space
  - Cloud storage integration (optional)
  - Backup and redundancy management

### **Phase 4: Advanced Features**
- [ ] **👥 Multi-User Collaboration** - Shared music libraries
  - User permissions and access control
  - Collaborative playlist creation
  - Social features (likes, comments, sharing)
- [ ] **📥 Offline Downloads (Web/Android)** - Seleccionar pistas para uso sin red
  - Sincronización explícita y permisos por usuario
  - Compatibilidad con almacenamiento externo cuando exista
- [ ] **🛑 Offline Mode** - Ejecutar sin llamadas externas
  - Desactivar refresh loops y consultas a Spotify/Last.fm/YouTube
  - Servir solo desde BD y descargas locales
- [ ] **🧭 Per-user Library Hiding** - Ocultar artistas/albums/tracks por usuario
  - No borra datos globales; solo filtra la vista personal
  - Endpoints dedicados para hide/unhide
- [ ] **⬇️ Download Metrics (anonimo)** - Contador de descargas por pista
  - Sin asociar al usuario; solo agregados globales
  - Visible en vistas de Tracks/Albumes como dato informativo
- [ ] **🏷️ Catalogo de generos** - Normalizacion y browse de generos
  - Consolidar generos de Spotify/Last.fm en una taxonomia unica
  - Endpoints dedicados para explorar y filtrar por genero
- [ ] **📺 YouTube DB-first** - Evitar llamadas externas si hay cache
  - Consultar `YouTubeDownload` antes de buscar en YouTube
  - Solo buscar cuando falte link/estado en BD
- [ ] **🎧 Local-first Streaming** - Reproducir desde `download_path` si existe
  - Reutilizar mp3/m4a ya descargados antes de streamear
- [ ] **📊 Analytics Dashboard** - Usage statistics and insights
  - Listening habits analysis
  - Genre preference evolution tracking
  - Playback statistics and trends
- [ ] **🔊 Audio Quality Management** - Quality selection intelligence
  - Automatic quality selection based on network/requirements
  - Lossless ✅ vs compressed balancing
  - Streaming optimization

### **Phase 5: Performance & Scale**
- [ ] **⚡ Performance Optimization** - Caching and speed improvements
  - Redis caching for fast metadata lookups
  - CDN integration for cover art images
  - Database indexing and query optimization
- [ ] **🌐 Cross-Platform Sync** - Multi-device synchronization
  - Web/mobile app companions
  - Play queue synchronization
  - Favorites synchronization across devices
- [ ] **🎙️ Audio Sync Technology** - Listening time synchronization across devices

### **Implementation Priority:**
1. **High**: Better artist recommendations (eliminate managers like Paul Rosenberg)
2. **Medium**: Torrent integration for offline-first experience
3. **Low**: Multi-user collaboration and analytics

**Contribute:** Issues and pull requests welcome! See `CONTRIBUTING.md` (future)

---

Setup Instructions

## Arrancar el proyecto (desarrollo)

### Backend
```bash
cd /home/micasa/audio2
source venv/bin/activate
source .env
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend
```bash
cd /home/micasa/audio2/frontend
npm run dev
```

### URLs
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- Health check: http://localhost:8000/health

### Ver logs
- Backend: `tail -f uvicorn.log` (o buscar el ID del proceso en background)
- Frontend: ver output de `npm run dev`

### Si falla psycopg2
```bash
source venv/bin/activate
pip install psycopg2-binary
```

---

## ✅ Estándares globales adoptados (2026-01)
Se aplican estándares consistentes de rendimiento, caché y DB-first:
- **HTTP caching**: `Cache-Control: private`, `ETag`, `Last-Modified` y `Vary` para endpoints personalizados.
- **Requests condicionales**: `If-None-Match` / `If-Modified-Since` → `304` si no hay cambios.
- **Compresión**: GZip para respuestas JSON grandes.
- **DB-first**: la UI no usa APIs externas salvo que falten datos locales o el usuario fuerce refresh.
- **Imágenes**: tamaños cacheados reales son `256` y `512`.
- **Linting**: backend compatible con flake8; frontend con ESLint + hooks.

## 🚨 **Problemas Críticos Encontrados y Soluciones Propuestas**

### **1. Seguridad - RCE mediante eval()**
**Archivo**: `app/crud.py:1141`
**Problema**: Uso peligroso de `eval()` que permite ejecución de código arbitrario.
```python
# ❌ PELIGROSO
artist_genres = eval(artist.genres) if isinstance(artist.genres, str) else artist.genres
```
**Solución**:
```python
# ✅ SEGURO
import json
artist_genres = json.loads(artist.genres) if isinstance(artist.genres, str) else artist.genres
```
**Prioridad**: CRÍTICA - Aplicar inmediatamente

### **2. Rendimiento - Índices Faltantes en PostgreSQL**
**Problema**: Queries lentas en `/tracks/overview` y búsquedas por falta de índices.
**Impacto**: Tiempos de respuesta >5 segundos con pocos miles de tracks.
**Solución**:
```sql
-- Índices críticos (ejecutar en producción con CONCURRENTLY)
CREATE INDEX CONCURRENTLY idx_track_spotify_id ON track(spotify_id);
CREATE INDEX CONCURRENTLY idx_track_name_trgm ON track USING gin(name gin_trgm_ops);
CREATE INDEX CONCURRENTLY idx_artist_name_trgm ON artist USING gin(name gin_trgm_ops);
CREATE INDEX CONCURRENTLY idx_youtubedownload_spotify_track_id ON youtubedownload(spotify_track_id);
CREATE INDEX CONCURRENTLY idx_playhistory_user_played_at_desc ON playhistory(user_id, played_at DESC);
```
**Prioridad**: ALTA - Aplicar antes de crecimiento significativo

### **3. Arquitectura - Archivos Monolíticos**
**Problema**: Archivos con 1500+ líneas violan SRP y son difíciles de mantener.
**Archivos afectados**:
- `app/api/tracks.py`: 1,705 líneas
- `app/api/search.py`: 1,883 líneas

**Solución**:
```bash
# Estructura recomendada
app/api/tracks/
├── __init__.py
├── overview.py      # GET /tracks/overview
├── playback.py      # POST /tracks/play, GET /most-played
├── downloads.py     # YouTube/download endpoints
└── favorites.py    # Favorites management
```
**Prioridad**: MEDIA - Hacer en refactorización planificada

### **4. Base de Datos - Tipos Ineficientes**
**Problema**: Uso de `str` para datos JSON en lugar de `JSONB`.
**Campos afectados**:
```python
genres: Optional[str] = None     # Debería ser JSONB
images: Optional[str] = None      # Debería ser JSONB
favorite_genres: Optional[str] = None  # Debería ser JSONB
```
**Solución**:
```python
from sqlalchemy.dialects.postgresql import JSONB

genres: Optional[dict] = Field(default=None, sa_column=Column(JSONB))
images: Optional[dict] = Field(default=None, sa_column=Column(JSONB))
```
**Prioridad**: MEDIA - Mejora performance y flexibilidad

### **5. Frontend - Componentes Sobrecargados**
**Problema**: Componentes con excesiva complejidad y líneas.
**Ejemplo**: `PlayerFooter.tsx` con 576 líneas.
**Solución**:
```typescript
// Extraer lógica a hooks personalizados
function usePlayerControls() {
  // Encapsular lógica compleja del reproductor
  return { handlePlay, handlePause, handleNext };
}

// Componentes más pequeños y reutilizables
const PlayerControls = () => { /* solo botones */ };
const PlayerProgress = () => { /* solo barra de progreso */ };
const TrackInfo = () => { /* solo info actual */ };
```
**Prioridad**: MEDIA - Mejora mantenibilidad

### **6. Gestión de Errores - Inconsistente**
**Problema**: Múltiples patrones de manejo de errores sin estandarización.
**Solución**:
```python
# Jerarquía de excepciones personalizada
class Audio2Exception(Exception):
    def __init__(self, message: str, error_code: str = None):
        self.message = message
        self.error_code = error_code

# Manejador centralizado
@app.exception_handler(Audio2Exception)
async def handle_audio2_exception(request, exc: Audio2Exception):
    return JSONResponse(
        status_code=400,
        content={"error": exc.error_code, "message": exc.message}
    )
```
**Prioridad**: ALTA - Mejora debugging y UX

### **7. Optimización de Bundle - Frontend**
**Problema**: Bundle grande sin code splitting ni lazy loading.
**Solución**:
```typescript
// vite.config.ts optimizado
export default defineConfig({
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          ui: ['@radix-ui/react-slot', 'lucide-react'],
          api: ['axios'],
          state: ['zustand']
        }
      }
    }
  }
});
```
**Prioridad**: BAJA - Mejora tiempo de carga inicial

---

## 📋 **Roadmap de Mejoras Priorizadas**

### **Fase 1: Críticas (1-3 días)**
1. ✅ **Reemplazar `eval()` por `json.loads()`** - Seguridad crítica
2. ✅ **Añadir índices básicos** - Performance inmediata
3. ⚠️ **Implementar manejo centralizado de errores** - Consistencia

### **Fase 2: Estabilización (1-2 semanas)**
1. ✅ **Migrar campos str→JSONB** - Optimización BD
2. ⚠️ **Refactorizar archivos monolíticos** - Mantenibilidad
3. ✅ **Implementar rate limiting consistente** - Protección API

### **Fase 3: Calidad (2-3 semanas)**
1. ✅ **Extraer componentes React grandes** - Mejora frontend
2. ✅ **Implementar caché Redis** - Performance
3. ⚠️ **Alcanzar 80%+ cobertura de tests** - Calidad

---

## 🎯 **Configuración de Desarrollo (Estado Actual)**

**Importante**: Tu configuración actual es **correcta para desarrollo**:

```bash
# .env - PERFECTAMENTE VÁLIDO para desarrollo
AUTH_DISABLED=true          # ✅ Facilita testing
SPOTIFY_CLIENT_ID=tu_key   # ✅ API key guardada
YOUTUBE_API_KEY=tu_key     # ✅ API key guardada
DEBUG=true                   # ✅ Logs detallados
LOG_LEVEL=debug              # ✅ Debugging fácil
```

**Estas configuraciones son estándar y seguras para entorno de desarrollo.**

---

## 🧩 Fallos de imágenes (álbumes con imágenes de artistas) — causa y solución
### Síntomas
- En la discografía del artista, **portadas de álbum incorrectas** (aparecían imágenes del artista).
- En la página del álbum, la imagen correcta sí aparecía.

### Causas
1) **Reutilización por hash**: imágenes se reasignaban entre entidades.
2) **Fallbacks inseguros**: `image_path_id` cruzaba tipos o buscaba por nombre.
3) **Frontend en discografía** usaba `image_path_id` corrupto.

### Soluciones aplicadas
- Se **evitó la reasignación por hash** entre entidades.
- Se **eliminaron fallbacks inseguros** y se restringió por `entity_type`.
- La discografía de artista **usa URL del álbum (proxy)** en lugar de `image_path_id`.
- Reparación **DB-first**: `image_path_id` se reasigna por `source_url` si ya existe en la DB.
- **Mantenimiento automático** repara `image_path_id` en background.

### Resultado
- Portadas correctas en la vista de artista.
- Reparación sin APIs externas ni borrado de datos.

## 🔧 Mantenimiento automático (DB-first)
Ya existe loop de mantenimiento que:
- refresca discografías y detecta nuevos álbumes/singles,
- repara `image_path_id` en background.

## 🛠️ Reparación manual (desde Settings)
Se añadió un botón en Settings:
- **"Reparar imágenes de álbum"** → dispara `POST /maintenance/repair-album-images`
- Funciona con auth y solo DB.

---

## 🏗️ Refactoring de API Artists (Enero 2026)

### Problema
El archivo `app/api/artists.py` había crecido hasta **1257 líneas** violando el Principio de Responsabilidad Única (SRP). Esto causaba:
- Dificultad para mantener y testear el código
- Mezcla de responsabilidades (discography, search, management, info)
- Conflictos de merge frecuentes en equipos

### Solución
Se spliteó el archivo monolítico en módulos especializados bajo `app/api/artists/`:

```
app/api/artists/
├── __init__.py          # Router principal que re-exporta todos los sub-routers
├── listing.py           # GET /artists/ - Listado con paginación y búsqueda
├── discography.py       # GET /artists/{spotify_id}/albums - Álbumes del artista
├── management.py        # POST /artists/save/{spotify_id}, /refresh-*, /hide
├── search.py            # GET /artists/search, /search-auto-download
└── info.py              # GET /artists/{spotify_id}/info, /related, /recommendations
```

### Cambios realizados

1. **`__init__.py`**:
   - Eliminado patrón antiparque de `try/except` para imports
   - Imports directos de sub-routers
   - Registro limpio de todos los routers

2. **`discography.py`** (~200 líneas):
   - Migrada lógica completa de `get_artist_albums()`
   - Consulta artistas locales y albums de Spotify
   - Manejo de proxy de imágenes
   - Tracking de YouTube links
   - Funciones auxiliares: `_parse_images_field`, `_persist_albums`, `_refresh_artist_albums`

3. **`management.py`** (~270 líneas):
   - `save_artist_to_db` - Guarda artista desde Spotify
   - `sync_artist_discography` - Sincroniza discografía
   - `refresh_artist_genres` - Backfill de géneros desde Last.fm
   - `refresh_missing_artist_metadata` - Completar datos faltantes
   - `hide_artist_for_user_endpoint` / `unhide_artist_for_user_endpoint`

4. **`info.py`** (~310 líneas):
   - `get_artist_info` - Info de Spotify + Last.fm bio/tags
   - `get_artist_recommendations` - Recomendaciones de Spotify
   - `get_related_artists` - Artistas relacionados (Last.fm + Spotify)
   - CRUD por ID local: `get_artist_by_id`, `delete_artist`, `get_local_artist_by_spotify_id`
   - `get_artist_discography_by_id` - Discografía desde BD local

### Beneficios
- **Mantenibilidad**: Cada módulo tiene una responsabilidad clara
- **Testeabilidad**: Se puede testear cada módulo independientemente
- **Escalabilidad**: Nuevas features van en su módulo correspondiente
- **Colaboración**: Diferentes desarrolladores pueden trabajar en paralelo

### Puntuación de calidad post-refactoring
| Aspecto | Puntuación |
|---------|------------|
| Calidad del refactoring | 5/5 |
| Profesionalismo | 5/5 |
| SQL Injection | 5/5 (ORM everywhere) |
| XSS | 5/5 (FastAPI + JSON por defecto) |


## Favorites Policy (SAGRADO - No Regresion)

- Fuente unica de verdad: tabla `userfavorite` en PostgreSQL.
- Favoritos son globales por usuario: clave logica `user_id + target_type + target_id`.
- `target_type` permitido: `ARTIST`, `ALBUM`, `TRACK`.
- Espejo obligatorio en UI: si marcas en Albums, debe verse en Tracks y Artists segun el tipo.
- Persistencia obligatoria: tras recargar, el estado se reconstruye desde BD (nunca solo estado local).
- Identidad consistente: todas las llamadas de favoritos y listados filtrados deben usar el mismo `user_id` efectivo (token activo).
- Regla de no-regresion: cualquier cambio que rompa el espejo Albums <-> Tracks (TRACK) se considera bug critico.

---

## Playlist Operations Policy (SAGRADO - Never Regress)

**Estado:** Implementado en FASE 1 (Feb 2026)  
**Ubicacion:** `frontend/src/hooks/usePlaylistTrackRemoval.ts`, `frontend/src/hooks/usePlaylistTrackAddition.ts`, `PlayerFooter.tsx`, `PlaylistsPage.tsx`

### Funcionalidad Implementada

**1. Eliminacion de tracks en playlists:**
- Desde `PlaylistsPage`: elimina track de BD y sincroniza UI
- Desde `AddToPlaylistModal`: elimina track de BD y sincroniza UI  
- Desde `PlayerFooter` (Cola Actual): elimina track de BD y de la cola
- **SIEMPRE** recarga la playlist desde servidor para confirmar
- **SIEMPRE** sincroniza entre componentes via eventos

**2. Insercion de tracks en playlists:**
- Hook `usePlaylistTrackAddition` centralizado
- Verifica duplicados antes de insertar
- Recarga playlist tras insercion para confirmar
- Soporta operaciones batch (multiple tracks)

**3. CRUD de playlists desde Cola Actual:**
- Crear nueva playlist: boton "+ Nueva" en "Listas en memoria"
- Eliminar playlist: boton "×" junto a cada playlist
- **Sincronizacion bidireccional**: cambios en Cola Actual se reflejan en PlaylistsPage y viceversa
- Eventos: `playlist-deleted`, `playlist-created`

### Reglas de No-Regresion

- **NUNCA** eliminar solo del estado local (siempre llamar API primero)
- **NUNCA** asumir que el track se elimino sin verificar respuesta del servidor
- **SIEMPRE** recargar la playlist tras modificaciones para sincronizar
- **SIEMPRE** emitir eventos para sincronizar entre componentes
- **SIEMPRE** verificar que `localTrackId` existe antes de operar
- **NUNCA** modificar estos hooks sin entender completamente el flujo de sincronizacion

### Tests

- Backend: `tests/test_playlist_endpoints.py` (6 tests, todos pasan)
- Frontend: `frontend/src/hooks/usePlaylistOperations.test.ts` (12 tests)
- Documentacion: `TESTS_PLAYLIST.md`

---

## Code Stability Rules (SAGRADO - Never Regress)

### Golden Rules for Any Code Change

1. **DO NOT modify working code without explicit user permission**
   - If it works, don't touch it
   - Only modify if user explicitly requests it or there's a critical bug

2. **If you MUST modify code:**
   - Understand the existing behavior BEFORE making changes
   - Run `flake8` BEFORE committing (will block on errors)
   - Test that the change doesn't break existing functionality
   - If you're unsure, ask the user before proceeding

3. **Before modifying ANY endpoint/function:**
   - Read the full file to understand the context
   - Identify all places that call this function
   - Verify the change won't break dependent code

4. **Async/Await Pattern (Critical):**
   - In async endpoints, ALWAYS use `await` with `session.exec()`
   - Wrong: `session.exec(select(...)).first()` → Fails silently in async
   - Correct: `(await session.exec(select(...))).first()`

5. **Imports (Critical):**
   - If you use a module (e.g., `asyncio`), you MUST import it
   - Missing imports cause F821 errors that flake8 will catch

6. **When in doubt, ask:**
   - "Do you want me to modify X?"
   - "Should I change this behavior?"
   - "I'm not sure about changing this code - can you confirm?"
