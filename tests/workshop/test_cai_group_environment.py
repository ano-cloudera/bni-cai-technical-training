"""Generated group.env for CAI: complete, non-secret, loaded automatically by the Lab 03 notebook."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

nbformat = pytest.importorskip("nbformat")

from bni_training.mock_llm import MockOpenAIServer  # noqa: E402
from bni_training.workshop.notebook_support import load_group_env  # noqa: E402
from bni_training.workshop.workspace_manager import (  # noqa: E402
    GROUP_IDS,
    WorkspaceError,
    WorkspaceManager,
    parse_env,
)
from scripts.execute_notebooks import execute  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
URL = "https://vllm.example.invalid"


def cai_manager(tmp_path, **kwargs) -> WorkspaceManager:
    return WorkspaceManager(
        tmp_path / "runtime", lab_mode="cai", vllm_base_url=kwargs.pop("url", URL), **kwargs
    )


def test_every_group_env_has_the_complete_cai_configuration(tmp_path) -> None:
    manager = cai_manager(tmp_path)
    manager.sync(apply=True)
    for group_id in GROUP_IDS:
        env = parse_env((tmp_path / "runtime/groups" / group_id / "config/group.env").read_text())
        assert env["LAB_MODE"] == "cai" and env["GROUP_ID"] == group_id
        assert env["VLLM_BASE_URL"] == URL + "/v1" and env["VLLM_MODEL"] == "qwen3.5-9b"
        workspace = Path(env["GROUP_WORKSPACE"])
        assert workspace.is_absolute() and workspace == (tmp_path / "runtime/groups" / group_id).resolve()


def test_group_env_never_contains_a_key_token_password_or_secret(tmp_path) -> None:
    cai_manager(tmp_path).sync(apply=True)
    text = (tmp_path / "runtime/groups/group_01/config/group.env").read_text()
    entries = [line for line in text.splitlines() if line.strip() and not line.startswith("#")]
    for line in entries:
        name = line.split("=", 1)[0].upper()
        assert not any(word in name for word in ("KEY", "TOKEN", "PASSWORD", "SECRET", "BEARER", "AUTH")), (
            line
        )
    assert "bearer" not in text.lower() and "authorization" not in text.lower()
    assert cai_manager(tmp_path).validate().passed


def test_the_url_gets_one_v1_suffix_and_the_model_name_is_configurable(tmp_path) -> None:
    manager = cai_manager(tmp_path, url=URL + "/v1/", vllm_model="other-model")
    assert manager.vllm_base_url == URL + "/v1"
    assert "VLLM_MODEL=other-model" in manager.group_env_text("group_02")


def test_cai_mode_fails_clearly_without_the_url_or_with_credentials(tmp_path) -> None:
    for bad in (None, "", "   "):
        with pytest.raises(WorkspaceError, match="VLLM_BASE_URL"):
            WorkspaceManager(tmp_path / "r", lab_mode="cai", vllm_base_url=bad)
    for bad in ("ftp://host", "https://user:pw@host", "https://host/v1?token=abc", "not a url"):
        with pytest.raises(WorkspaceError, match="VLLM_BASE_URL"):
            WorkspaceManager(tmp_path / "r", lab_mode="cai", vllm_base_url=bad)


def test_local_mode_stays_explicit_and_writes_no_service_url(tmp_path) -> None:
    manager = WorkspaceManager(tmp_path / "runtime", vllm_base_url=URL)
    text = manager.group_env_text("group_01")
    assert "LAB_MODE=local" in text and "VLLM_BASE_URL" not in text and "VLLM_MODEL" not in text


def test_the_prepare_script_refuses_cai_mode_without_the_url(tmp_path, monkeypatch, capsys) -> None:
    from scripts.prepare_group_workspaces import main

    monkeypatch.delenv("VLLM_BASE_URL", raising=False)
    runtime = tmp_path / "r"
    assert main(["--runtime-dir", str(runtime), "--lab-mode", "cai", "--apply"]) == 2
    assert "VLLM_BASE_URL" in capsys.readouterr().err and not runtime.exists()
    assert main(["--runtime-dir", str(runtime), "--lab-mode", "cai", "--vllm-base-url", URL, "--apply"]) == 0
    assert (runtime / "groups/group_10/config/group.env").is_file()


def test_load_group_env_applies_values_without_overriding_or_loading_secrets(tmp_path) -> None:
    path = tmp_path / "group.env"
    path.write_text("LAB_MODE=cai\nGROUP_ID=group_05\nVLLM_API_KEY=oops\nSOME_TOKEN=oops\n# GROUP_X=1\n")
    env = {"GROUP_ID": "group_01"}
    applied = load_group_env(path, env)
    assert env == {"GROUP_ID": "group_01", "LAB_MODE": "cai"} and applied == {"LAB_MODE": "cai"}


def test_lab_03_runs_in_cai_mode_from_a_generated_workspace_without_manual_setup(
    tmp_path, monkeypatch
) -> None:
    for name in ("GROUP_ID", "GROUP_WORKSPACE", "GROUP_ENV_FILE", "LAB_MODE", "VLLM_BASE_URL", "VLLM_MODEL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("BNI_REPO_ROOT", raising=False)  # the workspace carries it in config/group.env
    monkeypatch.setenv("VLLM_API_KEY", "test-key-not-real")
    with (
        MockOpenAIServer() as shared_endpoint
    ):  # stands in for the shared Application; the notebook starts none
        base = shared_endpoint.base_url.removesuffix("/v1").replace("127.0.0.1", "localhost")
        manager = cai_manager(tmp_path, url=base)
        manager.sync(apply=True)
        notebook = tmp_path / "runtime/groups/group_03/notebooks/03_llm_api_testing.ipynb"
        result = execute(notebook, tmp_path / "executed", "cai", 600)
        assert result["result"] == "PASS" and result["lab_status"] == "PASS", result
        assert result["skipped"] == 0  # local mode would report its mock as SKIPPED
        requests = shared_endpoint.requests
    assert len(requests) >= 3, "raw, streamed and exercise calls reached the shared endpoint"
    assert all(r.get("chat_template_kwargs") == {"enable_thinking": False} for r in requests)
    saved = tmp_path / "runtime/groups/group_03/output/03_llm_api_result.json"
    assert saved.is_file() and "test-key-not-real" not in saved.read_text()
    assert os.environ.get("GROUP_ID") is None  # nothing leaked into the test process
