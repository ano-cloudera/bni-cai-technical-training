import os
from pathlib import Path

import yaml


def load_environment(path: Path) -> dict:
    config = yaml.safe_load(path.read_text())
    base = os.getenv(config["api_base_url_env"], "")
    key = os.getenv(config["api_key_env"], "")
    return {
        **config,
        "api_base_url": base,
        "api_key": key,
        "ca_bundle": os.getenv(config["ca_bundle_env"], "") or None,
    }
