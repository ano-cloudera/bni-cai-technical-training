# Trainer: group assignment and missions

One physical dataset (`data/raw`) serves ten **logical bundles** defined in `data/scenarios/`. A bundle lists the
tables, optional row filters and metrics a group may use, plus its mission. Nothing is copied per group.

| Group | Mission | Logical tables |
|---|---|---|
| group_01 | Customer Portfolio Summary | customers, accounts |
| group_02 | Transaction Trend Analysis | transactions, accounts |
| group_03 | Loan Portfolio Monitoring | loans, customers, accounts |
| group_04 | Branch Performance | branches, accounts, transactions, loans (closed branches hidden) |
| group_05 | Dormant Account Analysis | accounts, customers |
| group_06 | Unusual Transaction Patterns | transactions, accounts |
| group_07 | Customer Segmentation | customers, accounts |
| group_08 | Product Adoption | accounts, loans, customers |
| group_09 | Regional Comparison | branches, customers, accounts, transactions, loans |
| group_10 | Management Summary | all five tables |

Files: `data/scenarios/dataset_bundles.yaml` (tables, filters, metrics), `group_assignments.yaml` (group, bundle,
mission title and objective), `sample_questions.yaml` (3-5 questions per mission). The catalog validates all three
at load time (unknown tables or metrics, metrics that need tables outside the bundle, question counts, and that
every sample question resolves).

Run `scripts/assign_participants.py` to spread about 40 participants over the ten groups (at most five per group;
trainer-only output). Participants choose their group in the Portal; it is locked after the first question. Tell groups their number.
Group 06 can find the unusual patterns with ordinary queries (a one-day burst of transactions, an amount far above the
account's norm for that type, repeated amounts just below 10,000); the validator proves it.
