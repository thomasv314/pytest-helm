# pytest-helm

`pytest-helm` makes Helm chart testing in pytest simple and repeatable.

It runs a helm template command, loads your manifest, and then allows you to make simple
assertions about it's shape/contents.

## Quickstart

Add pytest-helm:

```bash
uv add pytest-helm

```

Create `tests/conftest.py`:

```python
# tests/conftest.py
from pytest_helm import manifest_fixture

chart = manifest_fixture(
    "chart",
    ["helm", "template", ".", "-f", "values.yaml"],
)

prod_chart = manifest_fixture(
    "prod_chart",
    ["helm", "template", ".", "-f", "prod-values.yaml"],
)
```

Write tests:

```python
# tests/test_deployments.py
def test_it_provisions_one_replica_by_default(chart):
    api = chart.get("deployment/api-server")
    assert api.spec.replicas == 1

def test_it_provisions_multiple_replicas_in_prod(prod_chart):
    api = prod_chart.get("deployment/api-server")
    assert = api.spec.replicas == 3
```
