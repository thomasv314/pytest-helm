# Sample chart

This is a minimal Helm chart used to dogfood `pytest-helm` integration tests.

Render it:

```bash
helm template sample tests/chart -f tests/chart/values.yaml
```

Primary resources:

- `ConfigMap/example-config`
- `Service/example-api`
- `Deployment/example-api`
