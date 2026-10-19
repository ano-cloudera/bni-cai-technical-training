"""TRAINER ONLY. Validate the Qwen model directory on the CAI NFS workspace. Never downloads unless asked."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

from bni_training.labs import PrerequisiteMissing, run_lab, workshop_role
from bni_training.model_artifact import directory_manifest

DESCRIPTION = "Lab 01 (trainer only): validate the model artifact on NFS; no download by default."


def configure(parser):
    parser.add_argument("--model-path", type=Path, default=None, help="Defaults to $MODEL_PATH in cai mode")
    parser.add_argument("--model-id", default="Qwen/Qwen3.5-9B")
    parser.add_argument("--download", action="store_true", help="Explicit, trainer-only, one-time download")
    parser.add_argument(
        "--write-manifest", action="store_true", help="Record checksums in the model directory"
    )


def body(args, report):
    trainer = workshop_role() == "trainer"
    if args.download and not trainer:
        report.failed(
            "download", "refused: a download needs WORKSHOP_ROLE=trainer; participants never download models"
        )
        return
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
        if args.download:
            report.skipped("download", "local mode never downloads")
        return
    if not trainer:
        report.skipped("role", "trainer-only lab: read it, but the trainer validates the model on NFS")
        return
    model_path = args.model_path or (Path(os.environ["MODEL_PATH"]) if os.getenv("MODEL_PATH") else None)
    if model_path is None:
        raise PrerequisiteMissing("Set MODEL_PATH or pass --model-path")
    if args.download:
        from huggingface_hub import snapshot_download

        snapshot_download(args.model_id, local_dir=model_path)
        report.passed("download", "explicit one-time download finished")
    else:
        report.skipped("download", "no download requested (this lab never downloads by default)")
    manifest = directory_manifest(model_path)
    report.passed("nfs_model", f"validated {len(manifest)} model files")
    if args.write_manifest:
        (model_path / "training-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        report.passed("manifest_written", "training-manifest.json recorded in the model directory")


def main(argv=None) -> int:
    return run_lab("01", DESCRIPTION, body, argv, configure)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
