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

Seen at BNI: the Portal page shows this message and the log ends after the `qdrant_client` warning, just before the
embedding model loads. The page hides the detail on purpose. Reproduce it in a Session to read the real error (the last
8 lines):

```bash
env -u PYTHONPATH /home/cdsw/.venvs/bni-rag/bin/python -c "from sentence_transformers import SentenceTransformer as S; S('/home/cdsw/models/bge-m3', device='cpu'); print('loaded')" 2>&1 | tail -8
```

Most likely cause: `modules.json` names a `2_Normalize` folder, which Hugging Face does not store because it is empty,
so it is missing from the unzipped model. If the error mentions `2_Normalize`, create it and repeat the test above (it
must print `loaded`):

```bash
mkdir -p /home/cdsw/models/bge-m3/2_Normalize
```

Then restart the `bni-workshop-portal` Application.

Other causes to rule out if the error is something else:

- `EMBEDDING_MODEL_PATH` in the Portal environment must be exactly `/home/cdsw/models/bge-m3`.
- `QDRANT_URL` must be the Qdrant Application URL (no path), and `WORKSHOP_RUNTIME_DIR` must be
  `/home/cdsw/workshop-runtime` (it must contain `groups` and `shared`).

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
