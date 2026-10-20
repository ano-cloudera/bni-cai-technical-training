# BNI testing commands (copy and paste)

Working note for the BNI validation in `--mode cai`. Run from a **CPU Session** terminal (no GPU, so the vLLM Application
keeps its GPU). One block, one paste. This is not part of the documentation set; delete it when done.

Nothing here claims CAI readiness. Record every result in `PROJECT_STATE.md` and
`config/cai-validation-pending.yaml`.

Rules while testing:

- Never print, screenshot or paste a key. Use `read -rs` for `LITELLM_API_KEY`.
- Every command that talks to a shared service must be run with `env -u PYTHONPATH` so a venv is tested the way an
  Application sees it.
- One step at a time. Stop at the first failure and read its message before the next step.
- At most five Applications are active (vLLM, Qdrant, Phoenix, Portal, LiteLLM). Do not start a sixth.

## Confirmed at BNI so far

| Step | Result |
|---|---|
| Gate: five Applications answer 200, `qwen3.5-9b` served, LiteLLM aliases listed | Pass |
| Lab 03 (vLLM, plain and streaming chat) | Pass |
| Portal: answer without "Thinking Process", SQL shown | Pass |
| Portal: glossary search returns `group_03` notes | Pass |
| Lab 10 (LiteLLM) | Pass, after `SSL_CERT_FILE` on the LiteLLM Application |
| Lab 07 (Qdrant) | Pass, after `:443` and `SSL_CERT_FILE`; glossary indexed (5 documents) |
| Lab 06 (CrewAI tools) | Pass |
| Lab 08 (multi-agent) and Lab 09 (Phoenix) | Pass, after `VLLM_TOOL_CALL_PARSER=qwen3_coder` on vLLM (with 1 GPU) and the CrewAI thinking fix |
| Lab 11 (guardrails) | Pass |
| Lab 00 | Pass (`passed=11 skipped=3`), after the five profile variables of sections 0 and 0b |
| Labs 04, 05 and 12 | Pass (`passed=7 skipped=1`, `passed=11`, `passed=2`) |

Fixes for every problem found are in `BNI-FIX-COMMANDS.md`.

## 0. Variables (once per terminal)

The Application URLs are `https://<application-name>.<apps-domain>`. The BNI apps domain is kept out of this file on
purpose (the repository secret scan treats it as a private domain), so type it once. Ask the trainer for the value (it is
the part after the Application name in any Application URL), then paste one line at a time:

```bash
read -r APPS_DOMAIN; export APPS_DOMAIN
```

```bash
export VLLM_URL="https://bni-vllm-qwen35-9b.$APPS_DOMAIN"; export QDRANT_URL="https://bni-qdrant.$APPS_DOMAIN:443"; export PHOENIX_UI_URL="https://bni-phoenix.$APPS_DOMAIN"; export LITELLM_URL="https://bni-litellm-gateway.$APPS_DOMAIN"; export PORTAL_URL="https://bni-workshop-portal.$APPS_DOMAIN"; export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt; export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt; export RUNTIME_PROFILE=bni-h200; export WORKSHOP_RUNTIME_DIR=/home/cdsw/workshop-runtime; export DATA_MODE=csv; export VLLM_API_KEY=EMPTY; export PHOENIX_COLLECTOR_ENDPOINT="$PHOENIX_UI_URL/v1/traces"; export LITELLM_BASE_URL="$LITELLM_URL/v1"; export WORKSHOP_PORTAL_URL="$PORTAL_URL"
```

`QDRANT_URL` ends with `:443` because the Python Qdrant client otherwise uses port 6333. `SSL_CERT_FILE` makes Python trust
the internal BNI certificate (without it Lab 10 and the Qdrant client fail with `CERTIFICATE_VERIFY_FAILED`). Details:
`BNI-FIX-COMMANDS.md`, A6 and A7.

Check the five variables are set (each line must show a URL):

```bash
echo "$VLLM_URL"; echo "$QDRANT_URL"; echo "$PHOENIX_UI_URL"; echo "$LITELLM_URL"; echo "$PORTAL_URL"
```

The LiteLLM master key (type or paste it after the prompt appears; nothing is echoed):

```bash
read -rs LITELLM_API_KEY; export LITELLM_API_KEY
```

Check the key length without showing it (must be 67 for a key made with the guide's command):

```bash
echo "${#LITELLM_API_KEY}"
```

## 0b. After a new Session (all terminal variables are gone)

Files in `/home/cdsw` stay (repository, venvs, models, workspaces, lab output). Variables do not. Run these, one line at
a time, in the new terminal. Step 1 asks for the apps domain (see section 0), then step 2 sets the URLs and TLS trust:

```bash
read -r APPS_DOMAIN; export APPS_DOMAIN
```

```bash
export VLLM_URL="https://bni-vllm-qwen35-9b.$APPS_DOMAIN"; export QDRANT_URL="https://bni-qdrant.$APPS_DOMAIN:443"; export PHOENIX_UI_URL="https://bni-phoenix.$APPS_DOMAIN"; export LITELLM_URL="https://bni-litellm-gateway.$APPS_DOMAIN"; export PORTAL_URL="https://bni-workshop-portal.$APPS_DOMAIN"; export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt; export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt; export RUNTIME_PROFILE=bni-h200; export WORKSHOP_RUNTIME_DIR=/home/cdsw/workshop-runtime; export DATA_MODE=csv; export VLLM_API_KEY=EMPTY; export PHOENIX_COLLECTOR_ENDPOINT="$PHOENIX_UI_URL/v1/traces"; export LITELLM_BASE_URL="$LITELLM_URL/v1"; export WORKSHOP_PORTAL_URL="$PORTAL_URL"
```

```bash
read -rs LITELLM_API_KEY; export LITELLM_API_KEY
```

```bash
set -a; source /home/cdsw/workshop-runtime/groups/group_03/config/group.env; set +a; export LAB_MODE=cai; export PHOENIX_COLLECTOR_ENDPOINT="$PHOENIX_UI_URL/v1/traces"; export LITELLM_BASE_URL="$LITELLM_URL/v1"; echo "$GROUP_ID $MISSION_ID $LAB_MODE"
```

The last line must print `group_03 loan_portfolio_monitoring cai`. Then continue from section 1 (or the lab you were on).
Note: `QDRANT_URL` ends with `:443` because the Python Qdrant client otherwise uses port 6333 (see
`BNI-FIX-COMMANDS.md`, A7). Use `cd /home/cdsw/bni-cai-technical-training` before any lab command.

## 1. Code version

```bash
cd /home/cdsw/bni-cai-technical-training && git pull --ff-only origin main && git log --oneline -1
```

## 2. Gate: every Application answers (all must print 200)

```bash
curl -s -o /dev/null -w "vllm=%{http_code}\n" "$VLLM_URL/health"; curl -s -o /dev/null -w "qdrant=%{http_code}\n" "$QDRANT_URL/readyz"; curl -s -o /dev/null -w "phoenix=%{http_code}\n" "$PHOENIX_UI_URL/healthz"; curl -s -o /dev/null -w "portal=%{http_code}\n" "$PORTAL_URL/_stcore/health"; curl -s -o /dev/null -w "litellm=%{http_code}\n" "$LITELLM_URL/health/liveliness"
```

A `302`, `401` or `403` means CAI authentication is on. Stop and decide how Applications and Sessions authenticate before
any lab (section 6 of `docs/trainer/cai-application-deployment.md`).

The model is served under the expected name (must list `qwen3.5-9b`):

```bash
curl -s "$VLLM_URL/v1/models"
```

LiteLLM lists its aliases (must show `qwen-primary` and `training-fallback`):

```bash
curl -s -H "Authorization: Bearer $LITELLM_API_KEY" "$LITELLM_URL/v1/models"
```

Read the output only for the model names. Do not share a screenshot that shows the header line.

## 3. Prepare the group workspaces (once)

Dry run first; it lists what would be created and writes nothing:

```bash
cd /home/cdsw/bni-cai-technical-training && export WORKSHOP_RUNTIME_DIR=/home/cdsw/workshop-runtime && env -u PYTHONPATH /home/cdsw/.venvs/bni-rag/bin/python scripts/prepare_group_workspaces.py --lab-mode cai --vllm-base-url "$VLLM_URL"
```

Apply (safe to repeat; edited notebooks are never overwritten):

```bash
env -u PYTHONPATH /home/cdsw/.venvs/bni-rag/bin/python scripts/prepare_group_workspaces.py --lab-mode cai --vllm-base-url "$VLLM_URL" --apply
```

Validate:

```bash
env -u PYTHONPATH /home/cdsw/.venvs/bni-rag/bin/python scripts/validate_group_workspaces.py --mode group_driver
```

## 4. Load one group's environment (use `group_03` as the test group)

Each group has a `group.env` with no secrets. Load it, then add the service URLs for the labs. Run these in the same
terminal as the lab commands below.

```bash
cd /home/cdsw/workshop-runtime && ls
```

```bash
set -a; source /home/cdsw/workshop-runtime/groups/group_03/config/group.env; set +a; export LAB_MODE=cai; echo "$GROUP_ID $MISSION_ID $LAB_MODE"
```

If `source` says the file does not exist, use the path that `ls` showed (the workspace folder holds `config/group.env`).

Service variables the labs read (already exported in section 0):

```bash
export PHOENIX_COLLECTOR_ENDPOINT="$PHOENIX_UI_URL/v1/traces"; export LITELLM_BASE_URL="$LITELLM_URL/v1"
```

`PHOENIX_COLLECTOR_ENDPOINT` with `/v1/traces` is a guess that Lab 09 will confirm or reject.

## 5. Labs, in this order

Run each from the repository folder. A lab passes only when its last line is `LAB_STATUS: ... status=PASS`.

```bash
cd /home/cdsw/bni-cai-technical-training
```

### 5.0 All labs in one command (after sections 0b to 4 and the glossary indexing)

Runs Labs 00, 03 to 12 one after another and prints only the `LAB_STATUS` line of each plus any failing check. Nothing is
skipped silently: a failing lab shows its failing check. Run it from the repository folder, in a terminal with the
section 0b variables set. It takes a few minutes (the model answers real requests).

```bash
cd /home/cdsw/bni-cai-technical-training; for s in 00_environment_validation 03_llm_api_testing 04_csv_data_access 05_semantic_layer 06_crewai_tools 07_qdrant_rag 08_multi_agent_workflow 09_phoenix_monitoring 10_litellm_routing 11_guardrails 12_end_to_end_portal; do echo "== $s"; env -u PYTHONPATH EMBEDDING_MODEL_PATH=/home/cdsw/models/bge-m3 /home/cdsw/.venvs/bni-rag/bin/python scripts/$s.py --mode cai 2>&1 | grep -E -B1 -A1 '"status": "FAIL"|LAB_STATUS'; done
```

Send the whole output (it holds no keys). Then fix only the labs that show `status=FAIL`, one at a time, with the sections
below as the detail for each lab.

### 5.0b Run only some labs (to repeat the ones that failed)

Set the list once, then run the loop. Change the names in the first line to the labs you want. Run it from the repository
folder, with the section 0b variables set:

```bash
LABS="08_multi_agent_workflow 09_phoenix_monitoring"
```

```bash
for s in $LABS; do echo "== $s"; env -u PYTHONPATH EMBEDDING_MODEL_PATH=/home/cdsw/models/bge-m3 /home/cdsw/.venvs/bni-rag/bin/python scripts/$s.py --mode cai 2>&1 | grep -E -B1 -A1 '"status": "FAIL"|LAB_STATUS'; done
```

Labs still to run at BNI (Labs 00, 03, 06 to 11 passed). Click one sample question in the Portal first, so Lab 12 finds a
saved answer (done at BNI for `group_03`: the Portal answer and "My outputs (1)" were confirmed):

```bash
LABS="04_csv_data_access 05_semantic_layer 12_end_to_end_portal"
```

Lab names: `00_environment_validation`, `03_llm_api_testing`, `04_csv_data_access`, `05_semantic_layer`, `06_crewai_tools`,
`07_qdrant_rag`, `08_multi_agent_workflow`, `09_phoenix_monitoring`, `10_litellm_routing`, `11_guardrails`,
`12_end_to_end_portal`. Labs 08 and 09 need the vLLM Application to run with `VLLM_TOOL_CALL_PARSER=qwen3_coder` and one
GPU (`BNI-FIX-COMMANDS.md`, A11).

### 5.1 Lab 00 and Lab 03 (vLLM only)

Lab 00 needs the BNI runtime profile first:

```bash
export RUNTIME_PROFILE=bni-h200
```

```bash
env -u PYTHONPATH /home/cdsw/.venvs/bni-rag/bin/python scripts/00_environment_validation.py --mode cai
```

```bash
env -u PYTHONPATH /home/cdsw/.venvs/bni-rag/bin/python scripts/03_llm_api_testing.py --mode cai
```

Expect a normal answer without "Thinking Process", a streamed answer and a saved file under
`groups/group_03/output/`.

### 5.2 Portal

Open the Portal URL in the browser, choose `group_03`, click one sample question. Pass: the answer is short, has no
"Thinking Process", is not cut off, and shows the SQL. The sidebar says `Shared model: 0 of 3 running`.

Then test retrieval: open the panel "Related glossary and scenario notes (my group only)", type `outstanding balance` in
the Search box and press Enter. Pass: notes for `group_03` appear (for example Outstanding Balance, Loan Portfolio
Monitoring, DPD 30). This needs the glossary to be indexed (section 5.4), and `QDRANT_URL` (with `:443`),
`SSL_CERT_FILE` and `EMBEDDING_MODEL_PATH=/home/cdsw/models/bge-m3` in the Portal environment. Ask one sample question
before Lab 12, so a saved answer exists.

### 5.3 Lab 10 (LiteLLM)

```bash
env -u PYTHONPATH /home/cdsw/.venvs/bni-rag/bin/python scripts/10_litellm_routing.py --mode cai
```

Pass: the gateway answers for `qwen-primary`, and `training-fallback` answers too. The key is never printed. Needs
`SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt` in the `bni-litellm-gateway` Application environment (fix A6).

### 5.4 Lab 07 (Qdrant and bge-m3)

Run from the repository folder (`cd /home/cdsw/bni-cai-technical-training`). Index the glossary for the test group once. This is a dry run:

```bash
env -u PYTHONPATH EMBEDDING_MODEL_PATH=/home/cdsw/models/bge-m3 /home/cdsw/.venvs/bni-rag/bin/python scripts/index_glossary.py --group-id group_03
```

Then write it (the group's own `group_id` is stored on every point). A `ReadTimeout` on the first call is safe to repeat
(fix A8). Pass: `{"group_id": "group_03", "documents": 5, ...}`:

```bash
env -u PYTHONPATH EMBEDDING_MODEL_PATH=/home/cdsw/models/bge-m3 /home/cdsw/.venvs/bni-rag/bin/python scripts/index_glossary.py --group-id group_03 --execute
```

Run the lab:

```bash
env -u PYTHONPATH EMBEDDING_MODEL_PATH=/home/cdsw/models/bge-m3 /home/cdsw/.venvs/bni-rag/bin/python scripts/07_qdrant_rag.py --mode cai
```

Pass: every result belongs to `group_03`; no other group's note appears.

### 5.5 Lab 09 (Phoenix)

```bash
env -u PYTHONPATH /home/cdsw/.venvs/bni-rag/bin/python scripts/09_phoenix_monitoring.py --mode cai
```

Pass: the lab passes and a trace with `group_03` appears in the Phoenix UI. If it fails on the collector endpoint, try
`$PHOENIX_UI_URL/v1/traces` without a trailing slash, then report the exact error.

### 5.6 Labs 06, 08 and 11 (vLLM only)

```bash
env -u PYTHONPATH /home/cdsw/.venvs/bni-rag/bin/python scripts/06_crewai_tools.py --mode cai
```

```bash
env -u PYTHONPATH /home/cdsw/.venvs/bni-rag/bin/python scripts/08_multi_agent_workflow.py --mode cai
```

```bash
env -u PYTHONPATH /home/cdsw/.venvs/bni-rag/bin/python scripts/11_guardrails.py --mode cai
```

### 5.7 Lab 12 (Portal)

Ask one question in the Portal for `group_03` first, then:

```bash
env -u PYTHONPATH /home/cdsw/.venvs/bni-rag/bin/python scripts/12_end_to_end_portal.py --mode cai
```

Pass: the Portal is healthy and a saved answer exists for `group_03`.

## 5b. Prepare the retrieval index for all ten groups (trainer, once before the workshop)

Lab 07 in `cai` mode indexes only the group that runs it, and `index_glossary.py` indexes only the five glossary terms. The
Portal glossary panel needs the glossary **and** the mission note of every group. This script does both for all ten groups
(or for the groups you name). Every point carries its own `group_id` (the point id includes it), so groups never overwrite
each other, and repeating it is safe. Run it from the repository folder, with the section 0b variables set.

Variables needed (a new Session loses them; without `QDRANT_URL` the script stops with `QDRANT_URL is not set`). Two lines,
one at a time; the second must print a URL that ends with `:443`:

```bash
read -r APPS_DOMAIN; export APPS_DOMAIN
```

```bash
export QDRANT_URL="https://bni-qdrant.$APPS_DOMAIN:443"; export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt; export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt; echo "$QDRANT_URL"
```

Dry run first (writes nothing). Confirmed at BNI: it lists 6 documents for each of `group_01` to `group_10`:

```bash
cd /home/cdsw/bni-cai-technical-training; env -u PYTHONPATH /home/cdsw/.venvs/bni-rag/bin/python scripts/index_all_groups.py
```

Then write (about a minute; one JSON line per group, each with `"documents": 6`; a `ReadTimeout` is safe to repeat):

```bash
env -u PYTHONPATH EMBEDDING_MODEL_PATH=/home/cdsw/models/bge-m3 /home/cdsw/.venvs/bni-rag/bin/python scripts/index_all_groups.py --execute
```

Check the number of points per group (each must be 6; the group's own mission note is included):

```bash
env -u PYTHONPATH /home/cdsw/.venvs/bni-rag/bin/python -c "import os; from qdrant_client import QdrantClient as C, models as m; c=C(url=os.environ['QDRANT_URL'], timeout=60); print({g: c.count(collection_name='bni_training_knowledge', count_filter=m.Filter(must=[m.FieldCondition(key='group_id', match=m.MatchValue(value=g))])).count for g in ['group_%02d' % i for i in range(1, 11)]})"
```

A single group only: add `--group-id group_04` to the command.

## 5c. After indexing: check another group, rotate the key, smoke-test the load

Confirmed at BNI: all ten groups hold 6 points each in `bni_training_knowledge` (section 5b).

### 5c.1 Portal for another group

Open the Portal in a new tab, choose `group_05`, open the panel "Related glossary and scenario notes", type
`outstanding balance` and press Enter. Pass: notes appear, and the mission note is the mission of `group_05`, not of
`group_03`.

### 5c.2 Rotate the LiteLLM master key (after a key was partly visible in a screenshot)

Create the key into a file (nothing is printed; the length must be 67):

```bash
python3 -c "import secrets; print('sk-' + secrets.token_hex(32))" > /home/cdsw/LITELLM_MASTER_KEY.txt && chmod 600 /home/cdsw/LITELLM_MASTER_KEY.txt && echo "length: $(tr -d '\n' < /home/cdsw/LITELLM_MASTER_KEY.txt | wc -c)"
```

Open the file in JupyterLab, copy its content into `LITELLM_MASTER_KEY` of the `bni-litellm-gateway` Application (never screenshot
the value column) and click **Update Application**. Then use the new key in the Session:

```bash
export LITELLM_API_KEY="$(tr -d '\n' < /home/cdsw/LITELLM_MASTER_KEY.txt)"; echo "${#LITELLM_API_KEY}"
```

Test (must print `models=200`; the old key now gives 401):

```bash
curl -s -o /dev/null -w "models=%{http_code}\n" -H "Authorization: Bearer $LITELLM_API_KEY" "$LITELLM_URL/v1/models"
```

Delete the file and close its JupyterLab tab:

```bash
rm -f /home/cdsw/LITELLM_MASTER_KEY.txt
```

### 5c.3 vLLM concurrency smoke test

`scripts/vllm_concurrency_test.py` sends one small request (16 tokens) per group at the same time and prints the highest latency.
It is a smoke test, not a load test (its `requests_per_second` is not a real throughput, and it does not switch Qwen
thinking off). Run it from the repository folder with `VLLM_URL` set:

```bash
env -u PYTHONPATH /home/cdsw/.venvs/bni-rag/bin/python scripts/vllm_concurrency_test.py --url "$VLLM_URL/v1" --api-key EMPTY --groups 10
```

Confirmed at BNI: `{'requests': 10, 'max_latency_seconds': 0.857, ...}`, all ten small requests finished at the same time. Do not
read the `requests_per_second` value; it is not a throughput.

### 5c.4 vLLM load test with workshop-sized requests

`scripts/vllm_load_test.py` sends 40 requests at the same moment (four per group), each asking for about 200 tokens with Qwen
thinking switched off, and prints wall time, requests and output tokens per second, and p50 / p95 / max latency. Failures
are counted, not hidden. Run it from the repository folder with `VLLM_URL` set, and **no other lab or Portal user at the
same time**:

```bash
env -u PYTHONPATH /home/cdsw/.venvs/bni-rag/bin/python scripts/vllm_load_test.py --url "$VLLM_URL/v1" --concurrency 40 --max-tokens 200
```

Send the whole JSON. How to read it: `failed` must be 0; `latency_p95_seconds` is what the slowest participants wait (compare
it with the Portal timeouts: `PORTAL_REQUEST_TIMEOUT_S=60` and `PORTAL_QUEUE_TIMEOUT_S=120`). The Portal itself lets only 3
requests run at once, so this test is the worst case of direct vLLM use (notebooks), not of the Portal. Repeat once with
`--concurrency 10` to see how latency grows with load.

## 6. Whole-service check (read only)

```bash
env -u PYTHONPATH /home/cdsw/.venvs/bni-rag/bin/python scripts/check_shared_services.py --mode cai --phase day2_morning
```

`SKIPPED` means a service is not active in that phase. Use `--phase day1` for the first day.

## 7. What to send back

For each step: the line `LAB_STATUS: ...` or the last error line. Do not send a screenshot that shows a key, and do not
send the Application environment screen.

After the labs, write the vLLM H200 settings that actually ran (`MAX_MODEL_LEN`, `GPU_MEMORY_UTILIZATION`,
`MAX_NUM_SEQS`) into the status table of `docs/trainer/cai-application-deployment.md`. Capacity and speed tests
(`scripts/vllm_concurrency_test.py`) come **after** every lab passes, not before.
