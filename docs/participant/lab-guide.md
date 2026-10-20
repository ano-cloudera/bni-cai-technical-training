# Lab guide: what each lab is for

This guide explains the purpose of each notebook in `notebooks/templates/`. Read it before you open a lab.
Participants start with Lab 00, then work through Labs 03 to 12 in order. Labs 01 and 02 are for the trainer only.

Everything uses fully synthetic banking data. Nothing here makes lending decisions.

## Words used in the labs

| Word | Plain meaning |
|---|---|
| Model / LLM | The AI model that reads text and writes text. Your group shares one model. |
| vLLM | The program that runs the model on a GPU and answers requests. Only the trainer starts it. |
| Endpoint | The web address your notebook sends requests to. |
| Payload | The data you send to the model: the messages and the settings. |
| Token | A small piece of text. Models count input and output in tokens. |
| SQL | The language used to ask questions of a table, for example `SELECT ... FROM accounts`. |
| Metric | A business number, such as "total customers" or "average balance". |
| Dimension | A way to split a metric, such as "by region". |
| Agent | A model that can use tools and follow a role, such as "analyst". |
| Tool | A function an agent can call, such as "run a query for my group". |
| RAG | Retrieval-augmented generation: find relevant text first, then ask the model to answer with it. |
| Vector / embedding | A list of numbers that represents the meaning of a text. Similar texts get similar numbers. |
| Qdrant | The database that stores those vectors. |
| Trace / span | A record of what the system did, step by step, with timing. |
| Phoenix | The tool that shows traces, so you can see what happened. |
| LiteLLM | A gateway in front of models. It can route a request and retry or switch to a backup. |
| Guardrail | A rule that blocks unsafe or wrong input or output. |
| Group ID | Your group, `group_01` to `group_10`. Your data and results are kept apart by this ID. |
| Mission | The question set your group works on. It decides which tables you may use. |

## Lab 00: Environment Validation (everyone, first)

- **Purpose:** check that your session, your group settings and the dataset are ready before anything else.
- **You learn:** which group you are in, which mission you have, and which services the lab can reach.
- **Expected result:** the notebook shows your group ID and mission, and passes. A GPU check is skipped in a CPU session, which is normal.
- **If it fails:** tell your trainer and show them the line that failed. Do not change the settings yourself.

## Lab 01: Model Artifact Validation (trainer only)

- **Purpose:** check that the model files are complete on shared storage.
- **Participants:** you can read it, but do not run it. You never download the model.

## Lab 02: vLLM Deployment (trainer only)

- **Purpose:** show how the one shared model server is set up and checked.
- **Participants:** read only. You never start the model server. The shared server is already running.

## Lab 03: LLM API Testing (first participant lab)

- **Purpose:** send your first requests to the shared model and read the answers.
- **You learn:** how a request is built (messages, temperature, token limit), how to read the answer and usage,
  how to receive a streamed answer piece by piece, and what a busy or failing service looks like.
- **Expected result:** a normal answer, a streamed answer, and a saved file in your group's output folder.
- **Why thinking is off:** Qwen3.5 can write hidden "thinking" text that uses up the token budget. The lab sets
  `enable_thinking=false` so you see only the final answer.

## Lab 04: CSV Data Access

- **Purpose:** look at the data your group may use, and ask it questions with SQL.
- **You learn:** which tables and columns your mission gives you, how to write a read-only query, and why some
  requests are refused (other tables, write commands, or another group's data).
- **Expected result:** query results shown in the notebook, and a saved result.

## Lab 05: Semantic Layer

- **Purpose:** translate a business question into SQL automatically, and check that the answer is correct.
- **You learn:** what a metric and a dimension are, how the data dictionary and relationships work, and why
  metrics outside your mission are refused.
- **Expected result:** the planned SQL is shown, the rows come back, and the result matches the metric.

## Lab 06: CrewAI Tools

- **Purpose:** build a small tool that an agent can call to get data for your group.
- **You learn:** how to define a tool, how an agent and a task are described, and how to inspect which tool
  calls happened.
- **Expected result:** the tool returns rows for your group, and a request for another group is refused.

## Lab 07: Qdrant RAG

- **Purpose:** store glossary and mission notes as vectors, then find the most relevant ones for a question.
- **You learn:** what an embedding is, how a search works, and why every search must filter by your `group_id`.
- **Expected result:** search results that all belong to your group. No other group's note appears.

## Lab 08: Multi-Agent Workflow

- **Purpose:** combine two agents: one analyses the data, the other reviews the analysis.
- **You learn:** how one agent's output becomes the next agent's input, and how a reviewer checks whether an
  answer is supported by the data.
- **Expected result:** the question, the SQL, the rows, the analyst's answer and the reviewer's answer are shown,
  and the final answer is marked as grounded or rejected.

## Lab 09: Phoenix Monitoring

- **Purpose:** record what the system does as traces, so you can see each step and its timing.
- **You learn:** what a parent and a child span are, which group information is attached, and that secret-like
  values are removed before they are sent.
- **Expected result:** your trace appears in Phoenix with your group ID. No secret appears in it.

## Lab 10: LiteLLM Routing

- **Purpose:** send requests through the shared gateway and see how it picks a model.
- **You learn:** what a model alias is, how a retry differs from a fallback, and why keys are never printed.
- **Expected result:** the gateway answers. If the main route is unavailable, the fallback is shown.

## Lab 11: Input and Output Guardrails

- **Purpose:** block unsafe or wrong input, and check the model's output before you use it.
- **You learn:** three kinds of rule (input length and content, SQL limits, and whether an answer is supported by
  numbers from the data), and why a rule is not a complete protection.
- **Expected result:** the accepted and rejected samples are shown in a table, and you add one rule of your own.

## Lab 12: End-to-End Workshop Portal

- **Purpose:** use the shared Portal, and check that your notebook work matches what the Portal does.
- **You learn:** the Portal's queue states (queued, processing, completed, busy, timed out), why your group is
  locked after the first question, and where saved answers are stored.
- **Expected result:** the Portal is healthy, you have a saved answer for your group, and it matches the SQL from
  Lab 05.

## Suggested order for a session

1. Lab 00 (everyone).
2. Labs 03 to 04 (one hour, the basics).
3. Labs 05 to 06 (business logic and tools).
4. Labs 07 to 09 (search and monitoring). These are the most technical.
5. Labs 10 to 12 (gateway, guardrails and the Portal).

If time is short, stop after Lab 08. Labs 10 to 12 depend on shared services that your trainer may not have started yet.
