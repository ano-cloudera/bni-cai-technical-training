import os

from bni_training.rag import build_group_filter


def main():
    group = os.getenv("GROUP_ID", "group_01")
    print(
        {
            "collection": "bni_training_knowledge",
            "embedding": "BAAI/bge-m3",
            "query_filter": build_group_filter(group),
        }
    )
    print("Run scripts/index_glossary.py with the same GROUP_ID before live retrieval.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
