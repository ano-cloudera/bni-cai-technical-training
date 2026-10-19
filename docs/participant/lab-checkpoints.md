# Checkpoints

Use these to check your progress with your trainer. Each is something you can see in the Portal.

1. **Joined:** your mission title and objective are shown; the group selector says *Locked to group_xx* after your
   first question.
2. **First answer:** a sample question completed and a `SELECT` statement is shown under the answer.
3. **Your own question:** you asked a question that is not a sample question, using a metric and a breakdown from
   the lists for your mission.
4. **Understanding:** you can explain which table(s) the answer used and what the metric means (see
   `semantic/business_terms.yaml`).
5. **Limits:** you tried a metric outside your mission and read the friendly message.
6. **Saved:** *My outputs* lists at least two saved answers.

Notebook checkpoints:

| Labs | Visible checkpoint |
|---|---|
| 00 | Group, anonymous participant mode, mission, dataset, and writable output |
| 03-05 | Bounded API response, guarded CSV rows, and visible semantic SQL |
| 06-08 | Group-bound CrewAI tool, filtered RAG, then question/SQL/rows/Analyst/Reviewer outputs |
| 09-11 | Safe trace attributes, bounded gateway fallback, and accepted/blocked guardrail samples |
| 12 | Portal health, queue state, group lock, saved identity, and SQL comparison |

Each ends with `LAB_STATUS PASS` (or an explained `SKIPPED`). Outputs are in the active group-driver or anonymous
participant `output/` folder.
