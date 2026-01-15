"""Tests for package metadata and structure."""

import argdump


def test_version_defined():
    """Ensure __version__ is defined."""
    assert hasattr(argdump, "__version__")
    assert isinstance(argdump.__version__, str)


def test_version_matches_pyproject():
    """Ensure argdump.__version__ matches pyproject.toml."""
    import re
    from pathlib import Path

    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    content = pyproject_path.read_text()

    match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
    assert match, "Could not find version in pyproject.toml"

    assert argdump.__version__ == match.group(1)


def test_public_api():
    """Ensure expected public API is exported."""
    expected = {"dump", "dumps", "load", "loads"}
    actual = {name for name in dir(argdump) if not name.startswith("_")}

    assert expected <= actual
