from __future__ import annotations

from pathlib import Path
import shutil

import pytest

from pytest_helm import manifest_fixture

pytest.importorskip("box")
pytest.importorskip("ruamel.yaml")

if shutil.which("helm") is None:
    pytestmark = pytest.mark.skip(reason="helm binary not available")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHART_DIR = PROJECT_ROOT / "tests" / "chart"

sample_chart_manifest = manifest_fixture(
    "sample_chart_manifest",
    [
        "helm",
        "template",
        "sample",
        str(CHART_DIR),
        "-f",
        str(CHART_DIR / "values.yaml"),
    ],
)


def test_sample_chart_config_map(sample_chart_manifest) -> None:
    cfg_map = sample_chart_manifest.get("v1/configmap/example-config")
    assert cfg_map.data.AWS_DEFAULT_REGION == "us-east-2"


def test_sample_chart_deployment(sample_chart_manifest) -> None:
    deployment = sample_chart_manifest.get("apps/v1/deployment/example-api")
    container = deployment.spec.template.spec.containers[0]

    assert deployment.spec.replicas == 1
    assert container.image == "nginx:1.27.0"
    assert container.imagePullPolicy == "IfNotPresent"


def test_sample_chart_service(sample_chart_manifest) -> None:
    service = sample_chart_manifest.get("v1/service/example-api")
    first_port = service.spec.ports[0]

    assert service.spec.type == "ClusterIP"
    assert service.spec.selector["app.kubernetes.io/name"] == "example-api"
    assert first_port.port == 80
    assert first_port.targetPort == "http"
