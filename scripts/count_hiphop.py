"""
Counts how many Spotify artists match our hip hop filter using the live API.
Run with: source venv/bin/activate && python scripts/count_hiphop.py
"""

import requests

BASE = "http://localhost:8000"

def search(term: str, limit: int = 50):
    resp = requests.get(f"{BASE}/search/spotify", params={"q": term, "limit": limit}, timeout=15)
    resp.raise_for_status()
    return resp.json().get("artists", [])

def matches_genre(artist):
    disallow = ['tamil', 'kollywood', 'tollywood', 'telugu', 'k-pop', 'kpop', 'pop']
    keywords = ['hip hop', 'hip-hop', 'rap', 'trap', 'boom bap', 'gangsta']
    genres = [g.lower() for g in artist.get("genres", [])]
    if not genres:
        return False
    if any(any(bad in g for bad in disallow) for g in genres):
        return False
    return any(any(key in g for key in keywords) for g in genres)

def main():
    term = "hip hop"
    artists = search(term, limit=50)
    total = len(artists)
    matched = [a for a in artists if matches_genre(a)]
    print(f"Queried {total} artists from Spotify for '{term}'")
    print(f"Matched hip hop filter: {len(matched)}")
    print("Top matched names:")
    for a in matched[:10]:
        print(f"- {a.get('name')} | followers: {a.get('followers',{}).get('total')} | genres: {', '.join(a.get('genres', []))}")

if __name__ == "__main__":
    main()
