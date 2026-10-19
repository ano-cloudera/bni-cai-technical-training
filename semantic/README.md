# Semantic layer

A small, human-readable description of the fully synthetic banking dataset in `data/raw/`. Nothing here depends on
an external semantic platform; the files are plain YAML that participants can read during the workshop.

| File | What it defines |
|---|---|
| `data_dictionary.yaml` | Every table and column: meaning, type, key role, allowed values, sensitivity, and whether participant tools may expose it |
| `relationships.yaml` | Valid joins and their cardinality (always many-to-one toward the parent) |
| `metrics.yaml` | 18 executable metrics and the dimensions they can be broken down by |
| `business_terms.yaml` | Plain definitions such as "dormant account" and "digital transaction" |

How a question becomes SQL: the question is matched to one metric and up to two dimensions, the planner adds the
joins from the metric's base table toward the parent tables, and the guarded CSV engine runs the result. Only the
tables and metrics assigned to your group's logical bundle (`data/scenarios/`) are available.

The older `credit_portfolio.yaml` belongs to the rc1 placeholder dataset in `data/csv` and is kept for the legacy
multi-project topology.
