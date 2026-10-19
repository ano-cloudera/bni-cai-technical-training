# Getting started (single-project workshop)

You work in a group of about four people. All ten groups use the same **Workshop Portal**, the same synthetic
banking dataset and the same shared AI model. Each group has a different **mission**.

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
