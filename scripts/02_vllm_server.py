import os
import shlex
import subprocess

from apps.vllm.start import build_command

command = build_command(os.environ)
print(shlex.join(command))
if os.getenv("TRAINER_EXECUTE_VLLM", "").lower() == "true":
    raise SystemExit(subprocess.call(command))
