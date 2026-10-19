# Trainer Guide

> **Legacy multi-project guide.** This page describes the rc1 `multi_project` topology. The default workshop
> design is `single_project`; see `docs/trainer/`, `docs/participant/` and `docs/architecture/single-project-topology.md`.

## Class operating model

- 40 participants, 10 groups, 4 rotating roles per group.
- 10 group projects plus `bni-ai-training-shared`.
- One shared Qwen3.5-9B vLLM endpoint on one H200.
- One shared Qdrant collection with mandatory `group_id` filtering.
- One shared Phoenix and one shared LiteLLM Application.
- Maximum five CAI Applications active in total.
- During group UI rotation, keep vLLM and Qdrant active and run at most three group Streamlit Applications.
- Only one final Agent Studio workflow is published.

## Day 1

| Time | Module | Delivery |
|---|---|---|
| 09:00-09:30 | Architecture and objectives | Concept |
| 09:30-10:15 | Cloudera AI capabilities | Demo |
| 10:15-10:30 | Break | |
| 10:30-11:15 | Model lifecycle, Model Registry, GPU, and vLLM | Concept + demo |
| 11:15-12:00 | Agentic AI, semantic layer, RAG, and observability | Concept |
| 12:00-13:00 | Lunch | |
| 13:00-13:30 | Environment validation and model artifact | Guided lab |
| 13:30-14:00 | Shared vLLM deployment and API testing | Trainer demo + lab |
| 14:00-14:45 | CrewAI fundamentals | Guided lab |
| 14:45-15:00 | Break | |
| 15:00-15:45 | Impala or CSV tool and semantic layer | Guided lab |
| 15:45-16:15 | Multi-agent workflow and Streamlit | Guided lab |
| 16:15-16:30 | Phoenix traces and wrap-up | Demo |

## Day 2 technical morning

| Time | Module | Delivery |
|---|---|---|
| 09:00-09:15 | Day 1 validation | Review |
| 09:15-10:00 | LiteLLM gateway and routing | Concept + demo |
| 10:00-10:30 | Routing, retry, and fallback | Guided lab |
| 10:30-10:45 | Break | |
| 10:45-11:30 | Input, SQL, and output guardrails | Guided lab |
| 11:30-12:00 | Agent Studio with the shared LLM | Demo + guided exercise |

The `13:00-16:30` sharing session is owned by another team and is outside this technical bundle.

## Readiness gates

H-7: validate quota, project access, H200 availability, NFS model files, network routes, Impala mode, room, power, and Wi-Fi. H-1: run the full smoke test, index all ten group glossary partitions, test all four deployment waves, and save a redacted inventory. Day-of: stop the previous GPU workload, start only the shared services required for the current module, then open participant sessions.

