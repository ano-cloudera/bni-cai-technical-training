import json
from pathlib import Path

LABS = {
    0: (
        "Environment Check",
        "Validate Python 3.10, PBJ Runtime, GPU visibility, CUDA, and the selected runtime profile.",
    ),
    1: (
        "Model Artifact",
        "Understand one-time download, NFS staging, Model Registry option, and artifact validation.",
    ),
    2: ("vLLM Server", "Preview the trainer-led single-GPU vLLM Application deployment (L40S sandbox or H200)."),
    3: ("LLM API Testing", "Test health, model discovery, and OpenAI-compatible chat completions."),
    4: ("CrewAI Fundamentals", "Run a small sequential agent example against the shared endpoint."),
    5: (
        "Impala or CSV Ask Your Data",
        "Use one explicit backend interface with Kerberos, LDAP, or CSV mode.",
    ),
    6: ("Semantic Layer", "Map approved metrics and dimensions to constrained SQL."),
    7: ("RAG with Qdrant", "Index and retrieve synthetic glossary content with mandatory group isolation."),
    8: ("Multi-Agent Workflow", "Run structured data plus a grounded narrative as a deterministic workflow and as a CrewAI crew."),
    9: (
        "Phoenix Observability",
        "Generate OpenInference traces and verify them in Phoenix: spans, kinds, latency, tokens, and group attributes.",
    ),
    10: ("LiteLLM Routing", "Route requests through the shared gateway with retry and controlled fallback."),
    11: ("LLM Guardrails", "Apply input, SQL, and output controls in transparent Python."),
    12: ("Agent Studio Client", "Call the one published final Agent Studio workflow."),
}


def notebook(number, title, objective, script):
    sections = [
        ("markdown", f"# Lab {number:02d}: {title}\n\n## Objectives\n{objective}\n"),
        (
            "markdown",
            "## Prerequisites\nRead `README.md`, copy the example file for your runtime profile to an untracked `.env`, "
            "and use your assigned `GROUP_ID`.\n\n"
            "- `LAB_MODE=local`: mocks or local services, complete code path, no cluster. GPU, CAI, Impala and NFS "
            "steps are reported as `SKIPPED` with a reason.\n"
            "- `LAB_MODE=cai`: real services from environment variables. No mocks. A missing prerequisite is a `FAIL`.\n",
        ),
        (
            "markdown",
            "## Guided Lab\nThe Python script is the canonical implementation. Review it before execution.\n",
        ),
        (
            "code",
            "from pathlib import Path\nimport os, sys, importlib.util\n"
            "ROOT = Path.cwd().parent if Path.cwd().name == 'notebooks' else Path.cwd()\n"
            "sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]\n"
            "LAB_MODE = os.getenv('LAB_MODE', 'local').lower()\n"
            "assert LAB_MODE in {'local', 'cai'}, 'LAB_MODE must be local or cai'\n"
            "print({'project_root': str(ROOT), 'python': sys.version.split()[0], 'lab_mode': LAB_MODE})\n",
        ),
        (
            "code",
            "required = ['GROUP_ID', 'DATA_MODE', 'VLLM_BASE_URL']\n"
            "print({name: ('set' if os.getenv(name) else 'not-set') for name in required})\n",
        ),
        (
            "code",
            f"script = ROOT / 'scripts' / '{script}'\n"
            "print(f'Canonical Python file: {script}')\n"
            "print('\\n'.join(script.read_text().splitlines()[:40]))\n",
        ),
        (
            "code",
            "spec = importlib.util.spec_from_file_location('training_lab', script)\n"
            "module = importlib.util.module_from_spec(spec)\n"
            "assert spec and spec.loader\n"
            "spec.loader.exec_module(module)\n"
            "print('Lab module loaded. main() is ready.')\n",
        ),
        (
            "code",
            "exit_code = module.main(['--mode', LAB_MODE])\n"
            "outcome = {0: 'PASS', 3: 'SKIPPED'}.get(exit_code, 'FAIL')\n"
            "print({'exit_code': exit_code, 'outcome': outcome})\n"
            "assert outcome != 'FAIL', 'Lab reported FAIL; read the checks above'\n",
        ),
        (
            "markdown",
            "## Expected Output\nA JSON list of checks, each `PASS` or `SKIPPED` (with the reason), followed by one "
            "`LAB_STATUS:` line. A `FAIL` stops the notebook.\n",
        ),
        (
            "markdown",
            "## Checkpoint\nExplain which component ran, which environment variables it used, and which failure mode is expected if the service is unavailable.\n",
        ),
        (
            "markdown",
            "## Optional Challenge\nChange one safe parameter, rerun the lab, and compare the result without changing shared service ownership.\n",
        ),
        (
            "markdown",
            "## Cleanup\nStop only resources assigned to your group. Do not stop shared vLLM, Qdrant, Phoenix, or LiteLLM Applications.\n",
        ),
    ]
    cells = []
    for kind, source in sections:
        cell = {"cell_type": kind, "metadata": {}, "source": source.splitlines(keepends=True)}
        if kind == "code":
            cell.update(execution_count=None, outputs=[])
        cells.append(cell)
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3.10 (PBJ)", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.10"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def main():
    out = Path("notebooks")
    out.mkdir(exist_ok=True)
    for number, (title, objective) in LABS.items():
        script = next(Path("scripts").glob(f"{number:02d}_*.py")).name
        path = out / (script.replace(".py", ".ipynb"))
        path.write_text(json.dumps(notebook(number, title, objective, script), indent=1) + "\n")
        print(path)


if __name__ == "__main__":
    main()
