# Dataset and semantic layer

**Dataset** (`data/raw`, 12 MB): `branches` (100), `customers` (10,000), `accounts` (about 19,000), `transactions`
(about 100,000 over 24 months) and `loans` (5,000). Fully synthetic and deterministic (fixed seed, fixed reference date
2026-06-30, standard library only, identical bytes on Linux and macOS). No names, addresses, phone or identity
numbers; no BNI data; loan fields are descriptive only and nothing approves, rejects or scores credit.

**Quality gates** (`scripts/validate_dataset.py`): files and columns, row ranges, key uniqueness, foreign keys, value
domains, date and amount rules, privacy patterns, size, checksums, byte-for-byte regeneration, every mission returns
rows, and the seeded unusual patterns are discoverable.

**Semantic layer** (`semantic/`): data dictionary (with sensitivity and participant-exposure flags), relationships
(many-to-one only), 18 executable metrics with their dimensions, and plain business terms. A question is matched to
one metric and up to two dimensions; joins go only toward parent tables, so breakdowns never double count.

**Guarded CSV engine** (`src/bni_training/data/engine.py`): reuses SQLite on the CSV files; sqlglot rewrite replaces
each table with a sub-query exposing only visible columns and the bundle's row filter; an authorizer allows only
reads; results are capped and slow queries are stopped. No new service. Application-level operational isolation, not
a security boundary.

**Bundles** (`data/scenarios`): ten logical views of the one physical dataset (see `docs/trainer/group-assignment.md`).

**Backends:** CSV is the default (`DATA_BACKEND=csv`). Impala is optional, trainer-controlled, and only active with
`DATA_BACKEND=impala`; there is never a silent fallback in either direction.

**rc1 placeholder:** `data/csv` is only a temporary placeholder kept for the legacy topology and the rc1 labs.
