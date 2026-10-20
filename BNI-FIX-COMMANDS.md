# BNI fix commands (copy and paste)

Run these in a JupyterLab Session terminal at BNI. One block, one paste. This is a working note, not part of the
documentation set; delete it when done.

## A. Phoenix: `No module named 'dateutil'` (still failing after a reinstall)

Cause (confirmed at BNI): in a Session, `PYTHONPATH` is `/opt/cmladdons/python/site-customize`, and the CAI runtime
add-ons (`/runtime-addons/...`) provide packages such as `six` and `python-dateutil`. pip sees them there, reports
"already satisfied" and does **not** install them into the venv. The Session can import them; the Application cannot,
because its `PYTHONPATH` is only the repository. Always install **without** `PYTHONPATH`.

Proof (confirmed at BNI): the first command prints `/opt/cmladdons/python/site-customize`, then the import fails with
`ModuleNotFoundError: No module named 'dateutil'`:

```bash
echo "$PYTHONPATH"; env -u PYTHONPATH /home/cdsw/.venvs/bni-phoenix/bin/python -c "import dateutil, pandas; print(dateutil.__file__)"
```

Fix: reinstall the lock without `PYTHONPATH` (safe to repeat). The output must now show `Collecting` and
`Installing collected packages`, not only `Requirement already satisfied`:

```bash
cd /home/cdsw/bni-cai-technical-training && env -u PYTHONPATH PIP_USER=false /home/cdsw/.venvs/bni-phoenix/bin/python -m pip install --no-user --retries 10 --timeout 60 -r requirements/observability.lock
```

Verify in a clean environment (must print a path inside `.venvs/bni-phoenix`, then the version):

```bash
env -u PYTHONPATH /home/cdsw/.venvs/bni-phoenix/bin/python -c "import dateutil, pandas, phoenix; print(dateutil.__file__, phoenix.__version__)"
```

Then restart the `bni-phoenix` Application and check `/healthz` and the UI.

Check the other venvs the same way (replace the imports to fit; reinstall their lock with `env -u PYTHONPATH` if it fails):

```bash
env -u PYTHONPATH /home/cdsw/.venvs/bni-rag/bin/python -c "import pandas, qdrant_client, streamlit, sentence_transformers; print('ok')"
env -u PYTHONPATH /home/cdsw/.venvs/bni-litellm/bin/python -c "import litellm; print('ok')"
```

## A2. LiteLLM: `No module named 'dateutil'` (same cause, venv `bni-litellm`)

Seen at BNI: the LiteLLM log ends with `ModuleNotFoundError: Missing dependency No module named 'dateutil'` (raised
while importing `boto3`). Same fix as Phoenix: reinstall the lock without `PYTHONPATH`.

```bash
cd /home/cdsw/bni-cai-technical-training && env -u PYTHONPATH PIP_USER=false /home/cdsw/.venvs/bni-litellm/bin/python -m pip install --no-user --retries 10 --timeout 60 -r requirements/gateway.lock
```

Verify in a clean environment (the path must be inside `.venvs/bni-litellm`):

```bash
env -u PYTHONPATH /home/cdsw/.venvs/bni-litellm/bin/python -c "import dateutil, boto3, litellm; print(dateutil.__file__)"
```

Then restart the `bni-litellm` Application.

If `bni-rag` fails the same way (Portal, Lab 07), reinstall its lock the same way:

```bash
cd /home/cdsw/bni-cai-technical-training && env -u PYTHONPATH PIP_USER=false /home/cdsw/.venvs/bni-rag/bin/python -m pip install --no-user --retries 10 --timeout 60 -r requirements/rag.lock
```

## A3. Portal: "The portal is not configured: FileNotFoundError"

Seen at BNI: the Portal page shows this message. The page hides the detail on purpose, and the Application log does not
show it either. The log ends after the `qdrant_client` warning.

Already ruled out at BNI: the bge-m3 model is fine. This test printed `loaded` (391 weights), so no `2_Normalize`
folder is needed:

```bash
env -u PYTHONPATH /home/cdsw/.venvs/bni-rag/bin/python -c "from sentence_transformers import SentenceTransformer as S; S('/home/cdsw/models/bge-m3', device='cpu'); print('loaded')" 2>&1 | tail -8
```

Find the real error by building the Portal service the way the Application does (folder `/home/cdsw`, the Portal
environment). It does not touch the running Portal. It needs `VLLM_URL`, `QDRANT_URL` and `PHOENIX_UI_URL` to be set in
this terminal (section 0 of `BNI-TESTING-COMMANDS.md`):

```bash
cd /home/cdsw && env PYTHONPATH=/home/cdsw/bni-cai-technical-training/src:/home/cdsw/bni-cai-technical-training WORKSHOP_RUNTIME_DIR=/home/cdsw/workshop-runtime PORTAL_MODE=cai PORTAL_LLM_ROUTE=vllm VLLM_BASE_URL="$VLLM_URL/v1" SERVED_MODEL_NAME=qwen3.5-9b QDRANT_URL="$QDRANT_URL" EMBEDDING_MODEL_PATH=/home/cdsw/models/bge-m3 PHOENIX_COLLECTOR_ENDPOINT="$PHOENIX_UI_URL/v1/traces" DATA_BACKEND=csv PORTAL_ENFORCE_SINGLE_INSTANCE=false /home/cdsw/.venvs/bni-rag/bin/python -c "from bni_training.workshop.portal.service import PortalService; PortalService.from_env(); print('service ok')" 2>&1 | tail -12
```

- `service ok`: code and data are fine. Compare each value in the Portal Application environment with the command above.
- A traceback: the file name in its last lines is the missing file. Write the cause and fix here.

## B. Embedding model bge-m3 (optional; needed for Portal retrieval and Lab 07)

Upload `bge-m3.zip` (1.27 GB) to `/home/cdsw/` with the JupyterLab file panel, then:

```bash
cd /home/cdsw && echo "2354fd20310daa22a7b6a8728aa09c8578cde71a17d1d7e5bdc26094739d9b08  bge-m3.zip" | sha256sum -c
```

Must print `bge-m3.zip: OK`. Then:

```bash
unzip -q /home/cdsw/bge-m3.zip -d /home/cdsw/models && ls /home/cdsw/models/bge-m3/modules.json
```

Test loading (must print `1024`):

```bash
/home/cdsw/.venvs/bni-rag/bin/python -c "from sentence_transformers import SentenceTransformer as S; m=S('/home/cdsw/models/bge-m3', device='cpu'); print(len(m.encode(['test'])[0]))"
```

Portal Application environment, then restart the Portal:

```text
EMBEDDING_MODEL_PATH=/home/cdsw/models/bge-m3
```

Without the model, delete `QDRANT_URL` and `EMBEDDING_MODEL_PATH` from the Portal environment. The Portal still works,
only without retrieval.

## C. Code version and Portal check

```bash
cd /home/cdsw/bni-cai-technical-training && git pull --ff-only origin main && git log --oneline -1
```

The commit must be `e8248a7` or newer. Restart the Portal and LiteLLM Applications. A Portal answer must not start with
"Thinking Process".
