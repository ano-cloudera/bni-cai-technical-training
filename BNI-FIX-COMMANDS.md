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

Seen at BNI (twice). First: "Set RUNTIME_PROFILE to sandbox-l40s or bni-h200". After setting it, the check still failed with
`bni-h200: missing ['DATA_MODE', 'VLLM_API_KEY', 'PHOENIX_COLLECTOR_ENDPOINT', 'LITELLM_BASE_URL', 'WORKSHOP_PORTAL_URL']`.
The profile requires those variables. Set them all (one line), then run the lab again:

```bash
export RUNTIME_PROFILE=bni-h200; export DATA_MODE=csv; export VLLM_API_KEY=EMPTY; export PHOENIX_COLLECTOR_ENDPOINT="$PHOENIX_UI_URL/v1/traces"; export LITELLM_BASE_URL="$LITELLM_URL/v1"; export WORKSHOP_PORTAL_URL="$PORTAL_URL"
```

```bash
env -u PYTHONPATH /home/cdsw/.venvs/bni-rag/bin/python scripts/00_environment_validation.py --mode cai 2>&1 | grep -E -B1 -A1 '"status": "FAIL"|LAB_STATUS'
```

`DATA_MODE=csv` is the default participant backend. `VLLM_API_KEY=EMPTY` because the shared vLLM Application has no key.
Without the Phoenix, LiteLLM and Portal variables, three more checks show `SKIPPED`.

## A5. Portal: wrong `EMBEDDING_MODEL_PATH` (found at BNI)

Cause of the Portal "not configured: FileNotFoundError" at BNI: the folder name in the path had two letters swapped (`dcsw`
instead of `cdsw`). Fix: `EMBEDDING_MODEL_PATH=/home/cdsw/models/bge-m3`, then **Update Application**. Also add
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

Confirmed at BNI: without the variable, Python fails with `CERTIFICATE_VERIFY_FAILED: unable to get local issuer
certificate`; with it, the same request returns `200`. After adding `SSL_CERT_FILE` to the `bni-litellm-gateway`
Application and restarting it, Lab 10 passed (`LAB_STATUS: lab=10 mode=cai status=PASS passed=2 skipped=1 failed=0`).

The same trust problem applies to any Python code that calls an HTTPS BNI Application with `httpx` or `requests`
(`certifi`), for example the Qdrant client and the Phoenix exporter used by Labs 07 and 09 and by the Portal. Before those
labs, in the Session terminal:

```bash
export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt; export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
```

and add `SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt` to the Portal Application environment too. Never switch TLS
verification off.

## A7. Lab 07 / glossary indexing: `[Errno 111] Connection refused` (Qdrant)

Seen at BNI: `scripts/index_glossary.py ... --execute` fails in `qdrant_client` (`collection_exists`) with
`ResponseHandlingException: [Errno 111] Connection refused`. This is not a certificate problem. `curl` to
`$QDRANT_URL/readyz` returns 200 because `curl` uses port 443 for `https://`. Suspected cause: the Python Qdrant client
uses its default port 6333 when the URL has no port, and CAI exposes only 443. Prove it, one command at a time:

```bash
env -u PYTHONPATH /home/cdsw/.venvs/bni-rag/bin/python -c "import os; from qdrant_client import QdrantClient as C; print(C(url=os.environ['QDRANT_URL']).get_collections())" 2>&1 | tail -2
```

```bash
env -u PYTHONPATH /home/cdsw/.venvs/bni-rag/bin/python -c "import os; from qdrant_client import QdrantClient as C; print(C(url=os.environ['QDRANT_URL']+':443').get_collections())" 2>&1 | tail -2
```

The first fails with `Connection refused` and the second prints `collections=[...]` (it may be empty): confirmed. If the
second fails with `CERTIFICATE_VERIFY_FAILED`, set the CA variables from A6 and repeat.

Confirmed at BNI: without a port the first command fails with `[Errno 111] Connection refused` (the client tries
6333). With `:443` the connection is made and it stops at the next problem, `CERTIFICATE_VERIFY_FAILED: unable to get
local issuer certificate`, which is the same TLS trust problem as in A6. So two fixes are needed together: the port and
the CA list.

In the Session terminal (one line):

```bash
export QDRANT_URL="https://bni-qdrant.$APPS_DOMAIN:443"; export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt; export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
```

Check (must print `collections=[...]`, it may be empty):

```bash
env -u PYTHONPATH /home/cdsw/.venvs/bni-rag/bin/python -c "import os; from qdrant_client import QdrantClient as C; print(C(url=os.environ['QDRANT_URL']).get_collections())" 2>&1 | tail -2
```

Then index the test group's glossary and run Lab 07:

```bash
env -u PYTHONPATH EMBEDDING_MODEL_PATH=/home/cdsw/models/bge-m3 /home/cdsw/.venvs/bni-rag/bin/python scripts/index_glossary.py --group-id group_03 --execute
```

```bash
env -u PYTHONPATH EMBEDDING_MODEL_PATH=/home/cdsw/models/bge-m3 /home/cdsw/.venvs/bni-rag/bin/python scripts/07_qdrant_rag.py --mode cai 2>&1 | tail -3
```

In the **Portal** Application environment set these two, then **Update Application**. Without them the Portal glossary
search fails the same way:

```text
QDRANT_URL=https://bni-qdrant.<apps-domain>:443
SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
```

Open: the repository could default to port 443 for an `https://` Qdrant URL without a port, so a trainer never has to
add it. Record the Lab 07 result here once it runs.

## A8. Glossary indexing: `ReadTimeout` at `create_payload_index`, then Portal glossary check

Seen at BNI: Lab 07 passed (`passed=5 failed=0`), but `index_glossary.py --execute` ended with
`ResponseHandlingException: The read operation timed out` at `create_payload_index`. That step runs **before** the points
are written, so the glossary of `group_03` is probably not stored. The first call on a new collection can be slow through
the CAI gateway. Running it again is safe (the collection exists and the points are overwritten by id).

Run it again, in the same terminal that has the variables from A7:

```bash
env -u PYTHONPATH EMBEDDING_MODEL_PATH=/home/cdsw/models/bge-m3 /home/cdsw/.venvs/bni-rag/bin/python scripts/index_glossary.py --group-id group_03 --execute 2>&1 | tail -4
```

Pass: a JSON result with `"group_id": "group_03"` and a `documents` count, no traceback. If it times out again, send the last
lines; the client timeout can be raised.

Check that the points exist for the group (the count must be above 0):

```bash
env -u PYTHONPATH /home/cdsw/.venvs/bni-rag/bin/python -c "import os; from qdrant_client import QdrantClient as C, models as m; c=C(url=os.environ['QDRANT_URL'], timeout=60); print(c.count(collection_name='bni_training_knowledge', count_filter=m.Filter(must=[m.FieldCondition(key='group_id', match=m.MatchValue(value='group_03'))])))" 2>&1 | tail -2
```

If this reports that the collection does not exist, the collection has another name: print the names with
`print(c.get_collections())` and use that name.

Portal check, after `QDRANT_URL` (with `:443`), `SSL_CERT_FILE` and `PORTAL_MAX_TOKENS=512` are in the Portal
environment and you clicked **Update Application**:

1. Open the Portal, choose `group_03`, click one sample question.
2. Open the panel "Related glossary and scenario notes". It must show notes (not be empty). That proves retrieval.

## A9. Common slips seen at BNI (check these before anything else)

### A9.1 Wrong folder

Symptom: `can't open file '/home/cdsw/workshop-runtime/scripts/index_glossary.py'`. The script is in the repository.
Run lab and indexing commands from there:

```bash
cd /home/cdsw/bni-cai-technical-training
```

### A9.2 `Connection refused` from `qdrant_client` again

Cause: `QDRANT_URL` in this terminal has no `:443` (an old `export` line was pasted, or the variables were lost after a
new Session). Check it:

```bash
echo "$QDRANT_URL"
```

If it does not end with `:443`, set it (the last line printed must end with `:443`; confirmed at BNI):

```bash
export QDRANT_URL="https://bni-qdrant.$APPS_DOMAIN:443"; export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt; export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt; echo "$QDRANT_URL"
```

Then repeat the glossary indexing, from the repository folder (pass: a JSON result with `"group_id": "group_03"` and a
`documents` count, no traceback; a `ReadTimeout` means the client timeout is too short for the first call, send the last
lines):

```bash
env -u PYTHONPATH EMBEDDING_MODEL_PATH=/home/cdsw/models/bge-m3 /home/cdsw/.venvs/bni-rag/bin/python scripts/index_glossary.py --group-id group_03 --execute 2>&1 | tail -4
```

Count the stored points for the group (the number must be above 0):

```bash
env -u PYTHONPATH /home/cdsw/.venvs/bni-rag/bin/python -c "import os; from qdrant_client import QdrantClient as C, models as m; c=C(url=os.environ['QDRANT_URL'], timeout=60); print(c.count(collection_name='bni_training_knowledge', count_filter=m.Filter(must=[m.FieldCondition(key='group_id', match=m.MatchValue(value='group_03'))])))" 2>&1 | tail -2
```

If it still says `Connection refused` with `:443`, run the two connection tests of A7 and send their output.

### A9.3 Wrong variable name in the Portal environment

`PORTAL_MAX_TOKEN` (missing S) is ignored. The name must be `PORTAL_MAX_TOKENS` with value `512`. Also confirm the Portal
`QDRANT_URL` value ends with `:443` (the form cuts the value off on screen), then **Update Application**.

### A9.4 A new Session loses every variable

Use section 0b of `BNI-TESTING-COMMANDS.md`; it already contains `:443`, `SSL_CERT_FILE` and `RUNTIME_PROFILE`.

## A10. Lab 09: `Missing required environment variables: PHOENIX_COLLECTOR_ENDPOINT`

Seen at BNI: the variable was not set in that terminal (it is lost with a new Session). Set it, then run the lab again:

```bash
export PHOENIX_COLLECTOR_ENDPOINT="$PHOENIX_UI_URL/v1/traces"
```

```bash
cd /home/cdsw/bni-cai-technical-training; env -u PYTHONPATH /home/cdsw/.venvs/bni-rag/bin/python scripts/09_phoenix_monitoring.py --mode cai 2>&1 | grep -E -B1 -A1 '"status": "FAIL"|LAB_STATUS'
```

If it then fails with `CERTIFICATE_VERIFY_FAILED`, set `SSL_CERT_FILE` and `REQUESTS_CA_BUNDLE` (A6). If it fails on the
endpoint itself (404 or connection error), try `$PHOENIX_UI_URL/v1/traces` without a trailing slash, then send the
exact error: this path is still a guess.

## A11. Lab 08: `400 "auto" tool choice requires --enable-auto-tool-choice and --tool-call-parser to be set`

Seen at BNI: Lab 06 passes and Lab 08's `plain_workflow` passes (3 rows with SQL), but the CrewAI part fails with
`BadRequestError 400`. CrewAI sends `tool_choice="auto"` and the vLLM **server** must be started with
`--enable-auto-tool-choice --tool-call-parser <parser>`. This is a vLLM Application setting, not a Session setting.

Fix (needs the repository version with the launcher change: `git pull --ff-only origin main` in the Session, then restart
the vLLM Application; the restart reloads the model and takes several minutes):

1. In the `bni-vllm-qwen35-9b` Application environment add one variable (parser name from the official vLLM recipe for
   Qwen3.5):

   ```text
   VLLM_TOOL_CALL_PARSER=qwen3_coder
   ```

2. **Update Application** and wait for `Application startup complete.` in the log. The startup configuration line must
   now show `--enable-auto-tool-choice` and `--tool-call-parser qwen3_coder`.
3. Run Lab 08 again:

   ```bash
   cd /home/cdsw/bni-cai-technical-training; env -u PYTHONPATH /home/cdsw/.venvs/bni-rag/bin/python scripts/08_multi_agent_workflow.py --mode cai 2>&1 | grep -E -B1 -A1 '"status": "FAIL"|LAB_STATUS'
   ```

If vLLM refuses to start because it does not know the parser, send the log lines (the parser name may differ in this vLLM
version, for example `hermes`). Stop all GPU Sessions before the restart: one GPU per node.

## A12. Labs 08 and 09: the agent makes `0 data tool call(s)`

Seen at BNI after A11 worked (the `400` is gone, vLLM accepts tool calling):

- Lab 08: `plain_workflow` passes, `crewai_tool_call` fails with `0 data tool call(s)` (`passed=4 failed=1`).
- Lab 09: Phoenix collector and traces work, `agent_called_tool` fails with `0 data tool call(s)` (`passed=8 failed=1`).

The CrewAI agent answers without calling the data tool. Step 1 separates the server from CrewAI; step 2 is a repository fix
for one suspected cause.

### A12.1 Does the vLLM server return a tool call? (no CrewAI involved)

One command, nothing secret in it. Read the `"message"` part of the answer:

```bash
curl -s "$VLLM_URL/v1/chat/completions" -H "Content-Type: application/json" -d '{"model":"qwen3.5-9b","messages":[{"role":"user","content":"Use the tool to get total outstanding by risk band."}],"tools":[{"type":"function","function":{"name":"query_portfolio","description":"Query approved synthetic portfolio metrics.","parameters":{"type":"object","properties":{"question":{"type":"string"}},"required":["question"]}}}],"tool_choice":"auto","max_tokens":200,"chat_template_kwargs":{"enable_thinking":false}}'
```

- `"tool_calls": [ ... "name": "query_portfolio" ... ]` is present: the server and the parser are fine. The cause is on the CrewAI
  side; continue with A12.2.
- `"tool_calls"` is empty and `"content"` holds text such as `<tool_call>` or `<function=...>`: the parser
  `qwen3_coder` does not match the model output. Change `VLLM_TOOL_CALL_PARSER` in the vLLM Application (for example to
  `hermes`), keep **Number of GPUs = 1**, Update Application and run A12.1 again.
- An error (400 or 500): send the text.

### A12.2 CrewAI did not switch Qwen thinking off

The CrewAI `LLM` did not send `enable_thinking=false` like the other clients, so Qwen3.5 may think instead of calling the tool.
The repository now sends it (`bni_training.labs.crewai_llm`, commit "fix: switch Qwen thinking off in the CrewAI LLM").
Pull it and run both labs again; no vLLM restart is needed:

```bash
cd /home/cdsw/bni-cai-technical-training && git pull --ff-only origin main && git log --oneline -1
```

```bash
LABS="08_multi_agent_workflow 09_phoenix_monitoring"
```

```bash
for s in $LABS; do echo "== $s"; env -u PYTHONPATH EMBEDDING_MODEL_PATH=/home/cdsw/models/bge-m3 /home/cdsw/.venvs/bni-rag/bin/python scripts/$s.py --mode cai 2>&1 | grep -E -B1 -A1 '"status": "FAIL"|LAB_STATUS'; done
```

If `0 data tool call(s)` remains and A12.1 showed a tool call, send the lab output around `crewai_tool_call` (the CrewAI
panels "Agent Started", "Tool Used" and "Final Answer").

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
