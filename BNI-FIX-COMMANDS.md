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

## A4. Lab 00 fails only on `runtime_profile`

Seen at BNI: every check passes except `runtime_profile` ("Set RUNTIME_PROFILE to sandbox-l40s or bni-h200"). Set it,
then run the lab again:

```bash
export RUNTIME_PROFILE=bni-h200
```

```bash
env -u PYTHONPATH /home/cdsw/.venvs/bni-rag/bin/python scripts/00_environment_validation.py --mode cai 2>&1 | tail -3
```

## A5. Portal: wrong `EMBEDDING_MODEL_PATH` (found at BNI)

Cause of the Portal "not configured: FileNotFoundError" at BNI: the value was `/home/dcsw/models/bge-m3` (`dcsw`, not
`cdsw`). Fix: `EMBEDDING_MODEL_PATH=/home/cdsw/models/bge-m3`, then **Update Application**. Also add
`PORTAL_MAX_TOKENS=512`. Confirmed: the Portal then answers a sample question without "Thinking Process".

## A6. Lab 10: `HTTPError: HTTP Error 500: Internal Server Error`

Seen at BNI: `litellm_config` passes (aliases `qwen-primary` and `training-fallback` are read) but the chat call
returns HTTP 500. The gateway is up; it fails while forwarding to vLLM. The real message (the key is not shown; set it
first with `read -rs LITELLM_API_KEY; export LITELLM_API_KEY` if the variable is empty):

```bash
curl -s -H "Authorization: Bearer $LITELLM_API_KEY" -H "Content-Type: application/json" "$LITELLM_URL/v1/chat/completions" -d '{"model":"qwen-primary","messages":[{"role":"user","content":"hi"}],"max_tokens":16}'
```

Seen at BNI: `litellm.InternalServerError: OpenAIException - Connection error ... model group 'qwen-primary' failed ...
No fallback was attempted.` The LiteLLM environment was correct (`VLLM_BASE_URL`, `MOCK_FALLBACK_BASE_URL`,
`VLLM_API_KEY`), and the Portal and `curl` reach vLLM, so the likely cause is the TLS certificate: the vLLM URL is HTTPS
with an internal BNI certificate. `curl` in a Session uses the system CA list; LiteLLM (Python, `certifi`) does not.

Prove it, one command at a time:

```bash
ls /etc/ssl/certs/ca-certificates.crt
```

```bash
env -u PYTHONPATH /home/cdsw/.venvs/bni-litellm/bin/python -c "import httpx,os; print(httpx.get(os.environ['VLLM_URL']+'/health').status_code)" 2>&1 | tail -2
```

```bash
env -u PYTHONPATH SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt /home/cdsw/.venvs/bni-litellm/bin/python -c "import httpx,os; print(httpx.get(os.environ['VLLM_URL']+'/health').status_code)" 2>&1 | tail -2
```

If the second command fails with `CERTIFICATE_VERIFY_FAILED` and the third prints `200`, the cause is confirmed. If the
file in the first command does not exist, look for `/etc/pki/tls/certs/ca-bundle.crt` instead.

Fix: add one variable to the `bni-litellm-gateway` Application environment, **Update Application**, then run Lab 10
again. Never switch TLS verification off.

```text
SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
```

If the second command already prints `200`, TLS is not the cause: read the last 20 lines of the `bni-litellm-gateway` log
(no keys) to see which address LiteLLM tried. Other causes to rule out: `VLLM_BASE_URL` must end with `/v1` with no
placeholder left, and vLLM must serve `qwen3.5-9b` (`curl -s "$VLLM_URL/v1/models"`).

Key hygiene: a screenshot of the LiteLLM environment screen showed the first characters of `LITELLM_MASTER_KEY`. Treat
that key as leaked: after Lab 10, create a new one (`python3 -c "import secrets; print('sk-' + secrets.token_hex(32))"`),
replace it in the Application, restart, and set `LITELLM_API_KEY` again in the Session. Never screenshot the value column.

Record the final cause and fix here once Lab 10 passes.

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
