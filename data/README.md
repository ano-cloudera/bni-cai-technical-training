# Data

## `data/raw/` and `data/manifests/` - the workshop dataset

Five CSV files of **fully synthetic** banking data, generated deterministically by
`scripts/generate_synthetic_data.py` (fixed seed, fixed reference date 2026-06-30, standard library only, no
network). There are no names, addresses, phone numbers or identity numbers, and no BNI data.

| File | Rows (about) | Key |
|---|---:|---|
| `branches.csv` | 100 | `SYN-BR-xxxxx` |
| `customers.csv` | 10,000 | `SYN-CUST-xxxxx` |
| `accounts.csv` | 19,000-20,000 | `SYN-ACC-xxxxx` |
| `transactions.csv` | about 100,000 | `SYN-TXN-xxxxxx` |
| `loans.csv` | 5,000 | `SYN-LOAN-xxxxx` |

The whole dataset is about 12 MB (limit: 50 MB). Columns are described in `semantic/data_dictionary.yaml`.
`data/manifests/` holds `dataset_manifest.json` and `checksums.json`. The unusual patterns for Group 06 are in the
data but nothing in the project marks or lists them; participants have to discover them with queries.

One physical copy serves all ten groups. Each group sees a **logical bundle** (tables, optional row filters,
metrics, mission) defined in `data/scenarios/`; the files are not duplicated per group. The separation is
operational, not a security boundary.

```bash
python scripts/generate_synthetic_data.py --preview
python scripts/generate_synthetic_data.py --output-dir data/raw --manifest-dir data/manifests
python scripts/validate_dataset.py
```

Regenerating with the default seed reproduces the committed files byte for byte (compare `checksums.json`).

CSV is the default participant backend (`DATA_BACKEND=csv`). Impala is an optional, trainer-controlled extension
(`DATA_BACKEND=impala`) and is never required.

## `data/csv/` - rc1 placeholder (temporary)

The rc1 dataset (six tables, loan-account oriented) is **only a temporary placeholder**. It is kept so the legacy
multi-project topology and the rc1 labs keep working, and it is used by neither the single-project Workshop Portal nor the migrated labs and notebook templates 00-12.

## Other folders

`data/generator/` is the rc1 generator, `data/glossary/` the banking glossary used for retrieval, and
`data/impala/` the rc1 Impala DDL.
