# Audio2 AI - Sistema de Inteligencia Musical

Sistema de playlists inteligentes, recomendaciones y análisis usando LLM local (Ollama).

---

## Inicio Rápido - Arrancar Todo

Copia y ejecuta estas líneas en orden:

```bash
# 1. TERMINAL 1 - Arrancar Ollama (IA)
# Si no está corriendo:
ollama serve &

# 2. TERMINAL 2 - Arrancar Backend
cd /home/micasa/audio2
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 3. TERMINAL 3 - Arrancar Frontend (opcional)
cd /home/micasa/audio2/frontend
npm run dev
```

### Verificar que funciona

```bash
# Verificar Ollama
curl http://localhost:11434/api/version

# Verificar Backend AI
curl http://localhost:8000/ai/health
```

---

## Requisitos

### Hardware
- **RAM**: Mínimo 4GB (recomendado 8GB+)
- **CPU**: Procesador compatible con x86_64 o ARM64
- **Almacenamiento**: ~3GB para el modelo Llama-3.2-3B

### Software
- Python 3.10+
- PostgreSQL (base de datos existente de audio2)
- Ollama (se instala con el script)

## Instalación

### 1. Instalar Ollama

Ejecuta el script de instalación:

```bash
bash setup_ollama.sh
```

El script:
- Detecta tu sistema operativo (Linux/macOS/WSL)
- Instala Ollama automáticamente
- Descarga el modelo Llama-3.2-3B
- Verifica que el servicio esté corriendo
- Hace un test de conexión

### 2. Verificar la instalación

```bash
# Verificar que Ollama está corriendo
curl http://localhost:11434/api/version

# Verificar que el modelo está disponible
ollama list
```

Deberías ver:
```json
{"version":"0.x.x"}
```

Y el modelo `llama3.2:3b` en la lista.

### 3. Iniciar el servicio (si no está corriendo)

```bash
# En Linux con systemd
sudo systemctl start ollama
sudo systemctl enable ollama

# En macOS
brew services start ollama

# Manual (cualquier sistema)
ollama serve
```

## Uso de los Endpoints

### Verificar estado del servicio

```http
GET /ai/health
```

Response:
```json
{
    "available": true,
    "ollama": {
        "version": "0.5.4",
        "model": "llama3.2:3b"
    },
    "message": "El servicio de IA está disponible"
}
```

### Generar Playlist por Mood

Genera una playlist basada en un mood o contexto específico.

```http
POST /ai/generate-playlist
Content-Type: application/json

{
    "mood": "fiesta",
    "num_tracks": 20,
    "language": "español"
}
```

**Moods de ejemplo:**
- `fiesta` - Música upbeat, dance, alta energía
- `trabajar` - Música para focus, instrumental
- `triste` - Melanchólica, ballads
- `entrenar` - Alta energía, motivacional
- `relajar` - Calmada, acoustic
- `romantico` - Love songs, slow jams
- `viaje` - Road trip vibes
- `madrugada` - Electronic, chill

**Response:**
```json
{
    "success": true,
    "playlist": {
        "name": "Fiesta Energética",
        "description": "Playlist para una fiesta con los mejores hits",
        "mood": "fiesta",
        "tracks": [
            {
                "id": 123,
                "title": "Dancing Queen",
                "artist": "ABBA",
                "reason": "Clásico disco perfecto para animar la fiesta"
            },
            ...
        ],
        "notes": "Mezcla de clásicos y modernos para mantener la energía"
    }
}
```

### Crear Playlist en Base de Datos

Toma los tracks de una respuesta AI y los guarda como playlist real:

```http
POST /ai/create-playlist-from-ai
Content-Type: application/json

{
    "playlist_name": "Mi Playlist AI",
    "playlist_description": "Generada por inteligencia artificial",
    "mood": "fiesta"
}
```

**Params query:**
- `user_id` (default: 1)
- `playlist_name` (default: "AI Generated Playlist")
- `playlist_description`

### Biografía de Artista

Genera una biografía atractiva basada en datos disponibles.

```http
POST /ai/artist-bio
Content-Type: application/json

{
    "artist_id": 42,
    "language": "español"
}
```

**Response:**
```json
{
    "success": true,
    "biography": {
        "name": "The Beatles",
        "biography": "The Beatles fueron una banda de rock inglesa...",
        "highlights": [
            "4 miembros icónicos",
            "Álbumes innovadores",
            "Influencia histórica"
        ],
        "recommended_for_fans_of": ["Rock clásico", "British Invasion"],
        "notable_facts": [
            "Más vendido de todos los tiempos",
            "Innovadores en estudio"
        ]
    }
}
```

### Resumen de Álbum

Genera un resumen/reseña de un álbum.

```http
POST /ai/album-summary
Content-Type: application/json

{
    "album_id": 156,
    "language": "español"
}
```

**Response:**
```json
{
    "success": true,
    "summary": {
        "album": "Dark Side of the Moon",
        "artist": "Pink Floyd",
        "summary": "Obra maestra conceptual que explora temas de...",
        "key_tracks": ["Time", "Money", "Us and Them"],
        "mood": "Contemplativo, oscuro, progresivo",
        "verdict": "Esencial para cualquier colección"
    }
}
```

### Recomendaciones Personalizadas

Obtén recomendaciones basadas en tu historial y preferencias.

```http
POST /ai/recommendations

{
    "num_recommendations": 10
}
```

**Response:**
```json
{
    "success": true,
    "recommendations": {
        "recommendations": [
            {
                "type": "track",
                "id": 789,
                "name": "Bohemian Rhapsody",
                "artist": "Queen",
                "reason": "Similar a tus favoritos de rock clásico",
                "confidence": 0.85,
                "based_on": "Top artists: Queen, The Beatles"
            },
            ...
        ],
        "insights": [
            "Tu género principal es Rock",
            "Prefieres artistas de los 70s"
        ]
    }
}
```

### Búsqueda Semántica

Busca canciones usando lenguaje natural. El LLM interpreta tu búsqueda.

```http
POST /ai/semantic-search

{
    "query": "música para un día triste",
    "limit": 10
}
```

**Queries de ejemplo:**
- `"música para un día triste"` → Canciones melancólicas, blues
- `"canciones para entrenar"` → Alta energía, motivacional
- `"música relajante para dormir"` → Chill, acoustic, slow
- `"rock clásico de los 80s"` → Rock oldies
- `"algo para concentrarme"` → Instrumental, ambient

**Response:**
```json
{
    "success": true,
    "results": {
        "query": "música para un día triste",
        "interpretation": "El usuario busca canciones melancólicas...",
        "matches": [
            {
                "id": 456,
                "title": "Hurt",
                "artist": "Johnny Cash",
                "match_score": 0.92,
                "match_reason": "Tema melancólico con letra reflexiva"
            },
            ...
        ],
        "suggested_mood_tags": ["sad", "melancholic", "reflective"]
    }
}
```

### Insights de Usuario

Analiza tus patrones de escucha.

```http
GET /ai/user-insights?days=30
```

**Params:**
- `days` (default: 30, rango: 7-365)

**Response:**
```json
{
    "success": true,
    "insights": {
        "period": "últimos 30 días",
        "summary": "Has escuchado principalmente rock y clásico...",
        "statistics": {
            "total_listening_time_hours": 45.5,
            "average_session_length": "45 minutos",
            "genres_explored": 8,
            "new_artists_discovered": 12
        },
        "patterns": [
            {
                "pattern": "Escuchas más música por la noche",
                "evidence": "70% de reproducciones entre 20:00-02:00",
                "suggestion": "Prueba playlists energéticas para tardes"
            }
        ],
        "trends": {
            "rising_genres": ["Indie", "Alternative"],
            "declining_genres": ["Pop"],
            "new_interests": ["K-Pop"]
        },
        "achievements": [
            "Descubriste 12 artistas nuevos",
            "Escuchaste 45+ horas de música"
        ],
        "recommendations_for_improvement": [
            "Explora más artistas de los géneros emergentes"
        ]
    }
}
```

## Ejemplo Completo: Flujo de Trabajo

```python
import requests

BASE_URL = "http://localhost:8000"

# 1. Verificar que AI está disponible
response = requests.get(f"{BASE_URL}/ai/health")
print(response.json())

# 2. Generar playlist para una fiesta
playlist_resp = requests.post(f"{BASE_URL}/ai/generate-playlist", json={
    "mood": "fiesta",
    "num_tracks": 25
})
playlist_data = playlist_resp.json()

if playlist_data["success"]:
    # 3. Crear playlist real en la base de datos
    create_resp = requests.post(
        f"{BASE_URL}/ai/create-playlist-from-ai",
        params={
            "playlist_name": "Fiesta del Viernes",
            "playlist_description": "Generada por AI"
        },
        json=playlist_data["playlist"]
    )
    print(create_resp.json())
```

## Troubleshooting

### Ollama no responde

```bash
# Verificar servicio
curl http://localhost:11434/api/version

# Ver logs (Linux con systemd)
journalctl -u ollama -f

# Reiniciar servicio
sudo systemctl restart ollama
```

### Error: "No hay suficientes datos"

Necesitas tener más actividad en tu biblioteca:
- Añade favoritos (artistas, canciones)
- Reproduce algunas canciones
- Valora canciones (1-5 estrellas)

### Respuestas lentas

El modelo 3B es ligero pero puede ser lento en hardware limitado:
- Espera hasta 2 minutos para respuestas completas
- Reduce `num_tracks` en playlists
- Usa menos días en `user-insights`

### Error de memoria

Si Ollama consume mucha memoria:
```bash
# Verificar memoria disponible
free -h

# Reiniciar Ollama
sudo systemctl restart ollama
```

### El modelo no se descarga

```bash
# Descargar manualmente
ollama pull llama3.2:3b

# Verificar modelo
ollama list
```

## Arquitectura

```
PostgreSQL → Backend (FastAPI) → Ollama (Llama-3.2-3B) → JSON estructurado
    ↑                                              ↓
    └───────────── Datos del usuario ←─────────────┘
```

- **PostgreSQL**: Almacena favoritos, historial, metadatos
- **Backend**: Extrae datos, construye prompts, parsea respuestas
- **Ollama**: Procesa prompts, genera respuestas inteligentes
- **JSON**: Formato estructurado para consumo en frontend

## Limitaciones

1. **Modelo liviano**: 3B parámetros = respuestas más simples
2. **Sin fine-tuning**: Usa RAG + System Prompts
3. **Sin internet**: Todo corre localmente
4. **Contexto limitado**: Máximo ~2000 tokens de contexto

## Seguridad

- El LLM nunca accede directamente a PostgreSQL
- Backend controla qué datos envía al LLM
- Prompts especializados previenen inyecciones
- Respuestas siempre en JSON estructurado

## Configuración Avanzada

### Cambiar modelo

Edita `app/services/ollama_service.py`:

```python
@dataclass
class OllamaConfig:
    model: str = "tu-modelo:version"  # Cambiar aquí
```

Modelos alternativos más pequeños:
- `phi3:3.8b` (~2.4GB)
- `gemma:2b` (~2GB)

### Ajustar temperatura

Para respuestas más deterministas (menos creatividad):

```python
response = ollama_client.generate(
    prompt=...,
    temperature=0.3  # 0.0 = más determinista, 1.0 = más creativo
)
```

## Contribuir

1. Mejora los system prompts en `app/utils/prompts.py`
2. Añade nuevos tipos de análisis
3. Optimiza prompts para mejor rendimiento
4. Mejora el manejo de errores

## Licencia

Este módulo es parte de audio2 y usa la misma licencia.


## Favorites Policy (SAGRADO - No Regresion)

- Fuente unica de verdad: tabla `userfavorite` en PostgreSQL.
- Favoritos son globales por usuario: clave logica `user_id + target_type + target_id`.
- `target_type` permitido: `ARTIST`, `ALBUM`, `TRACK`.
- Espejo obligatorio en UI: si marcas en Albums, debe verse en Tracks y Artists segun el tipo.
- Persistencia obligatoria: tras recargar, el estado se reconstruye desde BD (nunca solo estado local).
- Identidad consistente: todas las llamadas de favoritos y listados filtrados deben usar el mismo `user_id` efectivo (token activo).
- Regla de no-regresion: cualquier cambio que rompa el espejo Albums <-> Tracks (TRACK) se considera bug critico.
