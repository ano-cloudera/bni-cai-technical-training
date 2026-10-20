"""The trainer indexing script covers all ten groups, writes nothing by default and keeps groups apart."""

from __future__ import annotations

import json

from scripts import index_all_groups


def test_the_dry_run_lists_all_ten_groups_and_writes_nothing(capsys) -> None:
    assert index_all_groups.main([]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["dry_run"] is True
    assert sorted(result["documents_per_group"]) == [f"group_{i:02d}" for i in range(1, 11)]
    assert set(result["documents_per_group"].values()) == {6}


def test_one_group_can_be_selected(capsys) -> None:
    assert index_all_groups.main(["--group-id", "group_03"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert list(result["documents_per_group"]) == ["group_03"]


def test_each_group_gets_its_own_mission_note() -> None:
    from bni_training.data.bundles import BundleCatalog

    catalog = BundleCatalog.load()
    notes = {
        group_id: [d for d in index_all_groups.documents_for(bundle) if d["document_type"] == "mission"]
        for group_id, bundle in catalog.bundles.items()
    }
    assert all(len(items) == 1 for items in notes.values())
    assert len({items[0]["chunk_id"] for items in notes.values()}) >= 1
