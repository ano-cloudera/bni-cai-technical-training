import os

from bni_training.labs import isolate_crewai_storage


def test_each_group_and_process_gets_a_private_crewai_database_folder(monkeypatch, tmp_path):
    monkeypatch.delenv("CREWAI_STORAGE_DIR", raising=False)
    monkeypatch.setenv("GROUP_ID", "group_04")
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    folder = isolate_crewai_storage()
    assert "group_04" in folder and str(os.getpid()) in folder and folder == os.environ["CREWAI_STORAGE_DIR"]


def test_an_explicit_setting_is_kept(monkeypatch):
    monkeypatch.setenv("CREWAI_STORAGE_DIR", "chosen-by-trainer")
    assert isolate_crewai_storage() == "chosen-by-trainer"


def test_crewai_stores_its_database_in_that_folder(monkeypatch, tmp_path):
    from crewai_core.paths import db_storage_path

    monkeypatch.delenv("CREWAI_STORAGE_DIR", raising=False)
    monkeypatch.setenv("GROUP_ID", "group_04")
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path))
    isolate_crewai_storage()
    assert db_storage_path().startswith(str(tmp_path))
