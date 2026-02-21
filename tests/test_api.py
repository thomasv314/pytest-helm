from __future__ import annotations

import pytest

import pytest_helm._api as api
from pytest_helm import ManifestIndex, manifest_fixture


def test_manifest_fixture_validates_inputs() -> None:
    with pytest.raises(ValueError, match="non-empty string"):
        manifest_fixture("", ["helm", "template", "."])

    with pytest.raises(ValueError, match="non-empty sequence"):
        manifest_fixture("default_manifest", [])

    with pytest.raises(ValueError, match="non-empty strings"):
        manifest_fixture("default_manifest", ["helm", "", "."])

def test_manifest_fixture_creates_named_session_fixture(monkeypatch) -> None:
    expected = ManifestIndex()
    calls: list[tuple[tuple[str, ...], str]] = []

    def fake_load_manifest(command, *, on_duplicate):
        calls.append((tuple(command), on_duplicate))
        return expected

    monkeypatch.setattr(api, "load_manifest", fake_load_manifest)

    fixture_function = manifest_fixture(
        "default_manifest",
        ["helm", "template", ".", "-f", "values.yaml"],
        on_duplicate="ignore",
    )

    marker = fixture_function._fixture_function_marker  # noqa: SLF001
    assert fixture_function.name == "default_manifest"
    assert marker.scope == "session"

    # pytest wraps fixture callables; __wrapped__ gives access to inner function.
    result = fixture_function.__wrapped__()
    assert result is expected
    assert calls == [
        (("helm", "template", ".", "-f", "values.yaml"), "ignore")
    ]
