# Trainer: Application lifecycle (maximum 5 active)

| Phase | Active Applications | Count |
|---|---|---:|
| Day 1 | vLLM, Qdrant, Phoenix, Workshop Portal | 4 |
| Day 2 morning | vLLM, Qdrant, LiteLLM, Workshop Portal (Phoenix optional) | 4 or 5 |
| Agent Studio publication | vLLM, LiteLLM (Qdrant only if the workflow uses RAG) **after stopping Phoenix and the Portal**, plus the workflow's own Applications | 4-5 |

`config/workshop/application-lifecycle.yaml` is checked by the planner: no phase may exceed five, counting the
optional Applications and `reserved_agent_studio_slots` (default 2, **cai-validation-pending**: measure how many
Application resources a published workflow actually creates). Always stop before you start so the count never
exceeds the limit, even briefly. The Portal stays one process and one replica in every phase.
