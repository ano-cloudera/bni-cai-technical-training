# Troubleshooting

| Symptom | Check | Safe action |
|---|---|---|
| Python is not 3.10 | Notebook kernel and PBJ runtime | Recreate the session with the approved runtime |
| GPU is not visible | Resource profile and `nvidia-smi` | Stop and ask the platform owner to assign the H200 profile |
| vLLM fails at import/start | Lab 00 report and GPU lock | Do not guess versions; rebuild the tested profile |
| Model path fails | `MODEL_PATH`, NFS mount, config and safetensors files | Correct the mount or pre-stage the model |
| Impala authentication fails | Selected mode, DNS, TLS, Kerberos/LDAP credentials | Fix authentication or explicitly select CSV mode |
| Qdrant returns no glossary | Collection, index, and `GROUP_ID` | Re-index the assigned group partition |
| Phoenix has no trace | OTLP endpoint and instrumentation packages | Verify endpoint and run lab 09 |
| Application will not start | `CDSW_APP_PORT`, quota, start command, logs | Stop unused group apps and retry the correct wave |
| LiteLLM fallback activates | Primary health and timeout | Validate vLLM first; fallback is workshop-only |
| `pip check` passes but `import phoenix` fails | Profile was layered with another one | Recreate the environment and install only the `observability` lock |
| Phoenix Application environment contains CrewAI | Wrong profile was installed | The Phoenix server uses only `observability`; participant libraries belong to `participant` |
| `phoenix.otel.register()` raises `AttributeError: _headers` | `arize-phoenix-otel` 0.17.1 with OpenTelemetry >= 1.45 | Use the OTLP/HTTP tracer shown in lab 09 (the participant profile does not install `phoenix.otel`) |
| A lab prints `status=SKIPPED` | Read the reason in the check detail | Expected in `--mode local` for GPU, CAI, Impala, NFS; in `--mode cai` it is a bug to report |
| A lab prints `status=FAIL` in `--mode cai` | Missing variable or unreachable service | Fix the prerequisite; the lab never mocks or falls back |
| LiteLLM exits at start with a master-key message | `LITELLM_MASTER_KEY` is unset | Generate one at runtime and set it in the Application environment; never commit it |
| `litellm` command fails with a missing module | Wrong profile | Install the `gateway` profile (`litellm[proxy]`) in its own environment |

Never place credentials in error reports. Redact URLs if they contain query tokens.

