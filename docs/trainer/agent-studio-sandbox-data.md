# Agent Studio tool: how the sandbox reaches the data

Agent Studio runs each custom tool in a sandbox. The sandbox does not see `/home`, so a `csv_dir` that points to the
project folder fails with `csv_dir_exists: false` (seen at BNI and in the sandbox environment).

## What the Cloudera documentation says (checked 2026-10-23)

- `/workspace` is the working directory and the only writable place (the artifact file directory, `SESSION_DIRECTORY`).
- `/workflow_data` is a **read-only mount of project files** (`WORKFLOW_DATA_DIRECTORY`). Absolute paths such as
  `/home/cdsw/...` are not reachable.
- `/tool` (tool code) and `/venv` (packages) are read-only.
- A tool can mount more folders with a `config.json` file placed in the tool directory (Collaborator access or higher on
  the Agent Studio project). Settings live under `"sandbox"`: `timeout`, `mounts` (`host_path`, `sandbox_path`,
  `read_only`, `required`) and `environment.variables`. Mounts are always read-only. `sandbox_path` must start with one of
  `/usr /lib /bin /sbin /opt /var /sys /etc /home/cdsw /runtime-addons /tmp`.
- Not documented: which project folder is exposed as `/workflow_data`, whether a mount survives re-saving a tool, and
  whether it applies to deployed workflows. Verify each one.

## What the tool does now

`csv_data_tool/tool.py` looks for the CSV files in this order: the configured `csv_dir`, `$WORKFLOW_DATA_DIRECTORY/data/raw`,
`.../raw`, `$WORKFLOW_DATA_DIRECTORY`, then `/workspace`. On failure it returns the diagnostics: what `/workflow_data`, `/tool`,
`/workspace`, `/home` and `/` contain (names only).

## Option 1: mount the repository data folder (documented)

Add `config.json` to the tool directory:

```json
{
  "sandbox": {
    "mounts": [
      {
        "host_path": "/home/cdsw/bni-cai-technical-training/data",
        "sandbox_path": "/home/cdsw/bni-cai-technical-training/data",
        "read_only": true,
        "required": true
      }
    ]
  }
}
```

Then set `csv_dir` to `/home/cdsw/bni-cai-technical-training/data/raw` and leave `bundles_file` empty
(the tool finds `../scenarios/dataset_bundles.yaml`).

## Option 2: put the files where `/workflow_data` comes from

Find the folder that is mounted as `/workflow_data` (the diagnostics print `workflow_data_entries`), and place
`data/raw/*.csv` and `data/scenarios/dataset_bundles.yaml` under it.

## Verify

Ask `Show total loans by loan status`. Expected: CURRENT 3109, PAID_OFF 992, GRACE 441, DEFAULTED 231, DELINQUENT 227.
If the tool returns `diagnostics`, send `workflow_data_entries`, `tool_entries` and `home_entries`.
