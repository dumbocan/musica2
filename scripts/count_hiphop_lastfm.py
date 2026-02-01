"""
Cuenta artistas etiquetados como "hip hop" en Last.fm usando tag.getTopArtists.
Usa la API key de Last.fm desde la variable de entorno LASTFM_API_KEY.

Ejecuta:
  source venv/bin/activate && python scripts/count_hiphop_lastfm.py
"""

import os
import sys
import requests

API_KEY = os.environ.get("LASTFM_API_KEY")
TAG = "hip hop"

if not API_KEY:
    print("Falta LASTFM_API_KEY en el entorno")
    sys.exit(1)


def fetch_top_artists(tag: str, page: int = 1, limit: int = 50):
    url = "http://ws.audioscrobbler.com/2.0/"
    params = {
        "method": "tag.gettopartists",
        "tag": tag,
        "api_key": API_KEY,
        "format": "json",
        "page": page,
        "limit": limit,
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    artists = data.get("topartists", {}).get("artist", [])
    attrs = data.get("topartists", {}).get("@attr", {})
    return artists, attrs


def main():
    artists, meta = fetch_top_artists(TAG, page=1, limit=50)
    total = meta.get("total") or "?"
    total_pages = meta.get("totalPages") or "?"
    print(f"Tag: {TAG}")
    print(f"Total artistas (según Last.fm): {total} en {total_pages} páginas")
    print("Ejemplos:")
    for a in artists[:10]:
        name = a.get("name")
        listeners = a.get("listeners")
        print(f"- {name} ({listeners} listeners)")


if __name__ == "__main__":
    main()
