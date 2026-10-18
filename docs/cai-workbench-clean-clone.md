# Clean Clone Workflow for CAI Workbench

Use this exact sequence in a new Workbench session. It makes no CAI API call and deploys nothing. Replace the
`<...>` placeholders with values from your platform owner; none of them is stored in the repository.

1. **Runtime.** Start a session with the approved PBJ Python 3.10 JupyterLab runtime. Use the *Standard* edition for
   participant work and the *NVIDIA GPU* edition only for the vLLM sandbox work (labs 00-03). The runtime identifier
   comes from your CAI runtime catalog and is never hard-coded here.
2. **Clone into an empty directory.**
   ```bash
   git clone <REPO_URL> bni-cai-technical-training
   cd bni-cai-technical-training
   git status --short            # must print nothing
   python --version              # must print Python 3.10.x
   ```
3. **Create the untracked environment file.** Pick the profile that matches the environment.
   ```bash
   cp config/profiles/sandbox-l40s.env.example .env      # or bni-h200.env.example
   chmod 600 .env
   # Edit .env: replace every <placeholder>. Never commit it; .env is ignored by Git.
   set -a; source .env; set +a
   ```
4. **Install exactly one dependency profile** (never several into one environment).
   ```bash
   python scripts/bootstrap.py participant               # participants and group Streamlit Application
   # trainer-only, in separate environments: rag, observability, gateway, gpu-l40s or gpu-h200
   ```
   Offline: build the wheelhouse in the same runtime family first (`docs/offline-installation.md`).
5. **Lab 00 in CAI mode.** It checks Python, GPU, CUDA, and that every required variable for `RUNTIME_PROFILE` is set.
   ```bash
   python scripts/00_environment_check.py --mode cai
   ```
   In the GPU sandbox, record the observed driver, CUDA runtime, torch, transformers, and vLLM versions, then
   freeze them into `requirements/gpu-l40s.lock`. Until then the GPU profiles stay **cai-validation-pending**.
6. **Repeat the local acceptance test on the clone.**
   ```bash
   python scripts/acceptance_test.py --mode local --report build/acceptance-local.md
   python scripts/secret_scan.py
   ```
7. **Dry-run the automation plan (trainer only).** This writes a local JSON file and calls no API.
   ```bash
   PYTHONPATH=src:. python -m automation.cai_api_v2.cli \
     --config config/env.sandbox-l40s.example.yaml plan --output build/cai-plan.json
   ```
   Compare the generated fields with the target `/api/v2/swagger.html` and set the runtime identifier from the
   catalog before any live write.
8. **Labs.** Run notebooks 00-12 in order with `LAB_MODE=cai`, or the matching scripts with `--mode cai`.
   A lab that cannot reach its service prints `status=FAIL`; it never mocks and never falls back silently.

Never paste credentials into notebooks, terminals that are logged, or commits. Stop only your own group Application.
