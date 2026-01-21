"""
Backfill search aliases for existing artists, albums, and tracks.
Idempotent: only inserts missing aliases.
"""

import argparse

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import func
from app.core.db import create_db_and_tables, get_session
from app.core.search_index import generate_aliases, normalize_search_text
from app.core.time_utils import utc_now
from sqlmodel import select

from app.models.base import Artist, Album, Track, SearchAlias, SearchEntityType


def _backfill_for_model(
    session,
    model,
    entity_type: SearchEntityType,
    batch_size: int,
    max_batches: int | None = None,
) -> int:
    total_candidates = 0
    last_id = 0
    batches = 0
    while True:
        rows = session.exec(
            select(model)
            .where(model.id > last_id)
            .order_by(model.id)
            .limit(batch_size)
        ).all()
        if not rows:
            break
        alias_rows = []
        seen = set()
        now = utc_now()
        for row in rows:
            for alias in generate_aliases(row.name):
                normalized = normalize_search_text(alias)
                if not normalized:
                    continue
                key = (row.id, normalized)
                if key in seen:
                    continue
                seen.add(key)
                alias_rows.append({
                    "entity_type": entity_type,
                    "entity_id": row.id,
                    "alias": alias,
                    "normalized_alias": normalized,
                    "source": "system",
                    "created_at": now,
                })
        if alias_rows:
            stmt = insert(SearchAlias).values(alias_rows)
            stmt = stmt.on_conflict_do_nothing(
                index_elements=["entity_type", "entity_id", "normalized_alias"]
            )
            result = session.exec(stmt)
            total_candidates += len(alias_rows)
        last_id = rows[-1].id
        session.commit()
        batches += 1
        if max_batches is not None and batches >= max_batches:
            break
    return total_candidates


def backfill_aliases(batch_size: int = 500, max_batches: int | None = None) -> None:
    create_db_and_tables()
    session = get_session()
    try:
        total_candidates = 0
        total_candidates += _backfill_for_model(session, Artist, SearchEntityType.ARTIST, batch_size, max_batches)
        total_candidates += _backfill_for_model(session, Album, SearchEntityType.ALBUM, batch_size, max_batches)
        total_candidates += _backfill_for_model(session, Track, SearchEntityType.TRACK, batch_size, max_batches)
        total_rows = session.exec(select(func.count()).select_from(SearchAlias)).one()
        print(f"Backfill completed. Alias candidates processed: {total_candidates}.")
        print(f"Total aliases in table: {total_rows}.")
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill search aliases.")
    parser.add_argument("--batch-size", type=int, default=500, help="Rows per batch.")
    parser.add_argument("--max-batches", type=int, default=None, help="Max batches per entity (optional).")
    args = parser.parse_args()
    backfill_aliases(batch_size=args.batch_size, max_batches=args.max_batches)
