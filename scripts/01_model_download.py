from __future__ import annotations

import argparse
import json
from pathlib import Path

from bni_training.model_artifact import directory_manifest


def main():
    parser = argparse.ArgumentParser(
        description="Validate a pre-staged NFS model or optionally download it once."
    )
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--model-id", default="Qwen/Qwen3.5-9B")
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    if args.download:
        from huggingface_hub import snapshot_download

        snapshot_download(args.model_id, local_dir=args.model_path)
    manifest = directory_manifest(args.model_path)
    out = args.model_path / "training-manifest.json"
    out.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Validated {len(manifest)} model files at {args.model_path}")


if __name__ == "__main__":
    main()
