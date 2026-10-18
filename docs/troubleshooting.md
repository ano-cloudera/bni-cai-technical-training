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

Never place credentials in error reports. Redact URLs if they contain query tokens.

