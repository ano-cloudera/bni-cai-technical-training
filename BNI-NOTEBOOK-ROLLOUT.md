# BNI notebook rollout checklist

Working note: what has to be done at BNI so the participant notebooks (Labs 00 and 03 to 12) run in `cai` mode. Everything
below was found in the sandbox on 2026-10-21 unless a line says otherwise. At BNI the **scripts** passed; the **notebooks
have not been run at BNI yet**. Delete this note when done.

Status words: **BNI done** (seen at BNI), **sandbox** (seen only in the sandbox), **to do** (not done anywhere).

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

For 40 participants this is too much to ask. Proposal (not built): write the non-secret service URLs into `group.env` when
the workspace is generated, and set only the LiteLLM key in the Session environment.

## 6. Data and checks at BNI

- Glossary and mission notes of all ten groups: BNI done (`index_all_groups.py`, 6 points per group). The sandbox is done too.
- Embedding model `bge-m3` on NFS: BNI done. Sandbox: downloaded in a Session; `Stale file handle` on NFS once, rerun fixed it.
- Run notebooks 00, 03 and one heavy lab (07 or 08) for one group at BNI before the workshop (to do).

## 7. Sandbox results of the notebooks (kernel BNI rag, group_03, `mode=cai`)

Pass: 00, 03, 04, 05, 06, 07, 08, 09, 10, 11 (11 with the thinking fix). Lab 12: waiting for the Portal answer to land in the
shared runtime folder (item 4). Not run: 01 and 02 (trainer only).

## 8. Known gaps (not blocking, to fix after the workshop)

- Lab 12 prints `'group_locked': False, 'identity_verified': False` in `cai` mode (values are only computed locally).
- Each Session loads the 2 GB bge-m3 model on CPU for Lab 07; memory and load time for 40 Sessions are not measured.
- Notebook redesign (explained steps, pandas tables): a draft of Lab 04 is in `notebooks/drafts/`. Renumbering the labs is postponed.
- `.ipynb_checkpoints` folders are not in `.gitignore`.
