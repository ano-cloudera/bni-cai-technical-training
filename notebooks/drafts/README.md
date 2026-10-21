# Notebook drafts

Redesign drafts that are **not** part of the 13 canonical templates. Nothing here is built into `notebooks/templates/`, copied into
group workspaces, or read by the tests. A draft is promoted by moving its source into `notebooks/authoring/` (under the canonical
name) and running `python scripts/build_notebooks.py`.

Labs 04 to 08 were drafted here, tried in the sandbox, and promoted to `notebooks/authoring/` (they are the canonical guided
notebooks now; the draft files were removed so there is one source of truth). Use this folder for the next lab to be redesigned.
Never run a notebook from here: open the copy in a group workspace, so `config/group.env` is found and the mode is `cai`.

## 09_phoenix_monitoring_v2

Guided version of Lab 09 (tracer, secret filter shown as a table, parent and child spans with kind and duration, a check of the
parent link, finding the trace, proving the secret never arrived, group_id as a search label, an exercise, a closing list). It keeps the
required section titles and the saved `09_trace_summary.json`. Executed locally for group_03, group_05 and group_09 (in-memory exporter,
PASS). Not yet run against the shared Phoenix. To try it, copy the `.ipynb` into a group workspace and open the copy there.

## 03_llm_api_testing_v2

Guided version of Lab 03 (the request as two tables, thinking switched off, a bounded retry, the answer and token usage, streaming with the time
to the first piece, two temperatures, a max_tokens cut-off with finish_reason, an exercise, a closing list). It keeps the saved
`03_llm_api_result.json`. Executed locally (mock model) for group_03, group_05 and group_09: PASS. Not yet run against the shared vLLM.
Copy the `.ipynb` into a group workspace and open the copy there; Lab 03 needs no service-address cell.

## 10_litellm_routing_v2, 11_guardrails_v2 and 12_end_to_end_portal_v2

Guided versions of Labs 10 to 12 (Day 2), same pattern as Labs 03 to 09. Lab 10 explains aliases, retry versus fallback, and never prints the key
(in `cai` mode it asks for the key with `getpass` when `LITELLM_API_KEY` is not set); Lab 11 shows the three rules, a real wrapped model call and
the limit of a phrase rule (a reworded injection passes); Lab 12 walks the Portal states and compares the Portal SQL with the Lab 05 path, and shows
"see the Portal sidebar" for the lock in `cai` mode instead of `False`. The Service addresses cell now also accepts a pasted `https://...` address.
All three were executed locally (mock services) for group_03, group_05, group_09, group_10, group_04 and group_06. Not yet run against the real
services. To try one, copy the `.ipynb` into a group workspace and open the copy there.
