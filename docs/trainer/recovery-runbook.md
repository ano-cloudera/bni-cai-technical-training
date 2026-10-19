# Trainer: recovery

| Situation | What to do |
|---|---|
| Portal says another instance is running after a restart | Wait about 30 seconds for the old heartbeat to expire, or stop the old process. Confirm the Application has one replica. |
| Participants see *Busy* | The shared model queue is full. Wait, or raise `PORTAL_MAX_QUEUE_DEPTH` only if vLLM has headroom. |
| Answers are slow | Check vLLM and the queue length in the Portal sidebar; do not raise `PORTAL_MAX_CONCURRENT_INFERENCE` without testing vLLM. |
| A participant picked the wrong group | They use *Reset session* (confirmation required). Never edit another group's folder. |
| Dataset looks wrong | `python scripts/validate_dataset.py`; if it fails, restore `data/raw` and `data/manifests` from Git. |
| Portal refuses to start | Check that `LITELLM_BASE_URL` or `VLLM_BASE_URL` is set; cai mode never uses a mock and never falls back. |
| DATA_BACKEND=impala | Not enabled for the Portal. Impala is an optional trainer extension and is never needed. |
