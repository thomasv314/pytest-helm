"""Helm manifest command execution and parsed index structures."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal
from box import Box
from ruamel.yaml import YAML
import shlex
import subprocess

DuplicatePolicy = Literal["error", "ignore"]


class HelmTemplateError(RuntimeError):
    """Raised when the Helm command fails to run successfully."""

    def __init__(
        self,
        command: Sequence[str],
        *,
        returncode: int | None = None,
        stderr: str = "",
        stdout: str = "",
        cause: BaseException | None = None,
    ) -> None:
        self.command = tuple(command)
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = stdout
        self.cause = cause

        cmd_text = shlex.join(command)
        if cause is not None:
            message = f"Failed to execute Helm command: {cmd_text}. Cause: {cause}"
        else:
            message = (
                f"Helm command failed with exit code {returncode}: {cmd_text}\n"
                f"stderr:\n{stderr.strip() or '(empty)'}"
            )
        super().__init__(message)


class ManifestParseError(ValueError):
    """Raised when rendered YAML cannot be interpreted as Kubernetes manifests."""


class DuplicateManifestError(ValueError):
    """Raised when duplicate apiVersion/kind/name manifests are found."""


class AmbiguousManifestError(LookupError):
    """Raised when a selector without apiVersion matches multiple manifests."""


@dataclass(frozen=True)
class _ManifestRecord:
    api_version: str
    kind: str
    name: str
    manifest: Any

    @property
    def duplicate_key(self) -> tuple[str, str, str]:
        return (
            self.kind.casefold(),
            self.name.casefold(),
            self.api_version.casefold(),
        )


class ManifestIndex:
    """Selector-based manifest lookup over a parsed Helm render."""

    def __init__(self, records: Sequence[_ManifestRecord] | None = None) -> None:
        self._records = tuple(records or ())

    def get(self, selector: str) -> Any:
        api_version, kind, name = self._parse_selector(selector)
        kind_records = self._records_for_kind(kind)
        name_records = self._records_for_name(kind_records, kind=kind, name=name)

        if api_version is None:
            return self._single_or_ambiguous(kind=kind, name=name, records=name_records)

        return self._match_api_version(
            kind=kind,
            name=name,
            api_version=api_version,
            records=name_records,
        )

    def _records_for_kind(self, kind: str) -> list[_ManifestRecord]:
        kind_cf = kind.casefold()
        matches = [record for record in self._records if record.kind.casefold() == kind_cf]
        if matches:
            return matches

        available = ", ".join(self._available_kinds())
        raise KeyError(
            f"Kind {kind!r} not found. "
            f"Available kinds: {available or '(none)'}"
        )

    def _records_for_name(
        self,
        records: Sequence[_ManifestRecord],
        *,
        kind: str,
        name: str,
    ) -> list[_ManifestRecord]:
        name_cf = name.casefold()
        matches = [record for record in records if record.name.casefold() == name_cf]
        if matches:
            return matches

        available = ", ".join(self._available_names_for_kind(records))
        raise KeyError(
            f"Manifest {kind!r}/{name!r} not found. "
            f"Available names for {kind!r}: {available or '(none)'}"
        )

    @staticmethod
    def _single_or_ambiguous(
        *,
        kind: str,
        name: str,
        records: Sequence[_ManifestRecord],
    ) -> Any:
        api_versions = sorted({record.api_version for record in records}, key=str.casefold)

        if len(api_versions) > 1:
            raise AmbiguousManifestError(
                f"Manifest {kind!r}/{name!r} is ambiguous across apiVersions: "
                f"{', '.join(api_versions)}. Use 'apiVersion/kind/name'."
            )

        return records[0].manifest

    @staticmethod
    def _match_api_version(
        *,
        kind: str,
        name: str,
        api_version: str,
        records: Sequence[_ManifestRecord],
    ) -> Any:
        api_cf = api_version.casefold()
        for record in records:
            if record.api_version.casefold() == api_cf:
                return record.manifest

        available = ", ".join(
            sorted({record.api_version for record in records}, key=str.casefold)
        )
        raise KeyError(
            f"Manifest {kind!r}/{name!r} with apiVersion {api_version!r} not found. "
            f"Available apiVersions for {kind!r}/{name!r}: {available or '(none)'}"
        )

    def _available_kinds(self) -> list[str]:
        seen: dict[str, str] = {}
        for record in self._records:
            seen.setdefault(record.kind.casefold(), record.kind)
        return sorted(seen.values(), key=str.casefold)

    @staticmethod
    def _available_names_for_kind(records: Sequence[_ManifestRecord]) -> list[str]:
        seen: dict[str, str] = {}
        for record in records:
            seen.setdefault(record.name.casefold(), record.name)
        return sorted(seen.values(), key=str.casefold)

    @staticmethod
    def _parse_selector(selector: str) -> tuple[str | None, str, str]:
        parts = [part for part in selector.strip("/").split("/") if part]
        if len(parts) < 2:
            raise ValueError(
                f"Invalid selector {selector!r}. Expected 'kind/name' or "
                "'apiVersion/kind/name'."
            )

        name = parts[-1]
        kind = parts[-2]
        api_version = "/".join(parts[:-2]) or None
        return api_version, kind, name

    def __repr__(self) -> str:
        by_kind: dict[str, dict[str, str]] = {}
        kind_case: dict[str, str] = {}

        for record in self._records:
            kind_key = record.kind.casefold()
            kind_case.setdefault(kind_key, record.kind)
            by_kind.setdefault(kind_key, {})
            by_kind[kind_key].setdefault(record.name.casefold(), record.name)

        kind_entries = []
        for kind_key in sorted(by_kind, key=str.casefold):
            kind = kind_case[kind_key]
            names = sorted(by_kind[kind_key].values(), key=str.casefold)
            names_text = ", ".join(repr(name) for name in names)
            kind_entries.append(f"{kind!r}: [{names_text}]")

        return f"ManifestIndex({{{', '.join(kind_entries)}}})"



def _apply_duplicate_policy(
    records: Sequence[_ManifestRecord],
    *,
    on_duplicate: DuplicatePolicy,
) -> list[_ManifestRecord]:
    deduped: list[_ManifestRecord] = []
    seen: set[tuple[str, str, str]] = set()

    for record in records:
        key = record.duplicate_key
        if key in seen:
            if on_duplicate == "error":
                raise DuplicateManifestError(
                    "Duplicate manifest detected for "
                    f"apiVersion={record.api_version!r}, "
                    f"kind={record.kind!r}, name={record.name!r}. "
                    "Set on_duplicate='ignore' to keep the first document."
                )
            continue

        seen.add(key)
        deduped.append(record)

    return deduped


def run_helm_template(command: Sequence[str]) -> str:
    """Execute `helm template ...` and return stdout text."""
    try:
        completed = subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise HelmTemplateError(command, cause=exc) from exc

    if completed.returncode != 0:
        raise HelmTemplateError(
            command,
            returncode=completed.returncode,
            stderr=completed.stderr,
            stdout=completed.stdout,
        )
    return completed.stdout


def parse_manifest_documents(
    manifest_text: str,
    *,
    on_duplicate: DuplicatePolicy = "error",
) -> ManifestIndex:
    """Parse Helm manifest YAML output into a selector-based index."""

    yaml = YAML(typ="safe")
    records: list[_ManifestRecord] = []

    for document_number, document in enumerate(yaml.load_all(manifest_text), start=1):
        if document is None:
            continue
        if not isinstance(document, Mapping):
            raise ManifestParseError(
                f"YAML document #{document_number} is not a mapping object."
            )

        kind = document.get("kind")
        api_version = document.get("apiVersion")
        metadata = document.get("metadata")
        name = metadata.get("name") if isinstance(metadata, Mapping) else None

        if not isinstance(api_version, str) or not api_version:
            raise ManifestParseError(
                f"YAML document #{document_number} is missing non-empty 'apiVersion'."
            )
        if not isinstance(kind, str) or not kind:
            raise ManifestParseError(
                f"YAML document #{document_number} is missing non-empty 'kind'."
            )
        if not isinstance(name, str) or not name:
            raise ManifestParseError(
                f"YAML document #{document_number} is missing non-empty 'metadata.name'."
            )

        records.append(
            _ManifestRecord(
                api_version=api_version,
                kind=kind,
                name=name,
                manifest=Box(document),
            )
        )

    deduped_records = _apply_duplicate_policy(records, on_duplicate=on_duplicate)
    return ManifestIndex(deduped_records)


def load_manifest(
    command: Sequence[str],
    *,
    on_duplicate: DuplicatePolicy = "error",
) -> ManifestIndex:
    """Run Helm and parse output into a manifest index."""
    rendered = run_helm_template(command)
    return parse_manifest_documents(rendered, on_duplicate=on_duplicate)
