# Getting started (single-project workshop)

You work in a group of about four people. All ten groups use the same **Workshop Portal**, the same synthetic
banking dataset and the same shared AI model. Each group has a different **mission**.

## 0. Your Session and your notebooks

Your trainer gives you a CPU-only Jupyter **Session** and your group number. Your group has its own folder,
`workshop/runtime/groups/<your group>/`, prepared for you:

| Folder | Use |
|---|---|
| `config/group.env` | Your group id, dataset bundle, mission and workspace. No secrets. |
| `notebooks/` | Your copies of notebooks 00-12. Edit and run these. |
| `output/` | Everything you save. Write only here. |

Work in this order:

1. Open `notebooks/00_environment_validation.ipynb` and run it. It prints your `GROUP_ID`, `DATASET_ID`,
   `MISSION_ID` and `GROUP_WORKSPACE`; check they match what your trainer told you.
2. Run notebooks **03 to 11** in order (see *Lab guide* below). Read **01 and 02** if you are curious, but they are
   trainer-only: you never download the model and you never start vLLM. The trainer runs the one shared endpoint.
3. Finish with notebook **12** and the Workshop Portal (next section).

Every notebook is safe to run again. Each one ends with a status line: `PASS`, `SKIPPED` (with a reason) or `FAIL`
(with what to fix). If a notebook says a shared service is not reachable, tell your trainer; do not start your own.

## Lab guide

| Lab | What you do | Who |
|---|---|---|
| 00 Environment Validation | Check Python, your group settings and the dataset | everyone |
| 01 Model Artifact Validation | Check the model files on shared storage | trainer only |
| 02 vLLM Deployment | Start the shared model server | trainer only |
| 03 LLM API Testing | Call the shared model | participant |
| 04 CSV Data Access | Read your mission's tables with guarded SQL | participant |
| 05 Semantic Layer | Ask for metrics and breakdowns | participant |
| 06 CrewAI Tools | Give an agent a data tool limited to your group | participant |
| 07 Qdrant RAG | Search the glossary and your mission notes | participant |
| 08 Agent Workflow | Run the two-step agent workflow | participant |
| 09 Phoenix Monitoring | See your traces in the shared Phoenix | participant |
| 10 LiteLLM Routing | Use the shared gateway | participant |
| 11 Input and Output Guardrails | Block unsafe input and output | participant |
| 12 End-to-End Workshop Portal | Ask your mission questions in the Portal | participant |

## 1. Open the Portal and choose your group

1. Open the Workshop Portal link from your trainer.
2. In the sidebar, choose your group (`group_01` ... `group_10`). A link such as `?group_id=group_03` pre-selects it.
3. The page now shows **your mission**: its title, its objective, the **tables and metrics** you may use, and three
   to five **sample questions**.

## 2. Ask questions

- Click a sample question or type your own, for example `Show total customers by segment`.
- Your request is queued if the shared model is busy. You will see **Queued** (with your place in line),
  **Processing**, then **Completed** or a clear message such as *Busy*, *Timed out*, *Failed* or *Cancelled*.
  You can press **Cancel request** at any time.
- Each answer shows the SQL that produced it and is saved for you automatically (see *My outputs* in the sidebar).

## 3. Your group is locked after your first question

After your first question the group selector is disabled so that your chat, outputs and results stay yours.
If you picked the wrong group, open **Reset session** in the sidebar, tick the confirmation and press the button.
Reset deletes this session's chat, outputs and temporary files, then lets you choose again. It never affects other
people or other groups.

## What you can and cannot do

| You can | You cannot |
|---|---|
| Use the tables and metrics listed for your mission | Query tables or metrics that belong to another mission |
| Break a metric down by up to two dimensions (`by region and segment`) | Write data, run commands, or read files |
| Look up glossary terms and your mission notes (Qdrant, your group only) | See another group's chat, outputs or results |

Everything in the workshop is **fully synthetic**. There are no real customers, and nothing here makes lending
decisions: loan fields describe the data only.

## Important: this is operational separation, not security

Everyone works in the same CAI project. The Portal keeps groups apart to prevent accidents, but it is not a security
boundary. Do not run Git commands, and do not edit the `data`, `semantic`, `src`, `config` or `deployments` folders.
