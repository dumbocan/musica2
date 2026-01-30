"""
Refresh search alias variants using the latest heuristics.
"""

from sqlmodel import select

from app.core.db import get_session
from app.core.search_index import ensure_entity_aliases
from app.models.base import Artist, Album, Track, SearchEntityType


def _refresh_aliases(session, model, entity_type):
    rows = session.exec(select(model)).all()
    count = 0
    for entity in rows:
        aliases_added = ensure_entity_aliases(session, entity_type, entity.id, entity.name)
        count += aliases_added
    session.commit()
    return count


def main():
    with get_session() as session:
        artists = _refresh_aliases(session, Artist, SearchEntityType.ARTIST)
        albums = _refresh_aliases(session, Album, SearchEntityType.ALBUM)
        tracks = _refresh_aliases(session, Track, SearchEntityType.TRACK)
    print(f"Aliases updated: artists={artists}, albums={albums}, tracks={tracks}")


if __name__ == "__main__":
    main()
