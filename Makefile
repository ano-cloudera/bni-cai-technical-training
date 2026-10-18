.PHONY: test lint smoke package profiles notebooks
test:
	PYTHONPATH=src:. pytest -q
lint:
	ruff check src automation scripts tests deployments apps data
profiles:
	python scripts/validate_profiles.py
notebooks:
	python scripts/execute_notebooks.py
smoke:
	bash scripts/smoke_test.sh
package:
	bash scripts/package_release.sh --version 0.2.0-rc1

