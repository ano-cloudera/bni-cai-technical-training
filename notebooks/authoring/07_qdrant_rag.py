# %% [markdown]
# # Lab 07: Qdrant RAG
#
# **Audience:** Participant  
# **Estimated duration:** 40–50 minutes
#
# ## Learning objectives
# Connect to Qdrant, build a deterministic CPU embedding, inspect the mandatory `group_id` filter, retrieve context, and verify every hit's group.
#
# ## Architecture context
# All groups share one Qdrant collection. The trainer pre-indexes it before CAI hands-on; participants only query it. Index and query use the same lightweight hashing embedder for this learning flow.
#
# ## Prerequisites
# Complete Lab 00. The participant profile includes `qdrant-client` but no sentence-transformers or GPU PyTorch requirement. CAI mode needs `QDRANT_URL`.

# %% [markdown]
# ## Configuration validation
# Resolve the group context and connect to an in-memory local client or the configured shared Application. Expect the mode and collection name without exposing authentication.

# %%
# Load the group context and connect without downloading any model.
import json
import os
import sys
import warnings
from pathlib import Path

ROOT = Path(os.getenv("BNI_REPO_ROOT", "")) if os.getenv("BNI_REPO_ROOT") else next(
    path for path in (Path.cwd().resolve(), *Path.cwd().resolve().parents)
    if (path / "pyproject.toml").is_file()
)
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
LAB_MODE = os.getenv("LAB_MODE", "local").lower()
group_env = Path.cwd().parent / "config" / "group.env"
if group_env.is_file() and not os.getenv("GROUP_ENV_FILE"):
    os.environ["GROUP_ENV_FILE"] = str(group_env)
from qdrant_client import QdrantClient
from bni_training.rag import COLLECTION, HashingEmbedder
from bni_training.workshop.lab_context import resolve_lab_context

context = resolve_lab_context(LAB_MODE)
if LAB_MODE == "local":
    client = QdrantClient(":memory:")
else:
    assert os.getenv("QDRANT_URL"), "QDRANT_URL is required in CAI mode; no local fallback is allowed."
    client = QdrantClient(url=os.environ["QDRANT_URL"], api_key=os.getenv("QDRANT_API_KEY") or None)
embedder = HashingEmbedder()
print({"mode": LAB_MODE, "collection": COLLECTION, "embedding": embedder.name, "dimensions": embedder.dim})

# %% [markdown]
# ## Step-by-step implementation
# Local mode creates teaching documents and indexes two partitions with the same embedder. In CAI this step is skipped because the trainer already indexed the shared collection. Expect a clear ownership message.

# %%
# Prepare deterministic learning documents; index only in isolated local mode.
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
            indexed = index_group_documents(client, bundle.group_id, mission_documents(bundle), embedder.embed_many)
            print({"indexed_group": bundle.group_id, "documents": indexed["documents"]})
else:
    print("CAI MODE: trainer-owned indexing is already complete; participant query only.")

# %% [markdown]
# Build and print the exact native Qdrant filter. The `must` condition on `group_id` is mandatory for every search. Expect one JSON condition containing only the current group.

# %%
# Make the isolation filter visible before retrieval.
from bni_training.rag import group_filter_json

filter_json = group_filter_json(context.group_id)
assert filter_json == {"must": [{"key": "group_id", "match": {"value": context.group_id}}]}
print(json.dumps(filter_json, indent=2))

# %% [markdown]
# Embed the question on CPU and query the existing collection through `search_group`. That helper always supplies the filter and re-checks returned payloads. Expect only current-group hits.

# %%
# Retrieve bounded context with the mandatory group filter.
from bni_training.rag import search_group

retrieval_question = context.bundle.mission_title
hits = search_group(client, context.group_id, retrieval_question, embedder.embed, limit=3)
assert hits, "No group-scoped documents were found; ask the trainer to verify the shared index."
assert {hit["group_id"] for hit in hits} == {context.group_id}
formatted_context = "\n\n".join(f"{hit['title']}: {hit['text']}" for hit in hits)
print({"question": retrieval_question, "hit_groups": sorted({hit["group_id"] for hit in hits})})
print("Retrieved context:\n", formatted_context)

# %% [markdown]
# ## Hands-on exercise
# Change the retrieval question and result limit, keeping the group filter unchanged. The default retrieves the mission note with a small limit.

# %%
# EXERCISE: edit only the question and a limit from 1 through 5.
exercise_question = context.bundle.mission_title
exercise_limit = 2
exercise_hits = search_group(client, context.group_id, exercise_question, embedder.embed, limit=exercise_limit)
assert exercise_hits and {item["group_id"] for item in exercise_hits} == {context.group_id}
print({"exercise_limit": exercise_limit, "titles": [item["title"] for item in exercise_hits]})

# %% [markdown]
# Save only titles, scores, and group ids. This checkpoint contains no vector, credential, or endpoint.

# %%
# Persist a bounded, group-scoped retrieval checkpoint.
safe_hits = [{key: hit[key] for key in ("title", "group_id", "score")} for hit in exercise_hits]
saved = context.write_output("07_retrieval.json", json.dumps(safe_hits, indent=2))
print({"saved": saved.name})

# %% [markdown]
# ## Expected result
# The exact `group_id` filter is visible, retrieval returns only current-group payloads, and the lightweight embedding runs without a download or GPU.
#
# ## Common errors
# A missing collection or empty result means the trainer should verify pre-indexing. A missing `QDRANT_URL` fails in CAI; it never switches to local mode silently.
#
# ## Completion checkpoint
# Explain why indexing and querying must use the same embedder and why payload verification follows the Qdrant filter.
#
# ## Reference implementation
# `bni_training.rag` contains the deterministic adapter and enforced filter; `scripts/07_qdrant_rag.py` is the trainer/reference flow.
#
# ## Cleanup
# Close the client. Do not delete or recreate the shared collection.

# %%
# Close Qdrant and print one executor status line.
from bni_training.workshop.notebook_support import lab_status

client.close()
context.close()
lab_status("07", LAB_MODE, passed=6, skipped=2 if LAB_MODE == "local" else 0)
