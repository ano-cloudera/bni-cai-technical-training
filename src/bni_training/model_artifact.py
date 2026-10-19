import hashlib
from pathlib import Path


def hash_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def validate_model_path(path: str | Path) -> Path:
    if not str(path).strip():
        raise ValueError("MODEL_PATH is not set; point it at the existing local model directory (NFS)")
    model = Path(path)
    required = [model / "config.json"]
    if not model.is_dir() or any(not item.exists() for item in required):
        raise ValueError(f"MODEL_PATH is not a complete local model directory: {model}")
    if not list(model.glob("*.safetensors")):
        raise ValueError("MODEL_PATH contains no .safetensors files")
    return model


def directory_manifest(path: str | Path) -> list[dict]:
    root = validate_model_path(path)
    result = []
    for file in sorted(p for p in root.rglob("*") if p.is_file()):
        digest = hash_file(file)
        result.append({"path": str(file.relative_to(root)), "size": file.stat().st_size, "sha256": digest})
    return result


def build_vllm_command(model_path: str, served_name: str, port: int) -> list[str]:
    return [
        "python",
        "-m",
        "vllm.entrypoints.openai.api_server",
        "--model",
        model_path,
        "--served-model-name",
        served_name,
        "--host",
        "0.0.0.0",
        "--port",
        str(port),
        "--tensor-parallel-size",
        "1",
        "--dtype",
        "bfloat16",
        "--max-model-len",
        "8192",
        "--gpu-memory-utilization",
        "0.75",
        "--max-num-seqs",
        "32",
    ]
