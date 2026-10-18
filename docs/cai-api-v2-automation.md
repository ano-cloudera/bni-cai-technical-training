# Cloudera AI API v2 Automation

The default command is read-only and creates a desired-state plan:

```bash
PYTHONPATH=src:. python -m automation.cai_api_v2.cli --config config/env.bni.example.yaml plan --output build/cai-plan.json
```

Set `CAI_API_BASE_URL`, `CAI_API_KEY`, and optionally `CAI_CA_BUNDLE` in the shell. Do not store them in YAML. The target workbench exposes its exact specification at `/api/v2/swagger.html` and Python client at `/api/v2/python.html`. Validate Application resource profiles and runtime identifiers there before enabling live creation. The included client uses Bearer authentication and the documented project and Application routes. Cleanup must use a generated inventory with exact IDs and the `bni-cai-training-2026` label.

Official references: [Cloudera AI API v2 overview](https://docs.cloudera.com/machine-learning/1.5.5/api/topics/ml-api-v2.html) and [REST API v2 reference](https://docs.cloudera.com/machine-learning/1.5.5/rest-api-reference/index.html).

