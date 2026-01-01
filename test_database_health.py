#!/usr/bin/env python3
"""Quick integrity test for the Audio2 database."""

from __future__ import annotations

from typing import Dict, Iterable, List, Sequence, Tuple

from sqlalchemy import func
from sqlmodel import Session, select

from app.core.db import create_db_and_tables, get_session
from app.models.base import (
    AlgorithmLearning,
    Album,
    Artist,
    FavoriteTargetType,
    PlayHistory,
    Playlist,
    PlaylistTrack,
    Tag,
    Track,
    TrackTag,
    User,
    UserFavorite,
    UserProfile,
    YouTubeDownload,
)

TABLE_MODELS = [
    ("users", User),
    ("artists", Artist),
    ("albums", Album),
    ("tracks", Track),
    ("playlists", Playlist),
    ("playlist_tracks", PlaylistTrack),
    ("tags", Tag),
    ("track_tags", TrackTag),
    ("favorites", UserFavorite),
    ("profiles", UserProfile),
    ("algorithm_learning", AlgorithmLearning),
    ("play_history", PlayHistory),
    ("youtube_downloads", YouTubeDownload),
]


def count_records(session: Session, model) -> int:
    return session.exec(select(func.count()).select_from(model)).one()


def summarize_counts(session: Session) -> Dict[str, int]:
    return {label: count_records(session, model) for label, model in TABLE_MODELS}


def _format_examples(rows: Sequence[Tuple[int, int]], limit: int = 5) -> str:
    preview = ", ".join(f"{src}->{target}" for src, target in rows[:limit])
    return preview if preview else ""


def check_albums(session: Session, artist_ids: Iterable[int]) -> List[str]:
    issues: List[str] = []
    artist_id_set = set(artist_ids)
    orphan_pairs: List[Tuple[int, int]] = []
    for album_id, artist_id in session.exec(select(Album.id, Album.artist_id)).all():
        if artist_id not in artist_id_set:
            orphan_pairs.append((album_id, artist_id))
    if orphan_pairs:
        examples = _format_examples(orphan_pairs)
        issues.append(
            f"Albums without artist reference: {len(orphan_pairs)} (examples: {examples})"
        )
    return issues


def check_tracks(session: Session, artist_ids: Iterable[int], album_ids: Iterable[int]) -> List[str]:
    issues: List[str] = []
    artist_id_set = set(artist_ids)
    album_id_set = set(album_ids)
    bad_artist: List[Tuple[int, int]] = []
    bad_album: List[Tuple[int, int]] = []
    for track_id, artist_id, album_id in session.exec(
        select(Track.id, Track.artist_id, Track.album_id)
    ).all():
        if artist_id not in artist_id_set:
            bad_artist.append((track_id, artist_id))
        if album_id is not None and album_id not in album_id_set:
            bad_album.append((track_id, album_id))
    if bad_artist:
        issues.append(
            f"Tracks referencing missing artists: {len(bad_artist)} (examples: {_format_examples(bad_artist)})"
        )
    if bad_album:
        issues.append(
            f"Tracks referencing missing albums: {len(bad_album)} (examples: {_format_examples(bad_album)})"
        )
    return issues


def check_playlists(session: Session, user_ids: Iterable[int], track_ids: Iterable[int]) -> List[str]:
    issues: List[str] = []
    user_id_set = set(user_ids)
    track_id_set = set(track_ids)

    orphan_playlists: List[Tuple[int, int]] = []
    for playlist_id, playlist_user_id in session.exec(
        select(Playlist.id, Playlist.user_id)
    ).all():
        if playlist_user_id not in user_id_set:
            orphan_playlists.append((playlist_id, playlist_user_id))
    if orphan_playlists:
        issues.append(
            f"Playlists referencing missing users: {len(orphan_playlists)} (examples: {_format_examples(orphan_playlists)})"
        )

    playlist_ids = {row[0] for row in session.exec(select(Playlist.id)).all()}
    orphan_pairs: List[Tuple[int, int]] = []
    for pivot_id, playlist_id, track_id in session.exec(
        select(PlaylistTrack.id, PlaylistTrack.playlist_id, PlaylistTrack.track_id)
    ).all():
        if playlist_id not in playlist_ids or track_id not in track_id_set:
            orphan_pairs.append((playlist_id, track_id))
    if orphan_pairs:
        issues.append(
            f"PlaylistTrack rows referencing missing playlist or track: {len(orphan_pairs)} (examples: {_format_examples(orphan_pairs)})"
        )
    return issues


def check_tags(session: Session, track_ids: Iterable[int], tag_ids: Iterable[int]) -> List[str]:
    issues: List[str] = []
    track_id_set = set(track_ids)
    tag_id_set = set(tag_ids)
    orphan_pairs: List[Tuple[int, int]] = []
    for rel_id, track_id, tag_id in session.exec(
        select(TrackTag.id, TrackTag.track_id, TrackTag.tag_id)
    ).all():
        if track_id not in track_id_set or tag_id not in tag_id_set:
            orphan_pairs.append((track_id, tag_id))
    if orphan_pairs:
        issues.append(
            f"TrackTag rows referencing missing track or tag: {len(orphan_pairs)} (examples: {_format_examples(orphan_pairs)})"
        )
    return issues


def check_favorites(
    session: Session,
    user_ids: Iterable[int],
    artist_ids: Iterable[int],
    album_ids: Iterable[int],
    track_ids: Iterable[int],
) -> List[str]:
    issues: List[str] = []
    user_id_set = set(user_ids)
    artist_id_set = set(artist_ids)
    album_id_set = set(album_ids)
    track_id_set = set(track_ids)

    missing_users: List[Tuple[int, int]] = []
    broken_targets: List[str] = []
    for fav in session.exec(select(UserFavorite)).all():
        if fav.user_id not in user_id_set:
            missing_users.append((fav.id, fav.user_id))
            continue
        if fav.target_type == FavoriteTargetType.ARTIST and (not fav.artist_id or fav.artist_id not in artist_id_set):
            broken_targets.append(f"favorite {fav.id} -> artist {fav.artist_id}")
        elif fav.target_type == FavoriteTargetType.ALBUM and (not fav.album_id or fav.album_id not in album_id_set):
            broken_targets.append(f"favorite {fav.id} -> album {fav.album_id}")
        elif fav.target_type == FavoriteTargetType.TRACK and (not fav.track_id or fav.track_id not in track_id_set):
            broken_targets.append(f"favorite {fav.id} -> track {fav.track_id}")
    if missing_users:
        issues.append(
            f"Favorites referencing missing users: {len(missing_users)} (examples: {_format_examples(missing_users)})"
        )
    if broken_targets:
        preview = ", ".join(broken_targets[:5])
        issues.append(
            f"Favorites pointing to missing targets: {len(broken_targets)} (examples: {preview})"
        )
    return issues


def check_profiles_and_learning(session: Session, user_ids: Iterable[int]) -> List[str]:
    issues: List[str] = []
    user_id_set = set(user_ids)

    profile_orphans = [
        (profile.id, profile.user_id)
        for profile in session.exec(select(UserProfile)).all()
        if profile.user_id not in user_id_set
    ]
    if profile_orphans:
        issues.append(
            f"UserProfile rows referencing missing users: {len(profile_orphans)} (examples: {_format_examples(profile_orphans)})"
        )

    learning_orphans = [
        (row.id, row.user_id)
        for row in session.exec(select(AlgorithmLearning)).all()
        if row.user_id not in user_id_set
    ]
    if learning_orphans:
        issues.append(
            f"AlgorithmLearning rows referencing missing users: {len(learning_orphans)} (examples: {_format_examples(learning_orphans)})"
        )

    play_history_orphans = [
        (row.id, row.user_id)
        for row in session.exec(select(PlayHistory)).all()
        if row.user_id not in user_id_set
    ]
    if play_history_orphans:
        issues.append(
            f"PlayHistory rows referencing missing users: {len(play_history_orphans)} (examples: {_format_examples(play_history_orphans)})"
        )
    return issues


def run_checks(session: Session) -> Tuple[Dict[str, int], List[str]]:
    counts = summarize_counts(session)

    user_ids = session.exec(select(User.id)).all()
    artist_ids = session.exec(select(Artist.id)).all()
    album_ids = session.exec(select(Album.id)).all()
    track_ids = session.exec(select(Track.id)).all()
    playlist_ids = session.exec(select(Playlist.id)).all()
    tag_ids = session.exec(select(Tag.id)).all()

    issues: List[str] = []
    issues += check_albums(session, artist_ids)
    issues += check_tracks(session, artist_ids, album_ids)
    issues += check_playlists(session, user_ids, track_ids)
    issues += check_tags(session, track_ids, tag_ids)
    issues += check_favorites(session, user_ids, artist_ids, album_ids, track_ids)
    issues += check_profiles_and_learning(session, user_ids)

    return counts, issues


def main() -> int:
    print("🔍 Running database health check...")
    create_db_and_tables()

    with get_session() as session:
        counts, issues = run_checks(session)

    print("\n📊 Table counts:")
    for label, value in counts.items():
        print(f"  - {label}: {value}")

    if issues:
        print("\n❌ Integrity issues detected:")
        for issue in issues:
            print(f"  - {issue}")
        print("\nFix the issues above before continuing.")
        return 1

    print("\n✅ Database integrity check passed. All foreign keys look consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
