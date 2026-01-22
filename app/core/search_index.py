"""
Helpers for DB-first search: normalization and alias management.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Iterable, Dict, Set

from sqlmodel import Session, select

from ..models.base import SearchAlias, SearchEntityType

logger = logging.getLogger(__name__)

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_VOWELS = frozenset("aeiou")
_VARIANT_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("ph", "f"),
    ("ck", "k"),
    ("qu", "k"),
    ("kk", "k"),
    ("sch", "sh"),
    ("sh", "s"),
    ("y", "i"),
)


def normalize_search_text(value: str) -> str:
    """Normalize user input for stable matching (lower, strip accents, collapse spaces)."""
    if not value:
        return ""
    cleaned = value.lower().strip()
    cleaned = unicodedata.normalize("NFD", cleaned)
    cleaned = "".join(ch for ch in cleaned if unicodedata.category(ch) != "Mn")
    cleaned = _NON_ALNUM_RE.sub(" ", cleaned)
    return " ".join(cleaned.split())


def _strip_vowels(value: str) -> str:
    return "".join(ch for ch in value if ch not in _VOWELS)


def _collapse_duplicates(value: str) -> str:
    if not value:
        return ""
    collapsed = [value[0]]
    for ch in value[1:]:
        if ch == collapsed[-1]:
            continue
        collapsed.append(ch)
    return "".join(collapsed)


def _apply_variant_replacements(value: str) -> Set[str]:
    variants: Set[str] = set()
    for pattern, replacement in _VARIANT_REPLACEMENTS:
        if pattern and pattern in value:
            variants.add(value.replace(pattern, replacement))
    return variants


def _generate_variant_forms(normalized: str) -> Set[str]:
    variants: Set[str] = set()
    stripped = normalized.replace(" ", "")
    if stripped:
        variants.add(stripped)
    collapsed = _collapse_duplicates(normalized)
    if collapsed:
        variants.add(collapsed)
        vowels = _strip_vowels(collapsed)
        if vowels:
            variants.add(vowels)
    vowels_removed = _strip_vowels(normalized)
    if vowels_removed:
        variants.add(vowels_removed)
    for variant in _apply_variant_replacements(normalized):
        variants.add(variant)
        collapsed_variant = _collapse_duplicates(variant)
        if collapsed_variant:
            variants.add(collapsed_variant)
        stripped_variant = _strip_vowels(variant)
        if stripped_variant:
            variants.add(stripped_variant)
    return variants


def generate_aliases(name: str) -> Set[str]:
    """Generate alias variants that cover typos and phonetic hits."""
    if not name:
        return set()
    normalized = normalize_search_text(name)
    variants: Set[str] = {
        name.strip(),
        normalized,
        normalized.replace(" ", "") if normalized else "",
    }
    variants.update(_generate_variant_forms(normalized))
    return {v for v in variants if v}


def upsert_aliases(
    session: Session,
    entity_type: SearchEntityType,
    entity_id: int,
    aliases: Iterable[str],
    source: str = "system",
) -> int:
    """Persist missing aliases and return how many were added."""
    alias_map: Dict[str, str] = {}
    for alias in aliases:
        if not alias:
            continue
        normalized = normalize_search_text(alias)
        if not normalized or normalized in alias_map:
            continue
        alias_map[normalized] = alias.strip()

    if not alias_map:
        return 0

    try:
        existing = session.exec(
            select(SearchAlias.normalized_alias)
            .where(SearchAlias.entity_type == entity_type)
            .where(SearchAlias.entity_id == entity_id)
            .where(SearchAlias.normalized_alias.in_(alias_map.keys()))
        ).all()
    except Exception as exc:
        logger.warning("SearchAlias unavailable; skipping alias upsert: %s", exc)
        return 0
    existing_set = set(existing)
    to_create = [norm for norm in alias_map.keys() if norm not in existing_set]
    for normalized in to_create:
        session.add(SearchAlias(
            entity_type=entity_type,
            entity_id=entity_id,
            alias=alias_map[normalized],
            normalized_alias=normalized,
            source=source,
        ))
    return len(to_create)


def ensure_entity_aliases(
    session: Session,
    entity_type: SearchEntityType,
    entity_id: int,
    name: str,
) -> int:
    """Ensure at least basic alias variants exist for the entity."""
    aliases = generate_aliases(name)
    return upsert_aliases(session, entity_type, entity_id, aliases)
