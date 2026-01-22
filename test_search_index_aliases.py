from app.core.search_index import generate_aliases


def test_generate_alias_captures_de_duped_names():
    aliases = generate_aliases("Metallica")
    assert "metalica" in {alias.lower() for alias in aliases}
    assert "mtlc" in {alias.lower() for alias in aliases}


def test_generate_alias_applies_phonetic_rules():
    aliases = generate_aliases("Phish")
    assert "fish" in {alias.lower() for alias in aliases}
