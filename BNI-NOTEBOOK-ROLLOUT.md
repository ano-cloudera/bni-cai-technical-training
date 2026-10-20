# BNI notebook rollout checklist

Working note: what has to be done at BNI so the participant notebooks (Labs 00 and 03 to 12) run in `cai` mode. Everything
below was found in the sandbox on 2026-10-21 unless a line says otherwise. At BNI the **scripts** passed; the **notebooks
have not been run at BNI yet**. Delete this note when done.

Status words: **BNI done** (seen at BNI), **sandbox** (seen only in the sandbox), **to do** (not done anywhere).

## 0. Pre-class runbook at BNI (do this in order, before participants arrive)

Each step has a pass criterion. Stop at the first failure and use the matching section below (or `BNI-FIX-COMMANDS.md`).
Terminal variables come from section 0b of `BNI-TESTING-COMMANDS.md` (`APPS_DOMAIN`, `VLLM_URL`, and so on).

| # | Do | Pass when |
|---|---|---|
| 1 | Laptop: `git push origin main` | `git status -sb` shows `main...origin/main` with no "ahead" |
| 2 | BNI Session: `git pull --ff-only origin main` (stash first if refused, section 1) | `git log --oneline -1` is the pushed commit |
| 3 | Register the kernel `bni-rag` (section 3) | "BNI rag (py3.10)" is in the kernel list after a browser reload |
| 4 | Check the Applications (section 4): vLLM has **1 GPU** and `VLLM_TOOL_CALL_PARSER`; Portal has `WORKSHOP_RUNTIME_DIR`; LiteLLM has `SSL_CERT_FILE` | the five health checks of `BNI-TESTING-COMMANDS.md` section 2 print 200 |
| 5 | Set the **project** environment variables of section 5, then restart the Session | a notebook cell `import os; print(os.getenv("QDRANT_URL"))` prints the URL ending `:443` |
| 6 | Refresh the group workspaces (section 2) | `grep -c "proved" .../group_03/notebooks/05_semantic_layer.ipynb` prints 1 or more (the guided notebooks 04 to 08 arrived) and `grep -c load_group_env` on the same file prints 1 or more |
| 7 | Ask one sample question in the Portal for `group_03` (wait for Completed) | "My outputs (1)" appears |
| 8 | **Day 1 notebooks.** Run, from `group_03/notebooks`, with the kernel BNI rag, in this order: 00, 03, 04, 05, 06, 07, 08, 09. Lab 07 needs `QDRANT_URL` and `EMBEDDING_MODEL_PATH`; Lab 09 needs `PHOENIX_COLLECTOR_ENDPOINT` and `PHOENIX_UI_URL` (project variables, step 5) | each prints `LAB_STATUS: ... mode=cai status=PASS`. The line must say `mode=cai`, never `mode=local`. Lab 04 shows `group_03` in its first step, not `group_01`. After Lab 09 a trace for `group_03` is visible in the Phoenix UI |
| 9 | **Day 2 notebooks**, if time: 10, 11, 12 (12 needs step 7 first; 10 needs a key and the LiteLLM Application, section 5) | same |
| 10 | Clean the test group so participants start clean: delete any `*_v2.ipynb` copy in `group_03/notebooks`, then reset (dry run first, then `--yes`): `scripts/reset_group_workspace.py --group-id group_03`, add `--include-notebooks` to restore the notebooks | the dry run lists only `group_03`, and `ls group_03/notebooks` shows the 13 standard names only |
| 11 | Rotate `LITELLM_MASTER_KEY` and decide Lab 10 (section 5, last paragraph) | `models=200` with the new key |

Step 5 test cell is the check that a project variable reaches the notebook kernel; this was **not** tested in the sandbox. If it
prints `None`, restart the Session once more; if it still prints `None`, fall back to the temporary first cell of section 5.

Day split: **Day 1 is Lab 00 and Labs 03 to 09; Day 2 is Labs 10 to 12.** Applications follow the same split: Day 1 runs vLLM,
Qdrant, Phoenix and the Portal; LiteLLM joins on Day 2 (never more than five at once). Both days use the same workspaces and
the same runtime folder; nothing is hidden or moved. The split is only the instruction on the slide, because a second template folder or a
second runtime root would split the Portal, the validators and the tests (they expect all 13 notebooks).

What participants do (put this on a slide or in the guide):

1. Open **Lab 00** from `workshop-runtime/groups/group_XX/notebooks/` (their own group folder, never `notebooks/templates`).
2. **Kernel, Change Kernel, BNI rag (py3.10)** in every notebook.
3. Run all cells from the top. Do not edit the setup cell.

## 1. Repository changes the notebooks need (`git pull` at BNI)

All of these are on `main` after the push. Without them the notebooks run the local mock or fail.

| Change | Why |
|---|---|
| Every notebook loads `config/group.env` before it reads `LAB_MODE` | Only Lab 03 did, so Labs 04 to 12 ran `mode=local` (mock) from a group workspace |
| Lab 07 embeds the question with bge-m3 in `cai` mode | The 256-dimension stand-in was rejected by the 1024-dimension collection |
| Lab 11 client sends `enable_thinking=false` | With thinking on, the answer began with "Thinking Process: 1." and the number rule blocked it |
| CrewAI `LLM` sends `enable_thinking=false` | Labs 08 and 09 showed `0 data tool call(s)` |
| vLLM launcher option `VLLM_TOOL_CALL_PARSER` | CrewAI needs tool calling (`400 "auto" tool choice requires ...`) |
| `scripts/index_all_groups.py` | Indexes glossary and mission notes of all ten groups with bge-m3 |
| Labs 04 to 09 rewritten as guided lessons | One setup cell, explained steps with a prediction, pandas tables, a real exercise, a closing list of what the participant proved. File names and saved outputs are unchanged. They replace the old notebooks of the same names in the templates, so a workspace refresh (section 2) is what delivers them |

After `git pull`, if git says local changes would be overwritten (a notebook was run inside the repository), stash them:

```bash
cd /home/cdsw/bni-cai-technical-training && git stash push -m "local run" -- notebooks && git pull --ff-only origin main && git log --oneline -1
```

Never open or run a notebook from `notebooks/templates/` or `notebooks/drafts/`: the templates are the source for the group
copies and must stay clean. Open the copy under `workshop-runtime/groups/group_XX/notebooks/`.

## 2. Create or refresh the group workspaces at BNI (to do)

The group notebooks are copies of the templates, so they only change when the workspaces are refreshed. `--overwrite` replaces
the notebooks of **all ten groups** and backs the old ones up under `shared/state/backups/`. Do it before participants edit.

```bash
export WORKSHOP_RUNTIME_DIR=/home/cdsw/workshop-runtime; cd /home/cdsw/bni-cai-technical-training; env -u PYTHONPATH /home/cdsw/.venvs/bni-rag/bin/python scripts/prepare_group_workspaces.py --lab-mode cai --vllm-base-url "$VLLM_URL" --overwrite --yes --apply
```

`VLLM_URL` must be set in that terminal (section 0b of `BNI-TESTING-COMMANDS.md`); without it the script stops with `REFUSED`.
Check a refreshed notebook: `grep -c "load_group_env" /home/cdsw/workshop-runtime/groups/group_03/notebooks/04_csv_data_access.ipynb`
must print 1 or more. Close old notebook tabs in JupyterLab without saving, and reopen from the group folder.

## 3. Add the notebook kernel at BNI (to do)

The default notebook kernel has no `crewai`, `qdrant_client` or `openinference`. The `bni-rag` venv has them but no `ipykernel`,
so install it once and register the kernel (sandbox: both steps worked, `pip check` clean):

```bash
cd /home/cdsw/bni-cai-technical-training && env -u PYTHONPATH PIP_USER=false /home/cdsw/.venvs/bni-rag/bin/python -m pip install --no-user --retries 10 --timeout 60 "ipykernel==7.3.0"
```

```bash
env -u PYTHONPATH /home/cdsw/.venvs/bni-rag/bin/python -m ipykernel install --user --name bni-rag --display-name "BNI rag (py3.10)"
```

The kernel is stored in `/home/cdsw/.local/share/jupyter/kernels/bni-rag`, so every Session of the project sees it. Reload
JupyterLab, then in each notebook choose **Kernel, Change Kernel, BNI rag (py3.10)** (once per notebook).
Open item: the participant guide does not say this yet, and 40 participants each choose the kernel themselves.

## 4. Application environment (Portal, vLLM, LiteLLM)

| Application | Variable | Status |
|---|---|---|
| Portal | `WORKSHOP_RUNTIME_DIR=/home/cdsw/workshop-runtime` | BNI done (in the Portal form). **Sandbox was missing it**: the Portal wrote answers to `<repo>/workshop/runtime/...`, so Lab 12 found no answer. Fixed in the sandbox, Portal restarted |
| Portal | `EMBEDDING_MODEL_PATH`, `QDRANT_URL` with `:443`, `SSL_CERT_FILE`, `PORTAL_MAX_TOKENS=512` | BNI done |
| vLLM | `VLLM_TOOL_CALL_PARSER=qwen3_coder`, **Number of GPUs = 1** after every Update Application | BNI done |
| LiteLLM | `SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt`, new `LITELLM_MASTER_KEY` | SSL done; key rotation to do |

Order for the Portal check: ask one sample question for `group_03` in the Portal and wait for Completed. Lab 12 reads that
saved answer from `groups/group_03/output/<session>/answer-NNN.json`.

## 5. Variables the notebooks need (decision to do)

A `export` in a terminal does not reach a notebook kernel. Today each notebook needs a temporary first cell
(`os.environ[...] = ...`, delete it afterwards):

| Lab | Variables |
|---|---|
| 00 | `RUNTIME_PROFILE`, `DATA_MODE=csv`, `VLLM_API_KEY=EMPTY`, `PHOENIX_COLLECTOR_ENDPOINT`, `LITELLM_BASE_URL`, `WORKSHOP_PORTAL_URL` |
| 07 | `QDRANT_URL` (with `:443`), `EMBEDDING_MODEL_PATH=/home/cdsw/models/bge-m3` |
| 09 | `PHOENIX_COLLECTOR_ENDPOINT` (ending `/v1/traces`), `PHOENIX_UI_URL` |
| 10 | `LITELLM_BASE_URL` (ending `/v1`), `LITELLM_API_KEY` (type it with `getpass`; never save it in a notebook) |
| 12 | `WORKSHOP_PORTAL_URL` |
| 03, 04, 05, 06, 08, 11 | none (08 needs vLLM tool calling) |

For 40 participants a temporary cell is too much to ask. Decision: the trainer sets these as **project environment variables** once
(CAI project settings, Advanced, Environment Variables), and every new Session, and so every notebook kernel, inherits
them. No code change. Replace `<apps-domain>` with the BNI Applications domain (kept out of the repository on purpose):

```text
QDRANT_URL=https://bni-qdrant.<apps-domain>:443
EMBEDDING_MODEL_PATH=/home/cdsw/models/bge-m3
PHOENIX_COLLECTOR_ENDPOINT=https://bni-phoenix.<apps-domain>/v1/traces
PHOENIX_UI_URL=https://bni-phoenix.<apps-domain>
LITELLM_BASE_URL=https://bni-litellm-gateway.<apps-domain>/v1
WORKSHOP_PORTAL_URL=https://bni-workshop-portal.<apps-domain>
SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
RUNTIME_PROFILE=bni-h200
DATA_MODE=csv
VLLM_API_KEY=EMPTY
```

These hold no secret: `VLLM_API_KEY=EMPTY` is a placeholder (the vLLM Application has no key). Restart the Session after changing
them. **Never put `LITELLM_API_KEY` or `LITELLM_MASTER_KEY` here**: every participant can read project variables.

Lab 10 needs a LiteLLM key, and only the master key exists (per-group virtual keys need Postgres, postponed). Decide before class:
(a) the trainer runs Lab 10 as a demonstration; or (b) participants type a workshop-only key with `getpass` in the Lab 10
notebook and the trainer rotates the key right after class. Do not put the key in a notebook, a Session variable or a slide.

## 6. Data and checks at BNI

- Glossary and mission notes of all ten groups: BNI done (`index_all_groups.py`, 6 points per group). The sandbox is done too.
- Embedding model `bge-m3` on NFS: BNI done. Sandbox: downloaded in a Session; `Stale file handle` on NFS once, rerun fixed it.
- Run notebooks 00, 03 and one heavy lab (07 or 08) for one group at BNI before the workshop (to do).

## 7. Sandbox results of the notebooks (kernel BNI rag, group_03, `mode=cai`)

Original notebooks, pass: 00, 03, 04, 05, 06, 07, 08, 09, 10, 11 (11 with the thinking fix) and 12 (after `WORKSHOP_RUNTIME_DIR` was
set on the sandbox Portal and one sample question was asked: `LAB_STATUS: lab=12 mode=cai status=PASS passed=7`). Not run: 01
and 02 (trainer only). Each lab was run with the temporary variable cells of section 5, not with permanent Session variables.

Guided notebooks (the rewritten Labs 04 to 09), run in the sandbox from a group workspace, `mode=cai`: 04 `passed=10`, 05
`passed=9`, 06 `passed=8`, 07 `passed=10`, 09 `passed=9`, all PASS. Lab 08 in its final text (the question written into both
tasks, a new default exercise criterion): `passed=9`, PASS. All guided notebooks of Day 1 (04 to 09) have now passed in the sandbox
with `mode=cai`. None of them has run at BNI yet: do step 8 there.

## 8. Known gaps (not blocking, to fix after the workshop)

- Lab 12 prints `'group_locked': False, 'identity_verified': False` in `cai` mode (values are only computed locally).
- Each Session loads the 2 GB bge-m3 model on CPU for Lab 07; memory and load time for 40 Sessions are not measured.
- Notebook redesign (explained steps, pandas tables): a draft of Lab 04 is in `notebooks/drafts/`. Renumbering the labs is postponed.
- `.ipynb_checkpoints` folders are not in `.gitignore`.
