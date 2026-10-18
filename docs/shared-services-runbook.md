# Shared Services Runbook

Create one `bni-ai-training-shared` project. Deploy `bni-vllm-qwen35-9b`, `bni-qdrant`, `bni-phoenix`, and `bni-litellm` as separate Cloudera AI Applications. Each launcher binds to `CDSW_APP_PORT`. Configure secrets in the Application environment, never in files.

Start order: Qdrant, Phoenix, vLLM, then LiteLLM. Validate `/v1/models`, Qdrant `/readyz`, Phoenix `/healthz`, and LiteLLM `/health`. Stop LiteLLM first and vLLM last. Qdrant and Phoenix storage should use approved NFS directories.

Qdrant is configured through `QDRANT__...` environment variables as documented in the [Qdrant configuration reference](https://qdrant.tech/documentation/operations/configuration/). LiteLLM uses its documented `--config` and `--port` proxy options.

