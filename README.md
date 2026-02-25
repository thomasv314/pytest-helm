# pytest-helm

`pytest-helm` makes it easy to test Helm charts in a simple and repeatable fashion.

It runs a helm template command, loads your manifests into a fixture, and then allows you to make simple
assertions about it's shape/contents.

## Quickstart

#### Add pytest-helm
```bash
uv add pytest-helm
```

#### Scaffold out the fixture/test file
We assume you won't have pytest configured for a chart directory, so if that's the case you can run:

```
uv run pytest-helm --init
```

That will create two sample test files, a fixture in `tests/conftest.py` and a test in `tests/test_deployment.py`.

If you are already using pytest, you can skip this step.

#### Usage

Define as many fixtures as you'd like in conftest:

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

Write tests to validate the YAML shape/output for different values meets your requirements:

```python
# tests/test_deployments.py
def test_it_provisions_one_replica_by_default(chart):
    api = chart.get("deployment/api-server")
    assert api.spec.replicas == 1

def test_it_provisions_multiple_replicas_in_prod(prod_chart):
    api = prod_chart.get("deployment/api-server")
    assert api.spec.replicas == 3
```

Use PDB to programatically inspect your manifests:

```python
def test_idk_what_to_test(chart):
   import pdb; pdb.set_trace()

$ pytest
(Pdb) chart
   ManifestIndex({
        'ConfigMap': ['release-name-base-config'],
        'Deployment': ['release-name-api', 'release-name-worker'],
        'Ingress': ['release-name-app'],
        'Job': ['release-name-db-migrate'],
        'Service': ['release-name-api'],
        'ServiceAccount': ['backend']
   })

(Pdb) chart.get("configmap/release-name-base-config")
Box({'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': 'release-name-base-config'}, 'data': {'EMAIL_FROM': 'foo@bar.com'}})

(Pdb)
```

**Notes:** 
- `chart.get()` is case-insensitive, `chart.get("ConfigMap/foo")` and `chart.get("configmap/foo")` are the same thing
- In the event that two resources have the same name/kind, you are required to pass an apiVersion as well, i.e. `v1/ConfigMap/foo` 
