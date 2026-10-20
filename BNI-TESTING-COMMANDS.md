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

## 0. Variables (once per terminal)

The Application URLs are `https://<application-name>.<apps-domain>`. The BNI apps domain is kept out of this file on
purpose (the repository secret scan treats it as a private domain), so type it once. Ask the trainer for the value (it is
the part after the Application name in any Application URL), then paste one line at a time:

```bash
read -r APPS_DOMAIN; export APPS_DOMAIN
```

```bash
export VLLM_URL="https://bni-vllm-qwen35-9b.$APPS_DOMAIN"; export QDRANT_URL="https://bni-qdrant.$APPS_DOMAIN"; export PHOENIX_UI_URL="https://bni-phoenix.$APPS_DOMAIN"; export LITELLM_URL="https://bni-litellm-gateway.$APPS_DOMAIN"; export PORTAL_URL="https://bni-workshop-portal.$APPS_DOMAIN"
```

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

### 5.1 Lab 00 and Lab 03 (vLLM only)

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

### 5.3 Lab 10 (LiteLLM)

```bash
env -u PYTHONPATH /home/cdsw/.venvs/bni-rag/bin/python scripts/10_litellm_routing.py --mode cai
```

Pass: the gateway answers for `qwen-primary`, and `training-fallback` answers too. The key is never printed.

### 5.4 Lab 07 (Qdrant and bge-m3)

Index the glossary for the test group once. This is a dry run:

```bash
env -u PYTHONPATH EMBEDDING_MODEL_PATH=/home/cdsw/models/bge-m3 /home/cdsw/.venvs/bni-rag/bin/python scripts/index_glossary.py --group-id group_03
```

Then write it (the group's own `group_id` is stored on every point):

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
