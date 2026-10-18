# Participant Guide

## Team model

Forty participants work in ten groups of four. Rotate Driver, LLM Engineer, Data Engineer, and Tester roles after each major lab. Each group uses one project and one `GROUP_ID`. Streamlit deployment rotates in four waves: groups 01-03, 04-06, 07-09, and 10. Groups waiting for a deployment slot run the same UI from their Workbench session.

## Preparation

1. Open the assigned `bni-ai-training-gNN` project and a Python 3.10 PBJ JupyterLab session.
2. Copy `.env.example` to an untracked `.env`, set only trainer-supplied values, then export it with `set -a; source .env; set +a`.
3. Run `python scripts/bootstrap.py participant` or the approved offline equivalent.
4. Run notebook 00 and confirm the expected environment output.
5. Follow notebooks in numerical order. Lab 02 is trainer-led.

CSV mode is always explicit: `DATA_MODE=csv`. Impala modes are `impala_gssapi` and `impala_ldap`. An authentication failure does not switch modes automatically.

Never paste API keys into notebooks, chat prompts, screenshots, source files, or Phoenix attributes. Stop only your assigned group Application.

