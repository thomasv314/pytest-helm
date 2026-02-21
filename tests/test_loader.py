from __future__ import annotations

import subprocess

import pytest

pytest.importorskip("box")
pytest.importorskip("ruamel.yaml")

from pytest_helm import (
    AmbiguousManifestError,
    DuplicateManifestError,
    HelmTemplateError,
    ManifestParseError,
    load_manifest,
    parse_manifest_documents,
)


def test_parse_manifest_documents_indexes_by_selector() -> None:
    manifest_text = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: example-config
data:
  AWS_DEFAULT_REGION: us-east-2
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: example-api
spec:
  replicas: 2
""".strip()

    manifests = parse_manifest_documents(manifest_text)

    cfg_map = manifests.get("configmap/example-config")
    deployment = manifests.get("apps/v1/deployment/example-api")
    assert cfg_map.data.AWS_DEFAULT_REGION == "us-east-2"
    assert deployment.spec.replicas == 2


def test_manifest_index_get_is_case_insensitive() -> None:
    manifest_text = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: release-name
spec:
  replicas: 2
""".strip()
    manifests = parse_manifest_documents(manifest_text)

    deployment = manifests.get("deployment/release-name")
    deployment_upper = manifests.get("APPS/V1/DEPLOYMENT/RELEASE-NAME")

    assert deployment.spec.replicas == 2
    assert deployment_upper is deployment


def test_manifest_index_repr_includes_kind_and_name_keys() -> None:
    manifest_text = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: example-config
data: {}
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: example-api
spec: {}
""".strip()
    manifests = parse_manifest_documents(manifest_text)

    assert (
        repr(manifests)
        == "ManifestIndex({'ConfigMap': ['example-config'], 'Deployment': ['example-api']})"
    )


def test_manifest_index_get_requires_selector_format() -> None:
    manifests = parse_manifest_documents(
        """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: release-name
spec: {}
""".strip()
    )

    with pytest.raises(ValueError, match="Expected 'kind/name' or 'apiVersion/kind/name'"):
        manifests.get("Deployment")


def test_manifest_index_get_raises_for_missing_values() -> None:
    manifests = parse_manifest_documents(
        """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: release-name
spec: {}
""".strip()
    )

    with pytest.raises(KeyError, match="Kind 'service' not found"):
        manifests.get("apps/v1/service/release-name")
    with pytest.raises(KeyError, match="Manifest 'deployment'/'missing' not found"):
        manifests.get("apps/v1/deployment/missing")
    with pytest.raises(KeyError, match="with apiVersion 'v1' not found"):
        manifests.get("v1/deployment/release-name")


def test_parse_manifest_documents_duplicate_manifest_errors_by_default() -> None:
    manifest_text = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: duplicate
data:
  A: one
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: duplicate
data:
  A: two
""".strip()

    with pytest.raises(DuplicateManifestError, match="Duplicate manifest detected"):
        parse_manifest_documents(manifest_text)


def test_parse_manifest_documents_duplicate_manifest_can_ignore() -> None:
    manifest_text = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: duplicate
data:
  A: one
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: duplicate
data:
  A: two
""".strip()

    manifests = parse_manifest_documents(manifest_text, on_duplicate="ignore")

    assert manifests.get("v1/configmap/duplicate").data.A == "one"


def test_case_only_duplicate_variants_are_treated_as_duplicates() -> None:
    manifest_text = """
apiVersion: APPS/v1
kind: Deployment
metadata:
  name: API
spec: {}
---
apiVersion: apps/V1
kind: deployment
metadata:
  name: api
spec: {}
""".strip()

    with pytest.raises(DuplicateManifestError, match="Duplicate manifest detected"):
        parse_manifest_documents(manifest_text)


def test_same_kind_name_different_api_versions_require_versioned_lookup() -> None:
    manifest_text = """
apiVersion: extensions/v1beta1
kind: Deployment
metadata:
  name: release-name
spec:
  replicas: 1
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: release-name
spec:
  replicas: 2
""".strip()
    manifests = parse_manifest_documents(manifest_text)

    with pytest.raises(AmbiguousManifestError, match="Use 'apiVersion/kind/name'"):
        manifests.get("deployment/release-name")

    old_deployment = manifests.get("extensions/v1beta1/deployment/release-name")
    new_deployment = manifests.get("apps/v1/deployment/release-name")
    assert old_deployment.spec.replicas == 1
    assert new_deployment.spec.replicas == 2


def test_parse_manifest_documents_requires_api_version_kind_and_name() -> None:
    with pytest.raises(ManifestParseError, match="missing non-empty 'apiVersion'"):
        parse_manifest_documents(
            """
kind: Service
metadata:
  name: no-api-version
""".strip()
        )

    with pytest.raises(ManifestParseError, match="missing non-empty 'kind'"):
        parse_manifest_documents(
            """
apiVersion: v1
metadata:
  name: no-kind
""".strip()
        )

    with pytest.raises(ManifestParseError, match="missing non-empty 'metadata.name'"):
        parse_manifest_documents(
            """
apiVersion: v1
kind: Service
metadata: {}
""".strip()
        )


def test_load_manifest_raises_helm_template_error_on_nonzero_exit(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=["helm", "template", "."],
            returncode=1,
            stdout="",
            stderr="template failed",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(HelmTemplateError, match="Helm command failed with exit code 1"):
        load_manifest(["helm", "template", "."])
