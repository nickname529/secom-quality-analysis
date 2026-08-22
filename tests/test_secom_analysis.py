from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import unquote

import numpy as np
import pandas as pd
import pytest
from sklearn.model_selection import train_test_split

import download_data
import secom_analysis as analysis


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = PROJECT_ROOT / "results"


@pytest.fixture(scope="module")
def loaded_data() -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    return analysis.load_secom(PROJECT_ROOT / "data" / "raw")


def test_official_raw_shape_labels_and_missingness(loaded_data) -> None:
    features, target, metadata = loaded_data

    assert features.shape == (1567, 590)
    assert target.value_counts().sort_index().to_dict() == {0: 1463, 1: 104}
    assert int(features.isna().sum().sum()) == 41_951
    assert int(np.isinf(features.to_numpy()).sum()) == 0
    assert metadata["source_label"].value_counts().sort_index().to_dict() == {
        -1: 1463,
        1: 104,
    }
    assert not features.duplicated().any()


def test_raw_files_match_pinned_source_hashes() -> None:
    manifest = json.loads(
        (PROJECT_ROOT / "data" / "raw" / "source_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    for name, expected in download_data.EXPECTED_SHA256.items():
        path = PROJECT_ROOT / "data" / "raw" / name
        assert download_data.sha256(path) == expected
        assert manifest["files"][name]["expected_sha256"] == expected
        assert manifest["files"][name]["matches_expected"] is True


def test_split_assignment_matches_fixed_stratified_split(loaded_data) -> None:
    features, target, _ = loaded_data
    expected_train, expected_test = train_test_split(
        features.index,
        test_size=analysis.TEST_SIZE,
        random_state=analysis.SEED,
        stratify=target,
    )
    assignment = pd.read_csv(RESULTS_DIR / "tables" / "split_assignment.csv")
    actual_test = assignment.index[assignment["split"] == "test"].to_numpy()
    actual_train = assignment.index[assignment["split"] == "train"].to_numpy()

    assert set(actual_test) == set(expected_test)
    assert set(actual_train) == set(expected_train)
    assert len(set(actual_train) & set(actual_test)) == 0
    assert int(target.loc[actual_train].sum()) == 83
    assert int(target.loc[actual_test].sum()) == 21
    assert "timestamp" not in features.columns


def test_binary_metrics_uses_fail_as_positive_and_correct_matrix_order() -> None:
    target = np.array([0, 0, 1, 1])
    scores = np.array([0.1, 0.9, 0.2, 0.8])
    metrics = analysis.binary_metrics(target, scores, threshold=0.5)

    assert metrics["true_negative"] == 1
    assert metrics["false_positive"] == 1
    assert metrics["false_negative"] == 1
    assert metrics["true_positive"] == 1
    assert metrics["fail_recall"] == pytest.approx(0.5)
    assert metrics["fail_precision"] == pytest.approx(0.5)
    assert metrics["fail_f1"] == pytest.approx(0.5)
    assert metrics["balanced_accuracy"] == pytest.approx(0.5)


def test_saved_test_metrics_recompute_from_predictions() -> None:
    predictions = pd.read_csv(RESULTS_DIR / "tables" / "test_predictions.csv")
    metrics_table = pd.read_csv(RESULTS_DIR / "tables" / "test_metrics.csv")
    target = predictions["label"].map({"PASS": 0, "FAIL": 1}).to_numpy()

    for record in metrics_table.to_dict("records"):
        model = record["model"]
        scores = predictions[f"{model}_score"].to_numpy()
        recomputed = analysis.binary_metrics(target, scores, record["threshold"])
        for key in [
            "true_negative",
            "false_positive",
            "false_negative",
            "true_positive",
        ]:
            assert recomputed[key] == record[key]
        for key in [
            "fail_recall",
            "fail_precision",
            "fail_f1",
            "balanced_accuracy",
            "roc_auc",
            "average_precision",
            "pr_auc_trapezoid",
        ]:
            assert recomputed[key] == pytest.approx(record[key], abs=1e-12)


def test_quality_threshold_and_false_negative_artifacts_are_consistent() -> None:
    threshold = json.loads(
        (RESULTS_DIR / "metadata" / "threshold_selection.json").read_text(
            encoding="utf-8"
        )
    )
    false_negatives = pd.read_csv(RESULTS_DIR / "tables" / "false_negatives.csv")
    quality_row = pd.read_csv(RESULTS_DIR / "tables" / "test_metrics.csv").iloc[-1]

    assert threshold["test_data_used_to_select_threshold"] is False
    assert threshold["recall_target_assumption"] == pytest.approx(0.80)
    assert threshold["selected_model"] == "random_forest_balanced"
    assert quality_row["true_positive"] == 17
    assert quality_row["false_negative"] == 4
    assert quality_row["fail_recall"] == pytest.approx(17 / 21)
    assert len(false_negatives) == 4
    assert set(false_negatives["detection_outcome"]) == {"FALSE_NEGATIVE"}
    assert (
        false_negatives["random_forest_balanced_score"]
        < threshold["selected_threshold"]
    ).all()


def test_preprocessing_is_inside_each_model_pipeline() -> None:
    models = analysis.make_models()
    for model in models.values():
        step_names = list(model.named_steps)
        assert step_names[:2] == ["imputer", "drop_constant"]
        assert step_names[-1] == "classifier"
        assert model.named_steps["imputer"].strategy == "median"


def test_feature_candidates_remain_anonymous() -> None:
    candidates = pd.read_csv(RESULTS_DIR / "tables" / "feature_candidates.csv")
    assert candidates["feature"].str.fullmatch(r"feature_\d{3}").all()
    assert candidates.iloc[0]["feature"] == "feature_059"
    assert bool(candidates.iloc[0]["meets_both_methods_60pct_rule"])


def test_temporal_threshold_is_train_only_and_records_generalization_drop() -> None:
    temporal = json.loads(
        (RESULTS_DIR / "metadata" / "temporal_sensitivity.json").read_text(
            encoding="utf-8"
        )
    )
    threshold = temporal["train_only_threshold_selection"]
    metrics = temporal["metrics_at_train_only_quality_threshold"]

    assert threshold["test_data_used_to_select_threshold"] is False
    assert temporal["train_time_max"] == "2008-10-02T19:25:00"
    assert temporal["test_time_min"] == "2008-10-02T20:54:00"
    assert threshold["selected_threshold"] == pytest.approx(0.06823468043947259)
    assert metrics["true_negative"] == 171
    assert metrics["true_positive"] == 7
    assert metrics["false_negative"] == 10
    assert metrics["false_positive"] == 126
    assert metrics["fail_recall"] == pytest.approx(7 / 17)
    assert metrics["fail_precision"] == pytest.approx(7 / 133)


def test_ap_and_trapezoidal_pr_auc_are_stored_separately() -> None:
    metrics = pd.read_csv(RESULTS_DIR / "tables" / "test_metrics.csv")
    dummy = metrics.loc[metrics["evaluation"] == "dummy_prior"].iloc[0]
    forest = metrics.loc[metrics["evaluation"] == "random_forest_balanced"].iloc[0]

    assert dummy["average_precision"] == pytest.approx(21 / 314)
    assert dummy["pr_auc_trapezoid"] > 0.5
    assert forest["average_precision"] == pytest.approx(0.22869676291471513)
    assert forest["pr_auc_trapezoid"] == pytest.approx(0.2072722579400118)


def test_shared_timestamp_groups_are_explicitly_audited() -> None:
    split = json.loads(
        (RESULTS_DIR / "metadata" / "split_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert split["shared_timestamp_groups_across_train_test"] == 11
    assert split["rows_in_shared_timestamp_groups"] == 22
    assert split["timestamp_used_as_model_feature"] is False


def test_locked_test_bootstrap_uncertainty_is_reproducible() -> None:
    intervals = pd.read_csv(
        RESULTS_DIR / "tables" / "test_metric_bootstrap_ci.csv"
    ).set_index("metric")
    metadata = json.loads(
        (RESULTS_DIR / "metadata" / "test_metric_uncertainty.json").read_text(
            encoding="utf-8"
        )
    )

    assert metadata["method"].startswith("True-label-stratified")
    assert metadata["seed"] == analysis.BOOTSTRAP_SEED
    assert metadata["valid_replicates"] == 10_000
    assert metadata["model_refit_in_bootstrap"] is False
    assert metadata["threshold_reselected_in_bootstrap"] is False
    assert intervals.loc["fail_recall", "point_estimate"] == pytest.approx(17 / 21)
    assert intervals.loc["fail_recall", "ci_low"] == pytest.approx(13 / 21)
    assert intervals.loc["fail_recall", "ci_high"] == pytest.approx(20 / 21)
    assert intervals.loc["fail_precision", "ci_low"] == pytest.approx(
        0.0817577974586061
    )
    assert intervals.loc["average_precision", "ci_high"] == pytest.approx(
        0.42665343689371255
    )


def test_bootstrap_caution_uses_the_actual_observed_prevalence() -> None:
    _, metadata = analysis.bootstrap_metric_intervals(
        target=np.array([0, 0, 1, 1]),
        scores=np.array([0.1, 0.4, 0.6, 0.9]),
        threshold=0.5,
        n_bootstrap=20,
        seed=1,
    )

    assert metadata["test_rows"] == 4
    assert metadata["test_fail_count"] == 2
    assert "observed 2/4 FAIL prevalence" in metadata["caution"]


def test_temporal_feature_stability_uses_only_strict_development_pool() -> None:
    metadata = json.loads(
        (RESULTS_DIR / "metadata" / "temporal_feature_stability.json").read_text(
            encoding="utf-8"
        )
    )
    logistic_details = pd.read_csv(
        RESULTS_DIR / "tables" / "temporal_logistic_feature_stability_by_fold.csv"
    )
    logistic_summary = pd.read_csv(
        RESULTS_DIR / "tables" / "temporal_logistic_feature_stability_summary.csv"
    )
    forest_details = pd.read_csv(
        RESULTS_DIR / "tables" / "temporal_rf_permutation_stability_by_fold.csv"
    )
    forest_summary = pd.read_csv(
        RESULTS_DIR / "tables" / "temporal_rf_permutation_stability_summary.csv"
    )
    candidates = pd.read_csv(
        RESULTS_DIR / "tables" / "temporal_feature_candidates.csv"
    )

    assert metadata["strict_development_pool_rows"] == 1_003
    assert metadata["strict_development_pool_fail_count"] == 67
    assert metadata["strict_development_unique_timestamps"] == 987
    assert metadata["rows_excluded_for_protected_timestamp_overlap"] == 7
    assert metadata["primary_test_row_overlap_after_filter"] == 0
    assert metadata["chronological_holdout_row_overlap_after_filter"] == 0
    assert metadata["protected_timestamp_overlap_after_filter"] == 0
    assert metadata["primary_test_used"] is False
    assert metadata["chronological_holdout_used"] is False
    assert all(fold["strict_time_order"] for fold in metadata["folds"])
    assert all(fold["shared_timestamp_count"] == 0 for fold in metadata["folds"])
    assert [
        (
            fold["train_rows"],
            fold["train_fail_count"],
            fold["valid_rows"],
            fold["valid_fail_count"],
        )
        for fold in metadata["folds"]
    ] == [(250, 34, 253, 15), (503, 49, 252, 9), (755, 58, 248, 9)]

    assert logistic_details.shape[0] == 590 * 3
    assert forest_details.shape[0] == 590 * 3
    assert logistic_summary.shape[0] == 590
    assert forest_summary.shape[0] == 590
    assert np.allclose(
        logistic_summary["top_k_frequency"],
        logistic_summary["top_k_count"] / 3,
    )
    assert np.allclose(
        forest_summary["positive_top_k_frequency"],
        forest_summary["positive_top_k_count"] / 3,
    )
    forest_top = forest_details[forest_details["in_positive_top_k"]]
    assert (forest_top["ap_permutation_importance_mean"] > 0).all()
    assert (forest_top.groupby("fold").size() <= 20).all()
    assert candidates["meets_both_methods_2_of_3"].sum() == 0
    feature_059 = candidates.loc[candidates["feature"] == "feature_059"].iloc[0]
    assert feature_059["logistic_top20_count"] == 1
    assert feature_059["rf_positive_top20_count"] == 1


def test_shared_timestamp_sensitivity_does_not_overstate_group_control() -> None:
    sensitivity = json.loads(
        (RESULTS_DIR / "metadata" / "shared_timestamp_sensitivity.json").read_text(
            encoding="utf-8"
        )
    )
    nonshared = sensitivity[
        "primary_model_on_nonshared_test_at_primary_threshold"
    ]
    shared_outcomes = sensitivity["shared_test_outcomes_at_primary_threshold"]

    assert sensitivity["shared_timestamp_group_count"] == 11
    assert sensitivity["removed_train_rows"] == 11
    assert sensitivity["removed_test_rows"] == 11
    assert sensitivity["removed_train_fail_count"] == 0
    assert sensitivity["removed_test_fail_count"] == 0
    assert shared_outcomes == {
        "pass_count": 11,
        "fail_count": 0,
        "true_negative": 5,
        "false_positive": 6,
        "false_negative": 0,
        "true_positive": 0,
    }
    assert nonshared["true_negative"] == 143
    assert nonshared["false_positive"] == 139
    assert nonshared["false_negative"] == 4
    assert nonshared["true_positive"] == 17
    assert nonshared["fail_recall"] == pytest.approx(17 / 21)
    assert sensitivity["primary_model_or_threshold_changed"] is False
    purged_threshold = sensitivity["purged_train_only_threshold_selection"]
    assert purged_threshold["test_labels_used_to_select_threshold"] is False
    assert purged_threshold["test_feature_values_used_to_select_threshold"] is False
    assert purged_threshold["test_timestamp_metadata_used_for_group_purge"] is True


def test_portfolio_notebook_is_fully_executed_without_errors() -> None:
    notebook_path = PROJECT_ROOT / "notebooks" / "secom_quality_analysis.ipynb"
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    code_cells = [
        cell for cell in notebook["cells"] if cell.get("cell_type") == "code"
    ]
    error_outputs = [
        output
        for cell in code_cells
        for output in cell.get("outputs", [])
        if output.get("output_type") == "error"
    ]
    stderr_outputs = [
        output
        for cell in code_cells
        for output in cell.get("outputs", [])
        if output.get("output_type") == "stream" and output.get("name") == "stderr"
    ]

    assert len(code_cells) == 12
    assert all(cell.get("execution_count") is not None for cell in code_cells)
    assert error_outputs == []
    assert stderr_outputs == []
    assert [cell["id"] for cell in notebook["cells"]] == [
        f"cell-{index:02d}" for index in range(1, 30)
    ]
    serialized = json.dumps(notebook)
    assert "/Users/" not in serialized
    assert "Documents/Codex" not in serialized


def test_all_local_markdown_links_resolve() -> None:
    missing: list[str] = []
    for markdown_path in PROJECT_ROOT.rglob("*.md"):
        content = markdown_path.read_text(encoding="utf-8")
        for raw_target in re.findall(r"!?(?:\[[^\]]*\])\(([^)]+)\)", content):
            target = raw_target.strip().split("#", maxsplit=1)[0]
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            resolved = (markdown_path.parent / unquote(target)).resolve()
            if not resolved.exists():
                missing.append(f"{markdown_path.relative_to(PROJECT_ROOT)} -> {target}")

    assert missing == []
