# %% [markdown]
# # Lab 07: Qdrant RAG
#
# **Audience:** Participant
# **Estimated duration:** 40–50 minutes
#
# ## Learning objectives
# By the end you can: explain what an embedding is, search a vector database by meaning, see why every search carries your
# `group_id`, turn search hits into context for an answer, and run a search of your own.
#
# ## How this notebook is organised
# 1. **Setup (one cell).** It connects to Qdrant and loads the embedding model. You do not edit it.
# 2. **Eight steps.** Each step says what the next cell does and why, you run it, and you read what it prints.
# 3. **Your turn.** You choose a question and a number of results.
# 4. **Closing.** A list of what you proved, and the questions to explain back to your trainer.
#
# Run the cells from top to bottom. Complete Lab 00 first.
#
# ## Prerequisites
# Complete Lab 00. In `cai` mode this lab needs `QDRANT_URL` and `EMBEDDING_MODEL_PATH`.
#
# ## Architecture context
# All groups share **one** Qdrant collection. The trainer stored the glossary and the mission notes before the workshop; you only
# search. A search turns your question into a list of numbers (an **embedding**) and returns the stored texts whose numbers are
# closest. Storing and searching must use the same embedding model: a small stand-in in `local` mode, bge-m3 in `cai` mode.

# %% [markdown]
# ## Service addresses (fill in once)
# This lab calls shared services. All of their addresses end with the same **Applications domain**. Ask your trainer for it and paste it
# between the quotes below. If your trainer already set the variable `APPS_DOMAIN`, leave the quotes empty. Nothing secret goes in
# this cell, and a value that is already set elsewhere is never replaced.

# %%
import os

APPS_DOMAIN = ""  # paste the Applications domain from your trainer between the quotes
APPS_DOMAIN = APPS_DOMAIN or os.getenv("APPS_DOMAIN", "")


def service_url(app, path="", port=""):
    """The address of a shared Application: its name, the domain you pasted above, an optional port and path."""
    from urllib.parse import urlunsplit

    return urlunsplit(("https", f"{app}.{APPS_DOMAIN}{port}", path, "", ""))
if APPS_DOMAIN:
    os.environ.setdefault("QDRANT_URL", service_url("bni-qdrant", port=":443"))
    os.environ.setdefault("EMBEDDING_MODEL_PATH", "/home/cdsw/models/bge-m3")

# %% [markdown]
# ## Configuration validation (setup)
# This cell finds the repository, reads your group's settings, connects to Qdrant and loads the embedding model. In `cai` mode
# loading the model takes about half a minute. You do not need to change anything. It prints the mode, the collection name and
# the embedding model, never a credential.

# %%
# Setup: find the repository, load your group's settings, connect to Qdrant and load the embedder. Nothing to edit.
import json
import os
import sys
import warnings
from pathlib import Path

import pandas as pd
from IPython.display import display

def _repo_root() -> Path:
    # A generated group workspace records the repository in config/group.env, so no setup is needed.
    env_file = Path.cwd().parent / "config" / "group.env"
    saved = dict(line.split("=", 1) for line in env_file.read_text().splitlines() if "=" in line) if env_file.is_file() else {}
    if os.getenv("BNI_REPO_ROOT") or saved.get("BNI_REPO_ROOT"):
        return Path(os.getenv("BNI_REPO_ROOT") or saved["BNI_REPO_ROOT"])
    found = [p for p in (Path.cwd().resolve(), *Path.cwd().resolve().parents) if (p / "pyproject.toml").is_file()]
    assert found, "Open this notebook from a generated group workspace, or set BNI_REPO_ROOT."
    return found[0]


ROOT = _repo_root()
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
from bni_training.workshop.notebook_support import load_group_env

# Values already set in the Session environment win over config/group.env.
group_env = Path.cwd().parent / "config" / "group.env"
load_group_env(group_env)
LAB_MODE = os.getenv("LAB_MODE", "local").lower()
if group_env.is_file() and not os.getenv("GROUP_ENV_FILE"):
    os.environ["GROUP_ENV_FILE"] = str(group_env)
from qdrant_client import QdrantClient, models
from bni_training.rag import COLLECTION, HashingEmbedder, SentenceTransformerEmbedder
from bni_training.workshop.lab_context import resolve_lab_context

context = resolve_lab_context(LAB_MODE)
if LAB_MODE == "local":
    client = QdrantClient(":memory:")
else:
    assert os.getenv("QDRANT_URL"), "QDRANT_URL is required in CAI mode; no local fallback is allowed."
    client = QdrantClient(url=os.environ["QDRANT_URL"], api_key=os.getenv("QDRANT_API_KEY") or None)
# Local mode uses the hashing stand-in. In CAI the trainer stored the texts with bge-m3, so the question must use the same model.
if LAB_MODE == "local":
    embedder = HashingEmbedder()
else:
    model_path = os.getenv("EMBEDDING_MODEL_PATH", "")
    assert os.path.isdir(model_path), "EMBEDDING_MODEL_PATH must point to the bge-m3 folder on NFS; ask the trainer."
    embedder = SentenceTransformerEmbedder(model_path)
proved = []  # one sentence per thing you prove; printed in the closing
print({"mode": LAB_MODE, "collection": COLLECTION, "embedding": embedder.name, "dimensions": embedder.dim})

# %% [markdown]
# ## Step-by-step implementation
# Each step says what the cell does, why it matters and what to look for.
#
# ## Step 1. What is an embedding?
# **What it does:** turns the phrase "delinquency rate" into a list of numbers and shows the first eight.
#
# **Why it matters:** a computer cannot compare meanings, but it can compare numbers. An embedding maps a text to a point in a
# space, and texts with similar meaning land close together.
#
# **Predict first:** how many numbers do you expect in the list? Compare with `dimensions` in the Setup output.

# %%
vector = embedder.embed("delinquency rate")
display(pd.DataFrame({"position": range(8), "value": [round(value, 4) for value in vector[:8]]}))
print("Length of the full list:", len(vector))
assert len(vector) == embedder.dim
proved.append(f"I turned a phrase into {len(vector)} numbers")

# %% [markdown]
# ## Step 2. Close numbers, close meaning
# **What it does:** compares "delinquency rate" with three other phrases using cosine similarity (1.0 means identical direction, 0
# means unrelated).
#
# **Why it matters:** search is exactly this comparison, repeated over every stored text.
#
# **Look for:** the real model (bge-m3, `cai` mode) scores "share of late loans" clearly above "branch opening hours". The small
# stand-in in `local` mode only notices shared words, so its scores are cruder.

# %%
def cosine(first, second):
    return sum(a * b for a, b in zip(first, second))

reference = embedder.embed("delinquency rate")
phrases = ["delinquency rate", "share of late loans", "delinquency ratio", "branch opening hours"]
scores = [round(cosine(reference, embedder.embed(phrase)), 3) for phrase in phrases]
display(pd.DataFrame({"compared with 'delinquency rate'": phrases, "similarity": scores}))
assert scores[0] >= 0.99, "A phrase must be identical to itself."
proved.append("I compared phrases by the closeness of their numbers")

# %% [markdown]
# ## Step 3. What is stored for my group?
# **What it does:** counts the texts stored in the shared collection for your group. In `local` mode it first stores two small
# groups itself, so the lab can run without a server. In `cai` mode the trainer already stored everything.
#
# **Why it matters:** every stored text carries its `group_id`. If the count is zero, the trainer has not stored your group yet
# and the search below cannot work.
#
# **Predict first:** how many texts does your group have?

# %%
from bni_training.data.bundles import BundleCatalog
from bni_training.rag import index_group_documents

def mission_documents(bundle):
    return [{
        "chunk_id": f"mission-{bundle.mission_id}",
        "title": bundle.mission_title,
        "document_type": "mission",
        "source": "synthetic-workshop",
        "text": f"{bundle.mission_title}. {bundle.mission_objective}",
    }]

if LAB_MODE == "local":
    other_group = "group_02" if context.group_id != "group_02" else "group_03"
    other_bundle = BundleCatalog.load().for_group(other_group)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for bundle in (context.bundle, other_bundle):
            index_group_documents(client, bundle.group_id, mission_documents(bundle), embedder.embed_many)
    print("LOCAL MODE: two small groups were stored for this exercise.")
else:
    print("CAI MODE: the trainer stored the texts before the workshop; you only search.")
my_filter = models.Filter(must=[models.FieldCondition(key="group_id", match=models.MatchValue(value=context.group_id))])
stored = client.count(collection_name=COLLECTION, count_filter=my_filter, exact=True).count
print(f"Texts stored for {context.group_id}: {stored}")
assert stored > 0, "No texts are stored for your group; ask the trainer to verify the shared index."
proved.append(f"I confirmed {stored} texts are stored for my group")

# %% [markdown]
# ## Step 4. The filter that keeps groups apart
# **What it does:** prints the exact filter that is added to every search.
#
# **Why it matters:** the collection holds all groups. The `must` condition on `group_id` is what limits a search to your texts. It
# is a rule of the workshop application, not a security boundary.
#
# **Look for:** one condition, with your own group id.

# %%
from bni_training.rag import group_filter_json

filter_json = group_filter_json(context.group_id)
assert filter_json == {"must": [{"key": "group_id", "match": {"value": context.group_id}}]}
print(json.dumps(filter_json, indent=2))
proved.append("I saw the group filter that every search carries")

# %% [markdown]
# ## Step 5. Search by meaning
# **What it does:** searches with your mission title as the question and returns the three closest texts. `search_group` always adds
# the filter from Step 4 and checks every hit again.
#
# **Why it matters:** this is retrieval, the "R" in RAG. You get the stored texts nearest to the meaning of the question.
#
# **Predict first:** which text will be first? Then read the `score` column (higher is closer).

# %%
from bni_training.rag import search_group

retrieval_question = context.bundle.mission_title
hits = search_group(client, context.group_id, retrieval_question, embedder.embed, limit=3)
assert hits, "No group-scoped documents were found; ask the trainer to verify the shared index."
display(pd.DataFrame([{"title": hit["title"], "type": hit.get("document_type"), "score": round(hit["score"], 3), "group_id": hit["group_id"]} for hit in hits]))
proved.append("I searched by meaning and read the scores")

# %% [markdown]
# ## Step 6. Are all hits mine?
# **What it does:** checks that every hit belongs to your group.
#
# **Why it matters:** retrieval must never leak another group's text. `search_group` checks this itself, and here you check it
# too, so you see the proof.
#
# **Look for:** a set that contains only your group id.

# %%
hit_groups = {hit["group_id"] for hit in hits}
print("Groups found in the hits:", sorted(hit_groups))
assert hit_groups == {context.group_id}
proved.append("Every hit belonged to my group")

# %% [markdown]
# ## Step 7. From hits to context for an answer
# **What it does:** joins the hit texts into one block and puts it into a prompt that tells a model to answer only from that block.
# It does not call a model.
#
# **Why it matters:** this is the "G" in RAG (generation). The model is given your retrieved facts, so its answer is grounded in
# them and not in its memory.
#
# **Look for:** the context block inside the prompt.

# %%
formatted_context = "\n\n".join(f"{hit['title']}: {hit['text']}" for hit in hits)
prompt = (
    "Answer the question using only the context below. If the context does not contain the answer, say so.\n\n"
    f"Context:\n{formatted_context}\n\nQuestion: {retrieval_question}"
)
print(prompt)
proved.append("I built a grounded prompt from the retrieved context")

# %% [markdown]
# ## Step 8. More results, same order
# **What it does:** searches again for one result and for five results.
#
# **Why it matters:** `limit` only decides how many hits you get. The best match stays first and the scores go down the list.
#
# **Look for:** the first row is the same in both tables.

# %%
one = search_group(client, context.group_id, retrieval_question, embedder.embed, limit=1)
five = search_group(client, context.group_id, retrieval_question, embedder.embed, limit=5)
display(pd.DataFrame([{"title": hit["title"], "score": round(hit["score"], 3)} for hit in five]))
assert len(one) <= 1 and len(five) <= 5
assert [hit["score"] for hit in five] == sorted((hit["score"] for hit in five), reverse=True)
assert one[0]["title"] == five[0]["title"]
proved.append("I saw that limit changes how many hits, not their order")

# %% [markdown]
# ## Hands-on exercise: your turn
# Change `exercise_question` and `exercise_limit` (from 1 to 5) and run the cell.
#
# - Easy: search for "late payments".
# - Medium: search for a term from your glossary, for example "DPD 30" or "approval rate".
# - Hard: write a question in other words, with no word from the stored title, and see whether it still finds the right text.
#
# **Predict first:** which stored text should come first? In `local` mode the small stand-in matches only shared words, so a
# reworded question may find less than in `cai` mode.

# %%
# EXERCISE: edit only the question and a limit from 1 through 5.
exercise_question = context.bundle.mission_title
exercise_limit = 2
assert 1 <= exercise_limit <= 5, "Use a limit from 1 to 5."
exercise_hits = search_group(client, context.group_id, exercise_question, embedder.embed, limit=exercise_limit)
assert exercise_hits and {item["group_id"] for item in exercise_hits} == {context.group_id}
display(pd.DataFrame([{"title": item["title"], "score": round(item["score"], 3)} for item in exercise_hits]))
proved.append("I ran a search of my own")

# %% [markdown]
# ## Save your checkpoint
# **What it does:** writes only the titles, scores and group ids of your last search to your group's output folder.
#
# **Why it matters:** the file holds no vector, no credential and no endpoint, so it is safe to keep and share with the trainer.

# %%
safe_hits = [{key: hit[key] for key in ("title", "group_id", "score")} for hit in exercise_hits]
saved = context.write_output("07_retrieval.json", json.dumps(safe_hits, indent=2))
print({"saved": saved.name})
proved.append("I saved a checkpoint with no vector or credential")

# %% [markdown]
# ## Closing: what you proved
# The next cell prints one line for every step you completed. If a line is missing, a step did not run: scroll up and run it.
#
# ## Expected result
# Ten lines. A phrase became numbers, similar phrases scored higher, your group's texts are stored, the group filter is visible, every
# hit is yours, and one checkpoint file is saved.
#
# ## Common errors
# A missing collection or no stored text for your group means the trainer should verify the shared index. A missing `QDRANT_URL` fails in
# `cai` mode; it never switches to local mode silently. A dimension error means the question was embedded with another model than the one used for storing.
#
# ## Completion checkpoint
# Explain in your own words:
# 1. What is an embedding, and why do similar meanings give close numbers?
# 2. Why must storing and searching use the same embedding model?
# 3. Why does every search carry the group filter, and why does the code check the hits again?
#
# ## Reference implementation
# `bni_training.rag` contains the embedders and the enforced filter; `scripts/07_qdrant_rag.py` is the trainer and reference flow.
#
# ## Cleanup
# The next cell closes the Qdrant client. Do not delete or recreate the shared collection.

# %%
from bni_training.workshop.notebook_support import lab_status

for number, sentence in enumerate(proved, start=1):
    print(f"{number:>2}. {sentence}")
client.close()
context.close()
lab_status("07", LAB_MODE, passed=len(proved), skipped=2 if LAB_MODE == "local" else 0)
