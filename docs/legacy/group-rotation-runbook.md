# Group Application Rotation

> **Legacy multi-project guide.** This page describes the rc1 `multi_project` topology. The default workshop
> design is `single_project`; see `docs/trainer/`, `docs/participant/` and `docs/architecture/single-project-topology.md`.

The CAI environment is planned for a maximum of five active Applications in total.

## Day 1 group UI exercise

Keep these shared Applications active:

1. `bni-vllm-qwen35-9b`
2. `bni-qdrant`

Rotate the group Streamlit Applications:

| Wave | Group Applications | Total active Applications |
|---|---|---:|
| 1 | g01, g02, g03 | 5 |
| 2 | g04, g05, g06 | 5 |
| 3 | g07, g08, g09 | 5 |
| 4 | g10 | 3 |

Stop the current wave and confirm `Stopped` status before starting the next wave. Stop all group Applications before starting Phoenix.

## Day 2

Start vLLM and LiteLLM for gateway routing. Group Streamlit Applications are not required. Start other shared services only when their lab requires them.
