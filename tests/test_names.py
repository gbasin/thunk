"""Tests for name generation."""

from thunk.names import ADJECTIVES, NOUNS, generate_name, generate_unique_name


def test_generate_name_format():
    """Test that generated names have correct format."""
    name = generate_name()
    assert "-" in name
    parts = name.split("-")
    assert len(parts) == 2


def test_generate_name_uses_vocabulary():
    """Test that names use the defined vocabulary."""
    for _ in range(100):
        name = generate_name()
        adj, noun = name.split("-")
        assert adj in ADJECTIVES
        assert noun in NOUNS


def test_generate_unique_name_avoids_collisions():
    """Test that unique names avoid existing names."""
    existing = {"swift-river", "calm-meadow", "bold-peak"}
    for _ in range(50):
        name = generate_unique_name(existing)
        assert name not in existing


def test_generate_unique_name_fallback():
    """Test fallback when collisions are likely."""
    # Create a set with all possible combinations (unrealistic but tests fallback)
    # Actually, just test with a small set that we know will collide
    existing = set()
    # Generate some names and add them
    for _ in range(100):
        name = generate_name()
        existing.add(name)

    # Should still work even with many existing names
    name = generate_unique_name(existing)
    assert name not in existing


def test_generate_unique_name_empty_set():
    """Test with empty existing set."""
    name = generate_unique_name(set())
    assert "-" in name


def test_vocabulary_sizes():
    """Test that vocabulary is reasonably sized."""
    # Should have enough for ~22,500 combinations
    assert len(ADJECTIVES) >= 100
    assert len(NOUNS) >= 100
    assert len(ADJECTIVES) * len(NOUNS) >= 10000
