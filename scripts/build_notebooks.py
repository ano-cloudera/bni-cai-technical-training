"""Generate the 13 canonical notebook templates from config/workshop/labs.yaml (the source of truth).

Templates are written stripped (no outputs, counts, timestamps or local values). Group copies are made later by
scripts/prepare_group_workspaces.py. The rc1 notebooks in notebooks/*.ipynb are kept as they are and are not
regenerated here.
"""

from __future__ import annotations

import argparse
import json
import sys

from bni_training.lab_registry import REPO_ROOT, Lab, canonical_labs

SETUP = """import json, os, sys
from pathlib import Path


def find_repo_root(start):
    for candidate in [start, *start.parents]:
        if (candidate / 'pyproject.toml').is_file() and (candidate / 'src' / 'bni_training').is_dir():
            return candidate
    if os.getenv('BNI_REPO_ROOT'):
        return Path(os.environ['BNI_REPO_ROOT'])
    raise RuntimeError('Open this notebook inside the repository checkout, or set BNI_REPO_ROOT.')


ROOT = find_repo_root(Path.cwd().resolve())
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]
LAB_MODE = os.getenv('LAB_MODE', 'local').lower()
assert LAB_MODE in {'local', 'cai'}, 'LAB_MODE must be local or cai'
# A group workspace keeps its settings next to the notebooks: <workspace>/config/group.env
group_env = Path.cwd().parent / 'config' / 'group.env'
if group_env.is_file() and not os.getenv('GROUP_ENV_FILE'):
    os.environ['GROUP_ENV_FILE'] = str(group_env)
print({'lab_mode': LAB_MODE, 'python': sys.version.split()[0], 'group_env': 'found' if os.getenv('GROUP_ENV_FILE') else 'not found (local defaults)'})
"""

PARTICIPANT_CONFIG = """from bni_training.workshop.lab_context import LabContextError, resolve_lab_context

try:
    context = resolve_lab_context(LAB_MODE)
    print(context.describe())
    context.close()
except LabContextError as exc:
    print('Group configuration problem:', exc)
for name in ['GROUP_ID', 'DATASET_ID', 'MISSION_ID', 'GROUP_WORKSPACE', 'DATA_BACKEND']:
    print(name, 'is set' if os.getenv(name) else 'is not set (taken from group.env or the local default)')
"""

TRAINER_CONFIG = """ROLE = os.getenv('WORKSHOP_ROLE', 'participant').lower()
print({'role': ROLE, 'trainer_only_lab': True})
if LAB_MODE == 'cai' and ROLE != 'trainer':
    print('You can read this notebook, but the steps are for the trainer. Do not start or change any server.')
"""

LOAD = """from bni_training.lab_registry import get_lab, load_script_module

lab = get_lab('{id}')
module = load_script_module(lab.script_path)
print(lab.id, lab.title, '-', 'TRAINER ONLY' if lab.trainer_only else 'participant lab')
"""

RUN = """exit_code = module.main(['--mode', LAB_MODE])
outcome = {0: 'PASS', 3: 'SKIPPED'}.get(exit_code, 'FAIL')
print({'exit_code': exit_code, 'outcome': outcome})
assert outcome != 'FAIL', 'The lab reported FAIL; read the checks above'
"""

REVIEW = """try:
    context = resolve_lab_context(LAB_MODE)
    saved = sorted(p.name for p in (context.workspace / 'output').glob('*.json'))
    print('Saved in your group workspace:', saved)
    context.close()
except LabContextError as exc:
    print('No workspace to list:', exc)
"""


def md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": text.splitlines(keepends=True)}


def code(text: str) -> dict:
    return {
        "cell_type": "code",
        "metadata": {},
        "source": text.rstrip("\n").splitlines(keepends=True),
        "execution_count": None,
        "outputs": [],
    }


def notebook(lab: Lab) -> dict:
    trainer = lab.trainer_only
    audience = " and ".join(a.capitalize() for a in lab.audience)
    banner = (
        "\n> **TRAINER ONLY.** Read this notebook, but do not start or change any server.\n"
        if trainer
        else ""
    )
    cells = [
        md(
            f"# Lab {lab.id}: {lab.title}\n\n**Audience:** {audience}\n{banner}\n## Purpose\n{lab.purpose}\n\n## Theory\n{lab.theory}\n"
        ),
        md(
            "## How to run\n"
            "Run the cells from top to bottom; they are safe to run again.\n\n"
            "- `LAB_MODE=local` uses explicit mocks or local services. Steps that need a GPU, CAI, Impala or NFS are "
            "reported as `SKIPPED` with a reason.\n"
            "- `LAB_MODE=cai` uses the shared services from your environment. Nothing is mocked and a missing "
            "prerequisite is a `FAIL`.\n"
            "- Save results only in your group workspace. Never paste secrets into a notebook.\n"
            + ("- Participants do not run any deployment step in this lab.\n" if trainer else "")
        ),
        code(SETUP),
        code(TRAINER_CONFIG if trainer else PARTICIPANT_CONFIG),
        code(LOAD.format(id=lab.id)),
        md(
            "## Run the lab\nThe script below is the canonical implementation. It prints one check per line and finishes with a `LAB_STATUS` line.\n"
        ),
        code(RUN),
    ]
    if not trainer:
        cells += [md("## Review your saved output\n"), code(REVIEW)]
    cells += [
        md(
            f"## Expected outcome\n{lab.expected}\n\nEvery check is `PASS` or `SKIPPED` (with a reason). A `FAIL` stops the notebook.\n"
        ),
        md(
            "## Checkpoint\nExplain which component ran, which settings it used, and what you would expect if its service were unavailable.\n"
        ),
        md(
            "## Optional challenge\nChange one safe setting, rerun, and compare the results without touching shared services.\n"
        ),
        md(
            "## Cleanup\nStop only resources assigned to your group. Do not stop shared vLLM, Qdrant, Phoenix, LiteLLM or the Workshop Portal."
            if not trainer
            else "## Cleanup\nLeave the shared Applications as the workshop phase requires; follow the Application lifecycle in the trainer docs."
        ),
    ]
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3.10 (PBJ)", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.10"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def render(lab: Lab) -> str:
    return json.dumps(notebook(lab), indent=1) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check", action="store_true", help="Fail if a committed template differs from the registry"
    )
    args = parser.parse_args(argv)
    stale = []
    for lab in canonical_labs():
        path = REPO_ROOT / lab.notebook
        text = render(lab)
        if args.check:
            if not path.is_file() or path.read_text() != text:
                stale.append(lab.notebook)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        print(path.relative_to(REPO_ROOT))
    if stale:
        print("Out of date:", *stale, sep="\n  ")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
