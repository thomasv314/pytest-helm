"""Pytest fixture factory for Helm manifest rendering."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from ._loader import DuplicatePolicy, ManifestIndex, load_manifest


def manifest_fixture(
    name: str,
    command: Sequence[str],
    *,
    on_duplicate: DuplicatePolicy = "error",
):
    """
    Create a named pytest fixture that returns a parsed Helm manifest index.

    Example:
        default_manifest = manifest_fixture(
            "default_manifest",
            ["helm", "template", ".", "-f", "values.yaml"],
        )
    """
    if not isinstance(name, str) or not name:
        raise ValueError("Fixture name must be a non-empty string.")

    command = tuple(command)
    if not command:
        raise ValueError("Helm command must be a non-empty sequence of strings.")
    if not all(isinstance(part, str) and part for part in command):
        raise ValueError("Helm command must contain only non-empty strings.")

    @pytest.fixture(name=name, scope="session")
    def _manifest_fixture() -> ManifestIndex:
        return load_manifest(command, on_duplicate=on_duplicate)

    return _manifest_fixture
