from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PROFILES_FILE = ROOT / "requirements" / "profiles.yaml"


def profile_lock(profile: str) -> Path:
    profiles = yaml.safe_load(PROFILES_FILE.read_text())["profiles"]
    if profile not in profiles:
        raise ValueError(f"Unknown dependency profile: {profile}")
    return Path(profiles[profile]["lock"])


def build_install_command(profile: str, *, offline: bool, wheelhouse: str = "wheelhouse") -> list[str]:
    lock = profile_lock(profile)
    command = [sys.executable, "-m", "pip", "install"]
    if offline:
        command.extend(["--no-index", "--find-links", wheelhouse])
    command.extend(["--requirement", str(lock)])
    return command


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install one pinned BNI training dependency profile")
    parser.add_argument("profile")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--wheelhouse", default="wheelhouse")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    command = build_install_command(args.profile, offline=args.offline, wheelhouse=args.wheelhouse)
    if args.dry_run:
        print(json.dumps(command))
        return 0
    subprocess.run(command, cwd=ROOT, check=True)
    editable = [sys.executable, "-m", "pip", "install", "--no-deps", "--editable", "."]
    subprocess.run(editable, cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
