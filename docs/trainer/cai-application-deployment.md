# Trainer: deploying the shared Applications in CAI (BNI)

Status: **cai-validation-pending.** The vLLM model was validated in a CAI Session. Deploying each service as a CAI
Application is being validated now. Nothing here claims CAI readiness. All URLs and paths below are placeholders or
examples; use your own values and never paste secrets into notes, screenshots or chat.

## 1. What you deploy

At most **five** Applications are active at any time (`config/workshop/application-lifecycle.yaml`).

| # | Application | Script | Runtime | CPU / memory / GPU |
|---|---|---|---|---|
| 1 | `bni-vllm-qwen35-9b` | `deployments/cai/vllm/app.py` | PBJ JupyterLab, Python 3.10, **NVIDIA GPU** | 16 vCPU / 64 GB / 1 GPU (H200) |
| 2 | `bni-qdrant` | `deployments/cai/qdrant/app.py` | PBJ JupyterLab, Python 3.10, Standard | 4 vCPU / 16 GB / 0 |
| 3 | `bni-phoenix` | `deployments/cai/phoenix/app.py` | PBJ JupyterLab, Python 3.10, Standard | 4 vCPU / 16 GB / 0 |
| 4 | `bni-workshop-portal` | `deployments/cai/workshop-portal/app.py` | PBJ JupyterLab, Python 3.10, Standard | 4 vCPU / 8 to 16 GB / 0, **one replica** |
| 5 | `bni-litellm` | `deployments/cai/litellm/app.py` | PBJ JupyterLab, Python 3.10, Standard | 2 vCPU / 4 GB / 0 |

Phases: day 1 runs vLLM, Qdrant, Phoenix and the Portal (four). LiteLLM joins on day 2 (Phoenix optional). Stop before
you start, so the count never passes five, even briefly. Participant notebooks run in **CPU Sessions**; CrewAI runs
there, not in an Application.

Rules that apply to every Application:

- Use a Python entrypoint (`app.py`), never a shell script.
- Do not set `CDSW_APP_PORT` yourself. CAI provides it. Do not hard-code a port.
- The Application starts in `/home/cdsw`, not in the repository. Use absolute paths for anything you set.
- CAI runs the Application script **cell by cell in a kernel**, not as `python app.py`. That is why its log shows the
  source code followed by `Cell In[n]` and `Engine exited with status 1`, and why `__file__` is not defined. The real
  error is the last lines of the log.
- Code changes reach an Application only after you `git pull` in a Session **and restart** the Application.
- An Application has no terminal. Prepare files and environments from a **Session**; they live in `/home/cdsw`,
  which the Session and the Application share.
- Keep keys out of the environment screen where possible; use CAI secrets for them.

### Where each Application stands (last observed in the sandbox, not at BNI)

| Application | Last observed | Notes |
|---|---|---|
| vLLM | **Running** (sandbox, A10G 24 GB, reduced settings) | After `VLLM_HOST=127.0.0.1` and a smaller cache budget. The final values were not recorded here; write them down. Not yet reached from another Application or Session |
| Qdrant | **Running** | After the binary was prepared (step 2.4) |
| Phoenix | `/healthz` OK; UI error fixed | The UI failed with Starlette 1.x. Fix the venv (see the errors table), restart, and confirm the UI page |
| Workshop Portal | Launcher bugs fixed, not yet confirmed Running | `File does not exist`, then `__file__` is not defined |
| LiteLLM | **Running** with a master key | The API works; the Admin UI login needs a database and is not available (see 3.5) |

Update this table as you confirm each one. Nothing here is validated at BNI yet. A successful sandbox run proves the
Application logic (launcher, port, paths, environment); it does not prove H200 capacity or performance.

### Resource groups in the sandbox

| Group | Instance | Used for |
|---|---|---|
| `ano-group` (CPU) | `r6a.24xlarge`, 96 vCPU, 768 GiB, autoscale 0 to 5 | Qdrant, Phoenix, Portal, LiteLLM and CPU Sessions. It has **no GPU**, so vLLM cannot run there |
| `ano-gpu-group` (GPU) | `g5.16xlarge`, 1 x A10G 24 GB, 64 vCPU, 256 GiB, autoscale 0 to 2 | vLLM only. Nodes are created on demand, so the first start is slow |

Choose the GPU resource group in the vLLM Application and turn **Enable GPU** on. BNI uses its own H200 group.

## 2. Prepare once, from a CPU Session

First check what is already in place with the read-only script (it installs and changes nothing; run it from a Session on
the GPU resource group and stop that Session afterwards): `bash scripts/preflight_gpu_env.sh`. Lines marked `CHECK` need
attention. Override the defaults with `VENV`, `MODEL_PATH`, `EXPECT_GPU` (for example `EXPECT_GPU=A10G`) when needed.

Open a PBJ JupyterLab Python 3.10 Session and a terminal.

### 2.1 Code

```bash
cd /home/cdsw/bni-cai-technical-training
git pull --ff-only origin main          # or replace the folder from the zip (see the update notes)
git log --oneline -1
```

After every pull, **restart** the Applications whose launcher or code changed. A running Application keeps the old
code until it is restarted.

### 2.2 One virtual environment per Application type

Install each profile into its own environment, never into the base runtime and never several profiles together.
Use the retry flags because the proxy can be unstable.

```bash
cd /home/cdsw/bni-cai-technical-training
export PIP_USER=false
PIPFLAGS="--no-user --retries 10 --timeout 60"

# Portal (also used for CPU notebooks that need Qdrant)
python -m venv /home/cdsw/.venvs/bni-rag && source /home/cdsw/.venvs/bni-rag/bin/activate
python -m pip install $PIPFLAGS --upgrade pip
python -m pip install $PIPFLAGS -r requirements/rag.lock
python -m pip install --no-user --no-deps -e . && python -m pip check
deactivate

# Phoenix (server only). The current lock pins Starlette 0.52.1; an older venv with Starlette 1.x must be fixed
# with: python -m pip install --no-user "starlette==0.52.1"
python -m venv /home/cdsw/.venvs/bni-phoenix && source /home/cdsw/.venvs/bni-phoenix/bin/activate
python -m pip install $PIPFLAGS --upgrade pip
python -m pip install $PIPFLAGS -r requirements/observability.lock
python -m pip install --no-user --no-deps -e . && python -m pip check
deactivate

# LiteLLM gateway
python -m venv /home/cdsw/.venvs/bni-litellm && source /home/cdsw/.venvs/bni-litellm/bin/activate
python -m pip install $PIPFLAGS --upgrade pip
python -m pip install $PIPFLAGS -r requirements/gateway.lock
python -m pip install --no-user --no-deps -e . && python -m pip check
deactivate
```

The `rag` lock is large and pulls CUDA wheels even though the Portal uses no GPU. Check disk quota first.

For vLLM use the **`.in`** file, not the `.lock`. The GPU lock is an intent-only stub (it holds only `vllm==0.29.0`):

```bash
python -m venv /home/cdsw/.venvs/bni-vllm-h200 && source /home/cdsw/.venvs/bni-vllm-h200/bin/activate
python -m pip install --no-user --retries 10 --timeout 60 --upgrade pip
python -m pip install --no-user --retries 10 --timeout 60 -r requirements/gpu-h200.in
python -m pip install --no-user --no-deps -e . && python -m pip check
python -c "import torch, vllm; print(torch.__version__, torch.version.cuda, vllm.__version__, torch.cuda.is_available())"
deactivate
```

Stop on any `pip check` problem. Save `pip freeze` for the record.

### 2.3 Folders

```bash
mkdir -p /home/cdsw/bni-qdrant-storage /home/cdsw/bni-phoenix-data /home/cdsw/tools/qdrant
```

Both storage folders must be writable and must survive a restart (`/home/cdsw` does).

### 2.4 Qdrant binary (once)

The Application never downloads the binary. Prepare the pinned, checksum-verified release from the Session:

```bash
bash scripts/prepare_qdrant_binary.sh            # default: /home/cdsw/tools/qdrant/qdrant
/home/cdsw/tools/qdrant/qdrant --version
```

The pinned asset (v1.19.2, Linux musl) is in `requirements/qdrant-binary-manifest.json`. For a BNI mirror set
`QDRANT_BINARY_URL` and `QDRANT_BINARY_SHA256` together. Check the pinned checksum against the release page or your
mirror before relying on it. Safe to run again; `QDRANT_FORCE=1` replaces an existing binary.

### 2.5 Model

The Qwen3.5-9B model is already on NFS (example `/home/cdsw/models/Qwen3.5-9B`). The Application never downloads it.
Validate it from a Session with lab 01 if you have not yet.

## 3. Create the Applications

Create in this order and confirm each one before the next. In every Application, **Enable GPU is off except vLLM**.
Paths below are the real BNI paths (the repository is `/home/cdsw/bni-cai-technical-training`). Only values written as
`<...>` (Application URLs, the embedding model path, keys) are yours to fill in.

### 3.1 vLLM

| Field | Value |
|---|---|
| Name | `bni-vllm-qwen35-9b` |
| Script | `bni-cai-technical-training/deployments/cai/vllm/app.py` |
| Runtime | PBJ JupyterLab Python 3.10 **NVIDIA GPU** |
| Resources | 16 vCPU, 64 GB, 1 GPU |

Set every value explicitly, so the effective configuration is visible and does not depend on a profile default.
The values below are for **BNI (H200)**. The table after the block lists what changes in the **sandbox (L40S)**.

```text
PYTHONPATH=/home/cdsw/bni-cai-technical-training/src:/home/cdsw/bni-cai-technical-training
PYTHON_EXECUTABLE=/home/cdsw/.venvs/bni-vllm-h200/bin/python
MODEL_PATH=/home/cdsw/models/Qwen3.5-9B
GPU_PROFILE=h200
VLLM_MODEL=qwen3.5-9b
SERVED_MODEL_NAME=qwen3.5-9b
CUDA_VISIBLE_DEVICES=0
HF_HUB_OFFLINE=1
VLLM_DTYPE=bfloat16
MAX_MODEL_LEN=8192
GPU_MEMORY_UTILIZATION=0.75
MAX_NUM_SEQS=32
TENSOR_PARALLEL_SIZE=1
VLLM_USE_FLASHINFER_SAMPLER=0
VLLM_DISABLE_THINKING=true
VLLM_TOOL_CALL_PARSER=qwen3_coder
APP_STARTUP_TIMEOUT_MINUTES=15
```

| Variable | BNI H200 | Sandbox L40S 48 GB | Sandbox A10G 24 GB (first try) |
|---|---|---|---|
| `GPU_PROFILE` | `h200` | `l40s` | `l40s` (only the profile name; the values below override it) |
| `PYTHON_EXECUTABLE` venv | `bni-vllm-h200` | `bni-vllm-l40s` (from `requirements/gpu-l40s.in`) | `bni-vllm-l40s` |
| `MAX_MODEL_LEN` | `8192` | `8192` | `4096` |
| `GPU_MEMORY_UTILIZATION` | `0.75` | `0.82` (validated in a Session) | `0.92` |
| `MAX_NUM_SEQS` | `32` | `16` | `4` |
| `APP_STARTUP_TIMEOUT_MINUTES` | `15` | `15` | `30` (the GPU node is created on demand) |
| Application name | `bni-vllm-qwen35-9b` | `bni-vllm-qwen35-l40s` | `bni-vllm-qwen35-l40s` |

The weights alone take 17.66 GiB. An A10G has about 22.5 GiB usable, so `0.80` with 4096 and 2 sequences failed with
`Available KV cache memory: -1.88 GiB`. If a small GPU still fails, lower `MAX_MODEL_LEN` to 2048 and `MAX_NUM_SEQS` to 1.
A run on this GPU proves the Application, not capacity: do not measure speed or parallel load from it.

Before you start the Application on a GPU group, check it from a Session on that group and **stop the Session
afterwards** (one GPU per node, so a running Session blocks the Application):

```bash
nvidia-smi
/home/cdsw/.venvs/bni-vllm-l40s/bin/python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0), torch.cuda.get_device_capability(0))"
```

`bfloat16` needs compute capability 8.0 or higher (A10G is 8.6). Note the driver version; torch `cu130` needs a driver that
supports CUDA 13.

- Do not set `CDSW_APP_PORT`; CAI provides it.
- The launcher binds `127.0.0.1` by default (`VLLM_HOST` overrides it). `0.0.0.0` failed with `Address already in use`.
- vLLM logs `Unknown vLLM environment variable` for `VLLM_MODEL`, `VLLM_DTYPE`, `VLLM_HOST` and
  `VLLM_DISABLE_THINKING`. It scans every `VLLM_*` variable; the warning is harmless.
- `app.py` is started first by the Application's own Python runtime, and only then calls the venv Python. So
  `PYTHONPATH` must let that first process import `bni_training` and `deployments`.
- `VLLM_DISABLE_THINKING` is read by the notebooks and clients (`model_request_extras`), **not** by the server. It is
  harmless here; the real switch is `chat_template_kwargs.enable_thinking=false` in each request.
- `VLLM_TOOL_CALL_PARSER=qwen3_coder` adds `--enable-auto-tool-choice --tool-call-parser qwen3_coder` to the server. Lab 08
  (CrewAI) sends `tool_choice="auto"`, and without these options vLLM answers `400 "auto" tool choice requires
  --enable-auto-tool-choice and --tool-call-parser to be set`. `qwen3_coder` is the parser the official vLLM recipe for
  Qwen3.5 names; confirm it with Lab 08 after the restart. Restarting vLLM reloads the model.
- `VLLM_CHAT_TEMPLATE=/home/cdsw/bni-cai-technical-training/config/vllm/qwen3_5_chat_template.jinja` is needed only when **Agent Studio**
  (or any CrewAI-style client) calls the model. The original Qwen3.5 template answers HTTP 400 `System message must be at the
  beginning.` when a system message is not the first message, and Agent Studio sends one. The repository template changes only that
  rule. It was checked with the Jinja renderer in tests, **not yet on a running vLLM**. Changing it restarts vLLM (several minutes);
  after Update Application check that **Number of GPUs is still 1**. The notebooks and the Portal do not need it.
- `PIP_USER=false` only matters when you run `pip`; it is not needed in the Application.
- The names `VLLM_MAX_MODEL_LEN` and `VLLM_GPU_MEMORY_UTILIZATION` are **ignored**; use `MAX_MODEL_LEN` and
  `GPU_MEMORY_UTILIZATION`. Without them the profile supplies the defaults (`h200`: 8192, 0.75, 32; `l40s`: 8192,
  0.82, 16).
- `VLLM_USE_FLASHINFER_SAMPLER=0` is also set automatically when `nvcc` is missing (the PBJ runtime has none).
- The start-up log must show `vLLM Application startup configuration:` with `--served-model-name qwen3.5-9b`,
  `--max-model-len 8192`, your `--gpu-memory-utilization` and `--max-num-seqs`, and `"port_source": "CDSW_APP_PORT"`.
  Wait for `Application startup complete.` If the Application is marked failed, read the log before reinstalling.
- If the Application has CAI authentication enabled, a plain `curl` returns 401 or 403. Do not switch security off;
  pass the right credential (not yet validated, see section 6).
- Validate: `curl -i https://<vllm-app-url>/health`, then `/v1/models`, then one chat request that includes
  `"chat_template_kwargs": {"enable_thinking": false}`.
- Status: validated in a Session, not yet as an Application.

### 3.2 Qdrant

| Field | Value |
|---|---|
| Name | `bni-qdrant` |
| Script | `bni-cai-technical-training/deployments/cai/qdrant/app.py` |
| Resources | 4 vCPU, 16 GB, no GPU |

```text
PYTHONPATH=/home/cdsw/bni-cai-technical-training/src:/home/cdsw/bni-cai-technical-training
QDRANT_BINARY=/home/cdsw/tools/qdrant/qdrant
QDRANT_STORAGE_PATH=/home/cdsw/bni-qdrant-storage
APP_STARTUP_TIMEOUT_MINUTES=5
```

- Validate: `curl -i https://<qdrant-app-url>/readyz`.
- Then create a collection, restart the Application, and confirm the collection is still there (persistence).
- If it fails with "Qdrant binary not found", run step 2.4 from a Session.

### 3.3 Phoenix

| Field | Value |
|---|---|
| Name | `bni-phoenix` |
| Script | `bni-cai-technical-training/deployments/cai/phoenix/app.py` |
| Resources | 4 vCPU, 16 GB, no GPU |

```text
PYTHONPATH=/home/cdsw/bni-cai-technical-training/src:/home/cdsw/bni-cai-technical-training
PYTHON_EXECUTABLE=/home/cdsw/.venvs/bni-phoenix/bin/python
PHOENIX_WORKING_DIR=/home/cdsw/bni-phoenix-data
APP_STARTUP_TIMEOUT_MINUTES=5
```

- The launcher sets `PHOENIX_HOST` and `PHOENIX_PORT` itself (the `phoenix serve` command has no `--host` or
  `--port`). Phoenix also opens a gRPC port (default 4317); set `PHOENIX_GRPC_PORT` only if a log reports a clash.
- Validate: `curl -i https://<phoenix-app-url>/healthz`, then open the UI.
- Observability is only PASS once a trace from a notebook appears here (lab 09).

### 3.4 Workshop Portal

| Field | Value |
|---|---|
| Name | `bni-workshop-portal` |
| Script | `bni-cai-technical-training/deployments/cai/workshop-portal/app.py` |
| Resources | 4 vCPU, 8 to 16 GB, no GPU |
| Replicas | **1** (never scale out) |

```text
PYTHONPATH=/home/cdsw/bni-cai-technical-training/src:/home/cdsw/bni-cai-technical-training
PYTHON_EXECUTABLE=/home/cdsw/.venvs/bni-rag/bin/python
WORKSHOP_RUNTIME_DIR=/home/cdsw/workshop-runtime
PORTAL_APP=apps/workshop-portal/app.py
PORTAL_MODE=cai
PORTAL_LLM_ROUTE=vllm
VLLM_BASE_URL=https://<vllm-app-url>/v1
SERVED_MODEL_NAME=qwen3.5-9b
QDRANT_URL=https://<qdrant-app-url>
EMBEDDING_MODEL_PATH=<path to the sentence-transformers model on NFS>
PHOENIX_COLLECTOR_ENDPOINT=<phoenix collector endpoint>
DATA_BACKEND=csv
PORTAL_MAX_CONCURRENT_INFERENCE=3
PORTAL_MAX_QUEUE_DEPTH=60
PORTAL_QUEUE_TIMEOUT_S=120
PORTAL_REQUEST_TIMEOUT_S=60
PORTAL_MAX_RETRIES=2
PORTAL_ENFORCE_SINGLE_INSTANCE=true
PORTAL_MAX_TOKENS=512
```

- `PORTAL_DISABLE_THINKING` defaults to `true` (Qwen3.5 thinking off); set it to `false` only for another model.
- `PORTAL_APP` is set explicitly here; the launcher resolves this relative path from the repository.
- Add the API key variables (`VLLM_API_KEY`, `QDRANT_API_KEY`) as CAI secrets only if those services need them.
- Without both `QDRANT_URL` and `EMBEDDING_MODEL_PATH` the Portal has no retrieval.
- Validate: `curl -i https://<portal-app-url>/_stcore/health`, then open the UI and ask a sample question.
- One process and one replica, because the inference limit (default 3) is a process-local semaphore.

### 3.5 LiteLLM (day 2)

| Field | Value |
|---|---|
| Name | `bni-litellm` (the name is free; `bni-litellm-gateway` also works) |
| Script | `bni-cai-technical-training/deployments/cai/litellm/app.py` |
| Resources | 2 vCPU, 4 GB, no GPU (4 vCPU / 8 GiB is also fine for a first test) |

```text
PYTHONPATH=/home/cdsw/bni-cai-technical-training/src:/home/cdsw/bni-cai-technical-training
LITELLM_EXECUTABLE=/home/cdsw/.venvs/bni-litellm/bin/litellm
LITELLM_CONFIG=/home/cdsw/bni-cai-technical-training/config/litellm.yaml
LITELLM_MASTER_KEY=<a strong key you create; see below>
VLLM_BASE_URL=https://<vllm-app-url>/v1
VLLM_API_KEY=<value from a CAI secret, or a placeholder if vLLM has no key>
MOCK_FALLBACK_BASE_URL=<fallback endpoint; see the note>
APP_STARTUP_TIMEOUT_MINUTES=5
```

- **`LITELLM_MASTER_KEY` is required.** LiteLLM refuses to start without it (`UnsafeMasterKeyError`), because every
  request would otherwise be accepted. Create one in a Session and paste it into the Application environment; do not
  commit it, screenshot it or share it in chat:
  `python -c "import secrets; print('sk-' + secrets.token_hex(32))"`. Do not use
  `LITELLM_DANGEROUSLY_PERMIT_WEAK_OR_UNSET_MASTER_KEY`; it is for local development only.
- The master key is an admin key. Clients (the Portal as `LITELLM_API_KEY`, notebooks) must send it as a Bearer token
  or use a virtual key. How participants get a key is not decided yet. If the key ever appears in a screenshot or in
  chat, treat it as leaked: create a new one, replace it in the Application and restart.
- **The Admin UI cannot be used yet.** Opening the Application URL shows a LiteLLM login page, and signing in with
  `admin` and the master key fails with `Authentication Error, Not connected to DB!`. The login writes to a database
  (the proxy source calls `user_update` and `generate_key_helper_fn`), and we run LiteLLM without one. This is not a wrong
  key. The API does not need a database: check it from a Session without showing the key:
  `read -rs LITELLM_API_KEY; export LITELLM_API_KEY` and then
  `curl -s -H "Authorization: Bearer $LITELLM_API_KEY" https://<litellm-app-url>/v1/models`.
- SQLite does not work: LiteLLM's schema is fixed to Postgres. Virtual keys per group, budgets and the Admin UI all need
  Postgres. A laptop test showed that an embedded Postgres (the `pgserver` and `prisma` packages) is enough for the
  UI and for creating virtual keys (login returned 303, a key was created). It is **not implemented**: it needs two
  more packages in the gateway profile, `prisma generate`, a Prisma toolchain download from the internet (about 75 s,
  may be blocked at BNI), a launcher that runs two processes, and the data would be lost on restart. The alternative
  is a Postgres provided by BNI (`DATABASE_URL`). This is postponed.
- `DISABLE_ADMIN_UI=True` should hide the login page; it is not verified in this version.
- The warning `trusted_proxy_ranges is not set` is harmless for now.
- `LITELLM_CONFIG` should be an absolute path. A relative `config/litellm.yaml` also works with the current launcher,
  which resolves it from the repository; with an older launcher it fails with `Config file not found`.
- `config/litellm.yaml` reads `VLLM_BASE_URL`, `VLLM_API_KEY` and `MOCK_FALLBACK_BASE_URL`. Define all three; the
  launcher prints a `WARNING` for any that is missing. The fallback model `training-fallback` points to
  `MOCK_FALLBACK_BASE_URL` and asks it for the model `qwen3.5-9b`, so that URL must serve that name: the vLLM URL
  does. `apps/litellm/mock_fallback.py` is a stand-in server that answers to any name; hosting it in CAI would be a
  sixth Application, so it is not planned.
- Values that work in the sandbox: `VLLM_API_KEY=EMPTY` if vLLM has no key, and the same `https://<vllm-app-url>/v1` for
  `MOCK_FALLBACK_BASE_URL`. Then `training-fallback` is a second alias of the same model, not a failover to another
  server. In the sandbox `qwen-primary` returned 200 through LiteLLM to vLLM.
- Replace `<vllm-app-url>` with the real Application URL. A literal placeholder such as `<actual-vllm-app-url>` makes
  every request fail.
- Validate: `curl -i https://<litellm-app-url>/health/liveliness`, then `/v1/models`, then a chat request with the
  alias `qwen-primary`.
- When it works, switch the Portal to `PORTAL_LLM_ROUTE=litellm`, `LITELLM_BASE_URL=https://<litellm-app-url>/v1`,
  `PORTAL_LITELLM_MODEL=qwen-primary`.
- Status: Running in the sandbox with a master key; the model route to vLLM is not yet tested end to end.

### 3.6 Wiring the Application URLs together

Copy each Application URL from its card in CAI (no trailing slash). **Before wiring anything, check that the vLLM URL
answers from outside the Application**, from a Session terminal:

```bash
export VLLM_URL="https://<vllm-app-url>"
curl -s -o /dev/null -w "health=%{http_code}\n" "$VLLM_URL/health"
curl -s "$VLLM_URL/v1/models"
```

`health=200` and a `qwen3.5-9b` entry mean the URL can be used. `302`, `401` or `403` mean CAI authentication is on and
other Applications will be refused too; stop and decide how to authenticate first (see section 6).

| Put the URL here | Variable | Value |
|---|---|---|
| LiteLLM | `VLLM_BASE_URL` | `https://<vllm-app-url>/v1` |
| LiteLLM | `MOCK_FALLBACK_BASE_URL` | any valid https URL for now, for example the same `/v1` URL |
| Portal (direct route) | `VLLM_BASE_URL` | `https://<vllm-app-url>/v1` |
| Portal | `QDRANT_URL` | `https://<qdrant-app-url>` |
| Portal | `PHOENIX_COLLECTOR_ENDPOINT` | `https://<phoenix-app-url>/v1/traces` (a guess, not yet tested) |
| Portal (through LiteLLM) | `LITELLM_BASE_URL`, `LITELLM_API_KEY`, `PORTAL_LITELLM_MODEL` | `https://<litellm-app-url>/v1`, the key, `qwen-primary` |
| Notebook workspaces | `prepare_group_workspaces.py --lab-mode cai --vllm-base-url` | `https://<vllm-app-url>` (`/v1` is added) |

Rules: `VLLM_BASE_URL` and `LITELLM_BASE_URL` end with `/v1`; `QDRANT_URL` has no path; never paste a placeholder such as
`<actual-vllm-app-url>`. After changing a variable, restart that Application. Wire one Application at a time and test
after each.

Keep prompts small: the context limit (`MAX_MODEL_LEN`) of the sandbox vLLM may be only 2048 or 4096 tokens.

## 4. Check and start order

| Step | Do | Pass when |
|---|---|---|
| 1 | Create vLLM, wait for startup | `/health` is 200 and `/v1/models` lists `qwen3.5-9b` |
| 2 | Run lab 03 against it | `LAB_STATUS` passes in `cai` mode |
| 3 | Create Qdrant | `/readyz` is 200; a collection survives a restart |
| 4 | Create Phoenix | `/healthz` is 200 |
| 5 | Run labs 07 and 09 | retrieval returns your group; a trace shows in Phoenix |
| 6 | Create the Portal | `/_stcore/health` is 200; a sample question completes |
| 7 | Run lab 12 | a saved answer exists for your group |
| 8 | Day 2: stop Phoenix if needed, create LiteLLM | `/health/liveliness` is 200; lab 10 passes |

Test one service at a time. A failure then has one obvious cause.

## 5. Errors we have seen, and the fix

| Log message | Cause | Fix |
|---|---|---|
| `No such file or directory: '/home/cdsw/tools/qdrant/qdrant'` | The binary was never prepared | Step 2.4, then restart |
| `unrecognized arguments: --host ... --port ...` (Phoenix) | `phoenix serve` has no such options | Use the current launcher (`git pull`), restart |
| `OSError: [Errno 98] Address already in use` (vLLM) | Binding `0.0.0.0` on the Application port clashed with a loopback listener | The launcher now binds `127.0.0.1` (older launcher: set `VLLM_HOST=127.0.0.1`) |
| `Available KV cache memory: -N GiB` / `No available memory for the cache blocks` (vLLM) | The weights plus overhead leave no room for the cache on a small GPU | Raise `GPU_MEMORY_UTILIZATION`, lower `MAX_MODEL_LEN` and `MAX_NUM_SEQS`, or use a bigger GPU |
| Phoenix UI shows `Internal Server Error` while `/healthz` is `OK` | Starlette 1.x is incompatible with arize-phoenix 12.x (`TemplateResponse() missing ... 'name'`) | Reinstall the `bni-phoenix` venv from the updated `requirements/observability.lock` (Starlette 0.52.1), or run `pip install "starlette==0.52.1"` in it, then restart |
| `File does not exist: apps/workshop-portal/app.py` | The Application starts in `/home/cdsw` | Use the current launcher (`git pull`), restart |
| `StopIteration` in the first cell of a notebook run from `/home/cdsw/workshop-runtime/...` | The notebook looked for `pyproject.toml` above its folder, but the workspace is outside the repository | `git pull`, then run `prepare_group_workspaces.py ... --apply` again: `config/group.env` now records `BNI_REPO_ROOT`. Meanwhile: `export BNI_REPO_ROOT=/home/cdsw/bni-cai-technical-training` |
| `NameError: name '__file__' is not defined` (Portal) | CAI runs the script in a kernel without `__file__` | Use the current launcher (`git pull`), restart |
| FlashInfer or `nvcc` error at vLLM start | No CUDA Toolkit in the runtime | `VLLM_USE_FLASHINFER_SAMPLER=0` |
| `Config file not found: config/litellm.yaml` (LiteLLM) | The Application starts in `/home/cdsw` | Set `LITELLM_CONFIG` to the absolute path, or use the current launcher (`git pull`) |
| `UnsafeMasterKeyError: ... no master key is set` (LiteLLM) | `LITELLM_MASTER_KEY` is missing | Create a key and set it (see section 3.5); the launcher now says so before starting |
| `Authentication Error, Not connected to DB!` on the LiteLLM login page | The Admin UI login needs a database | Not a wrong key. Use the API with the Bearer key; a database is postponed (see 3.5) |
| `The model 'training-fallback' does not exist` (LiteLLM, 404) | The fallback alias asked its endpoint for a model name it does not serve | Use the current `config/litellm.yaml` (`git pull`, restart LiteLLM); `MOCK_FALLBACK_BASE_URL` must serve `qwen3.5-9b` |
| `WARNING: litellm.yaml reads variables that are not set` | The config uses `os.environ/NAME` | Define `VLLM_BASE_URL`, `VLLM_API_KEY` and `MOCK_FALLBACK_BASE_URL` |
| Port 8100 unavailable | A Session may not use it | Applications use `CDSW_APP_PORT`; Sessions can use 8101 |
| Thinking text in answers, short or empty answers | Qwen3.5 thinking uses the token budget | Send `chat_template_kwargs.enable_thinking=false` |
| `pip` retries and `Connection broken` | Unstable proxy | Keep the retry flags; pip resumes the download |

If an Application fails, copy the last 30 lines of its Logs (no secrets) before changing anything.

## 6. Known gaps (do not treat as validated)

- **Access between Applications and from other Sessions.** CAI Application URLs may require authentication. How
  notebooks and the Portal reach vLLM, Qdrant, Phoenix and LiteLLM is not yet validated.
- **Portal and Qwen thinking.** Seen in the sandbox: the first Portal answer started with `Thinking Process` and was
  cut off. The Portal now sends `enable_thinking=false` (`PORTAL_DISABLE_THINKING`, default `true`, also through the
  LiteLLM alias) and `config/litellm.yaml` injects it for every alias (verified with a real LiteLLM against a recording
  stand-in server). Confirm in the Portal after `git pull` and a restart of the Portal and LiteLLM.
- **Embedding model.** The sentence-transformers model for Qdrant retrieval is not yet prepared on NFS.
- **LiteLLM keys and Admin UI.** How the Portal and participants authenticate to LiteLLM (master key versus virtual
  keys) is not decided; the master key must not be handed to participants. Virtual keys per group and the Admin UI
  need a Postgres database, which we do not have (postponed; see 3.5).
- **Small-GPU limits.** The sandbox A10G runs vLLM with a short context and few sequences. It proves the Application
  only; H200 behaviour, speed and capacity at BNI are not validated.
- **LiteLLM fallback.** The mock fallback endpoint has no CAI deployment plan yet.
- **GPU locks.** `requirements/gpu-*.lock` are stubs; resolve them on the target runtime.
- **Capacity.** The 40-participant Portal capacity, the single replica setting and Session quota are unmeasured.
- **Isolation is operational.** Group IDs separate data by application logic; they are not a security boundary.

Record every result in `PROJECT_STATE.md` and `config/cai-validation-pending.yaml`.
