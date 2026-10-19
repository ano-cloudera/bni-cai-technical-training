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
`data/manifests/` holds `dataset_manifest.json`, `checksums.json` and `anomaly_test_manifest.json`. The last one
lists the deliberately seeded unusual transactions for automated tests and trainer validation only; it is never
read by the Workshop Portal and is never shown to participants.

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
multi-project topology and the rc1 labs keep working, and it is not used by the single-project Workshop Portal.

## Other folders

`data/generator/` is the rc1 generator, `data/glossary/` the banking glossary used for retrieval, and
`data/impala/` the rc1 Impala DDL.
