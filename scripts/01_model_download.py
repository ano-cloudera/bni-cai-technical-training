from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

from bni_training.labs import PrerequisiteMissing, run_lab
from bni_training.model_artifact import directory_manifest

DESCRIPTION = "Lab 01: validate a pre-staged NFS model directory, or optionally download it once."


def configure(parser):
    parser.add_argument("--model-path", type=Path, default=None, help="Defaults to $MODEL_PATH in cai mode")
    parser.add_argument("--model-id", default="Qwen/Qwen3.5-9B")
    parser.add_argument(
        "--download", action="store_true", help="cai mode only: download once to --model-path"
    )


def body(args, report):
    if args.mode == "local":
        report.skipped(
            "nfs_model", "The Qwen3.5-9B weights live on NFS and are never packaged or downloaded locally"
        )
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp)
            (fake / "config.json").write_text("{}")
            (fake / "model-00001-of-00001.safetensors").write_bytes(b"synthetic-placeholder-weights")
            manifest = directory_manifest(fake)
        report.passed("manifest_code_path", f"hashed {len(manifest)} files in a synthetic stand-in directory")
        return
    model_path = args.model_path or (Path(os.environ["MODEL_PATH"]) if os.getenv("MODEL_PATH") else None)
    if model_path is None:
        raise PrerequisiteMissing("Set MODEL_PATH or pass --model-path")
    if args.download:
        from huggingface_hub import snapshot_download

        snapshot_download(args.model_id, local_dir=model_path)
    manifest = directory_manifest(model_path)
    (model_path / "training-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    report.passed("nfs_model", f"validated {len(manifest)} model files")


def main(argv=None) -> int:
    return run_lab("01", DESCRIPTION, body, argv, configure)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
