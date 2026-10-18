.PHONY: test lint smoke package
test:
	PYTHONPATH=src:. pytest -q
lint:
	ruff check src automation scripts tests
smoke:
	bash scripts/smoke_test.sh
package:
	bash scripts/package_release.sh --version 0.2.0-rc1

