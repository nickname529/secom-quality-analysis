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
    assert threshold["selected_threshold"] == pytest.approx(0.06491104740935137)
    assert metrics["true_positive"] == 8
    assert metrics["false_negative"] == 9
    assert metrics["false_positive"] == 166
    assert metrics["fail_recall"] == pytest.approx(8 / 17)
    assert metrics["fail_precision"] == pytest.approx(8 / 174)


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

    assert len(code_cells) == 9
    assert all(cell.get("execution_count") is not None for cell in code_cells)
    assert error_outputs == []
    assert stderr_outputs == []
    assert [cell["id"] for cell in notebook["cells"]] == [
        f"cell-{index:02d}" for index in range(1, 24)
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
