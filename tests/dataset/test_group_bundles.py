from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from bni_training.data.bundles import SCENARIOS_DIR, BundleCatalog, BundleConfigError

EXPECTED = {
    "group_01": ("Customer Portfolio Summary", {"customers", "accounts"}),
    "group_02": ("Transaction Trend Analysis", {"transactions", "accounts"}),
    "group_03": ("Loan Portfolio Monitoring", {"loans", "customers", "accounts"}),
    "group_04": ("Branch Performance", {"branches", "accounts", "transactions", "loans"}),
    "group_05": ("Dormant Account Analysis", {"accounts", "customers"}),
    "group_06": ("Unusual Transaction Patterns", {"transactions", "accounts"}),
    "group_07": ("Customer Segmentation", {"customers", "accounts"}),
    "group_08": ("Product Adoption", {"accounts", "loans", "customers"}),
    "group_09": ("Regional Comparison", {"branches", "customers", "accounts", "transactions", "loans"}),
    "group_10": ("Management Summary", {"branches", "customers", "accounts", "transactions", "loans"}),
}


@pytest.fixture(scope="module")
def catalog() -> BundleCatalog:
    return BundleCatalog.load()


def test_each_group_gets_the_assigned_mission_and_logical_tables(catalog) -> None:
    assert set(catalog.bundles) == set(EXPECTED)
    for group_id, (title, tables) in EXPECTED.items():
        bundle = catalog.for_group(group_id)
        assert bundle.mission_title == title and set(bundle.tables) == tables, group_id
        assert bundle.mission_objective.strip() and bundle.dataset_id.endswith("_bundle")


def test_every_bundle_defines_all_required_fields(catalog) -> None:
    for bundle in catalog.bundles.values():
        assert bundle.dataset_id and bundle.mission_id and bundle.tables and bundle.allowed_metrics
        assert 3 <= len(bundle.sample_questions) <= 5
        assert isinstance(bundle.row_filters, dict)


def test_ten_distinct_bundles_and_missions_over_one_physical_dataset(catalog) -> None:
    assert len({b.dataset_id for b in catalog.bundles.values()}) == 10
    assert len({b.mission_id for b in catalog.bundles.values()}) == 10
    assert len({b.csv_dir for b in catalog.bundles.values()}) == 1, (
        "one physical directory serves every group"
    )
    csv_files = list(Path("data").rglob("*.csv"))
    assert not [p for p in csv_files if "group_" in str(p) or "bundle" in str(p)], (
        "no per-group copies of the data"
    )


def test_metrics_only_need_tables_inside_the_bundle(catalog, semantic) -> None:
    for bundle in catalog.bundles.values():
        for metric in bundle.allowed_metrics:
            assert semantic.metrics[metric].tables <= set(bundle.tables), (bundle.group_id, metric)


def test_the_management_summary_bundle_exposes_every_table_and_metric(catalog, semantic) -> None:
    bundle = catalog.for_group("group_10")
    assert set(bundle.allowed_metrics) == set(semantic.metrics)
    assert len(bundle.tables) == 5


def test_a_row_filter_exists_and_is_applied_by_the_branch_mission(catalog) -> None:
    assert catalog.for_group("group_04").row_filters == {"branches": "operational_status <> 'CLOSED'"}


def copy_config(tmp_path: Path) -> Path:
    target = tmp_path / "scenarios"
    shutil.copytree(SCENARIOS_DIR, target)
    return target


def edit(path: Path, change) -> None:
    data = yaml.safe_load(path.read_text())
    change(data)
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def test_a_metric_that_needs_a_table_outside_the_bundle_is_a_configuration_error(tmp_path) -> None:
    directory = copy_config(tmp_path)
    edit(
        directory / "dataset_bundles.yaml",
        lambda d: d["bundles"]["customer_portfolio_bundle"]["allowed_metrics"].append("total_loans"),
    )
    with pytest.raises(BundleConfigError, match="needs tables"):
        BundleCatalog.load(directory)


def test_too_few_sample_questions_are_rejected(tmp_path) -> None:
    directory = copy_config(tmp_path)
    edit(
        directory / "sample_questions.yaml",
        lambda d: d["missions"].__setitem__("customer_portfolio_summary", ["Show total customers"]),
    )
    with pytest.raises(BundleConfigError, match="three to five"):
        BundleCatalog.load(directory)


def test_a_bundle_shared_by_two_groups_is_rejected(tmp_path) -> None:
    directory = copy_config(tmp_path)
    edit(
        directory / "group_assignments.yaml",
        lambda d: d["assignments"][1].__setitem__("dataset_id", "customer_portfolio_bundle"),
    )
    with pytest.raises(BundleConfigError, match="more than one group"):
        BundleCatalog.load(directory)


def test_a_row_filter_on_a_hidden_column_is_rejected(tmp_path) -> None:
    directory = copy_config(tmp_path)
    edit(
        directory / "dataset_bundles.yaml",
        lambda d: d["bundles"]["unusual_patterns_bundle"].__setitem__(
            "row_filters", {"transactions": "is_seeded_anomaly = 0"}
        ),
    )
    with pytest.raises(BundleConfigError, match="unavailable columns"):
        BundleCatalog.load(directory)


def test_a_sample_question_that_does_not_fit_the_bundle_is_rejected(tmp_path) -> None:
    directory = copy_config(tmp_path)
    edit(
        directory / "sample_questions.yaml",
        lambda d: d["missions"].__setitem__(
            "customer_portfolio_summary", ["Show total loans", "Show total customers", "Show total balance"]
        ),
    )
    with pytest.raises(ValueError):
        BundleCatalog.load(directory)
