#!/usr/bin/env python3
"""Reproducible, leakage-aware baseline analysis for the UCI SECOM dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import warnings
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import joblib
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
import seaborn as sns
import sklearn
from sklearn.base import clone
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import VarianceThreshold
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    make_scorer,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import (
    RepeatedStratifiedKFold,
    StratifiedKFold,
    cross_val_predict,
    cross_validate,
    train_test_split,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


SEED = 42
TEST_SIZE = 0.20
CV_SPLITS = 5
CV_REPEATS = 3
QUALITY_RECALL_TARGET = 0.80
TOP_K = 20

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_RESULTS_DIR = PROJECT_ROOT / "results"
DEFAULT_FIGURES_DIR = PROJECT_ROOT / "figures"
DEFAULT_MODELS_DIR = PROJECT_ROOT / "models"

LABEL_NAMES = {0: "PASS", 1: "FAIL"}
MODEL_LABELS = {
    "dummy_prior": "Dummy (prior)",
    "logistic_balanced": "Logistic Regression",
    "random_forest_balanced": "Random Forest",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def to_builtin(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): to_builtin(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_builtin(item) for item in value]
    if isinstance(value, np.ndarray):
        return [to_builtin(item) for item in value.tolist()]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        numeric = float(value)
        return numeric if math.isfinite(numeric) else None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(to_builtin(payload), ensure_ascii=False, indent=2, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def validate_raw_files(data_dir: Path) -> None:
    required = ["secom.data", "secom_labels.data", "secom.names"]
    missing = [name for name in required if not (data_dir / name).exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing raw files: {missing}. Run scripts/download_data.py first."
        )

    manifest_path = data_dir / "source_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError("source_manifest.json is required for hash verification")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for name in required:
        expected = manifest.get("files", {}).get(name, {}).get("sha256")
        if not expected:
            raise RuntimeError(f"No SHA-256 recorded for {name}")
        actual = sha256(data_dir / name)
        if actual != expected:
            raise RuntimeError(
                f"SHA-256 mismatch for {name}: expected {expected}, got {actual}"
            )


def load_secom(data_dir: Path) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    validate_raw_files(data_dir)

    features = pd.read_csv(
        data_dir / "secom.data",
        sep=r"\s+",
        header=None,
        na_values=["NaN"],
        dtype=float,
    )
    features.columns = [f"feature_{index:03d}" for index in range(features.shape[1])]

    labels = pd.read_csv(
        data_dir / "secom_labels.data",
        sep=" ",
        skipinitialspace=True,
        header=None,
        names=["source_label", "timestamp"],
        quotechar='"',
    )
    labels["timestamp"] = pd.to_datetime(
        labels["timestamp"],
        format="%d/%m/%Y %H:%M:%S",
        errors="raise",
    )

    if len(features) != len(labels):
        raise ValueError(
            f"Feature/label row mismatch: {len(features)} != {len(labels)}"
        )
    unique_labels = set(labels["source_label"].astype(int).unique())
    if unique_labels != {-1, 1}:
        raise ValueError(f"Expected labels {{-1, 1}}, found {unique_labels}")

    target = labels["source_label"].astype(int).map({-1: 0, 1: 1})
    target.name = "is_fail"
    metadata = pd.DataFrame(
        {
            "sample_id": [f"sample_{index:04d}" for index in range(len(features))],
            "timestamp": labels["timestamp"],
            "source_label": labels["source_label"].astype(int),
            "label": target.map(LABEL_NAMES),
        },
        index=features.index,
    )
    return features, target, metadata


def audit_dataset(
    features: pd.DataFrame,
    target: pd.Series,
    metadata: pd.DataFrame,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    missing_count = features.isna().sum()
    observed_count = features.notna().sum()
    observed_unique = features.nunique(dropna=True)
    variances = features.var(skipna=True, ddof=0)

    feature_quality = pd.DataFrame(
        {
            "feature": features.columns,
            "missing_count": missing_count.values,
            "missing_pct": (missing_count / len(features)).values,
            "observed_count": observed_count.values,
            "observed_unique": observed_unique.values,
            "all_missing": (observed_count == 0).values,
            "observed_constant": (observed_unique <= 1).values,
            "observed_variance": variances.values,
        }
    ).sort_values(["missing_pct", "feature"], ascending=[False, True])

    row_missing = features.isna().sum(axis=1)
    row_quality = metadata[["sample_id", "timestamp", "label"]].copy()
    row_quality["missing_count"] = row_missing
    row_quality["missing_pct"] = row_missing / features.shape[1]

    feature_hash = pd.util.hash_pandas_object(features, index=False)
    hash_audit = pd.DataFrame({"feature_hash": feature_hash, "is_fail": target})
    hash_groups = hash_audit.groupby("feature_hash").agg(
        group_size=("is_fail", "size"),
        label_count=("is_fail", "nunique"),
    )
    duplicate_groups = hash_groups[hash_groups["group_size"] > 1]

    label_counts = target.value_counts().sort_index()
    total_cells = int(features.shape[0] * features.shape[1])
    missing_cells = int(features.isna().sum().sum())
    summary = {
        "rows": int(features.shape[0]),
        "input_features_actual": int(features.shape[1]),
        "uci_metadata_feature_count": 591,
        "metadata_count_discrepancy_note": (
            "UCI metadata reports 591 features, while every official secom.data "
            "row contains 590 values. This project uses the raw file structure."
        ),
        "label_mapping": {"-1": "PASS (0)", "1": "FAIL (1)"},
        "pass_count": int(label_counts.get(0, 0)),
        "fail_count": int(label_counts.get(1, 0)),
        "pass_pct": float((target == 0).mean()),
        "fail_pct": float((target == 1).mean()),
        "pass_to_fail_ratio": float((target == 0).sum() / (target == 1).sum()),
        "total_feature_cells": total_cells,
        "missing_cells": missing_cells,
        "missing_cell_pct": float(missing_cells / total_cells),
        "features_with_missing": int((missing_count > 0).sum()),
        "all_missing_features_full_data": int((observed_count == 0).sum()),
        "observed_constant_features_full_data": int((observed_unique <= 1).sum()),
        "infinite_values": int(np.isinf(features.to_numpy()).sum()),
        "duplicate_feature_rows": int(features.duplicated(keep=False).sum()),
        "duplicate_feature_groups": int(len(duplicate_groups)),
        "duplicate_groups_with_conflicting_labels": int(
            (duplicate_groups["label_count"] > 1).sum()
        ),
        "duplicate_timestamps": int(metadata["timestamp"].duplicated(keep=False).sum()),
        "timestamp_min": metadata["timestamp"].min(),
        "timestamp_max": metadata["timestamp"].max(),
        "row_missing_count_median": float(row_missing.median()),
        "row_missing_count_p95": float(row_missing.quantile(0.95)),
        "row_missing_count_max": int(row_missing.max()),
    }
    return summary, feature_quality, row_quality


def make_models(seed: int = SEED) -> dict[str, Pipeline]:
    common_steps = [
        (
            "imputer",
            SimpleImputer(strategy="median", keep_empty_features=True),
        ),
        ("drop_constant", VarianceThreshold(threshold=0.0)),
    ]

    return {
        "dummy_prior": Pipeline(
            [
                *common_steps,
                ("classifier", DummyClassifier(strategy="prior")),
            ]
        ),
        "logistic_balanced": Pipeline(
            [
                *common_steps,
                ("scaler", StandardScaler()),
                (
                    "classifier",
                    LogisticRegression(
                        C=1.0,
                        class_weight="balanced",
                        max_iter=5000,
                        random_state=seed,
                        solver="liblinear",
                    ),
                ),
            ]
        ),
        "random_forest_balanced": Pipeline(
            [
                *common_steps,
                (
                    "classifier",
                    RandomForestClassifier(
                        n_estimators=400,
                        min_samples_leaf=2,
                        max_features="sqrt",
                        class_weight="balanced_subsample",
                        random_state=seed,
                        n_jobs=1,
                    ),
                ),
            ]
        ),
    }


def positive_scores(estimator: Pipeline, features: pd.DataFrame) -> np.ndarray:
    probabilities = estimator.predict_proba(features)
    classes = list(estimator.classes_)
    if 1 not in classes:
        raise ValueError(f"FAIL class 1 missing from estimator classes: {classes}")
    return probabilities[:, classes.index(1)]


def positive_oof_scores(
    probabilities: np.ndarray,
    target: pd.Series | np.ndarray,
) -> np.ndarray:
    classes = list(np.unique(np.asarray(target, dtype=int)))
    if 1 not in classes:
        raise ValueError(f"FAIL class 1 missing from OOF target classes: {classes}")
    return probabilities[:, classes.index(1)]


def wilson_interval(successes: int, trials: int, z: float = 1.96) -> tuple[float, float]:
    if trials == 0:
        return (float("nan"), float("nan"))
    proportion = successes / trials
    denominator = 1 + (z**2 / trials)
    center = (proportion + (z**2 / (2 * trials))) / denominator
    margin = (
        z
        * math.sqrt(
            (proportion * (1 - proportion) / trials)
            + (z**2 / (4 * trials**2))
        )
        / denominator
    )
    return center - margin, center + margin


def trapezoidal_pr_auc(
    target: pd.Series | np.ndarray,
    scores: np.ndarray,
) -> float:
    """Compute trapezoidal area under the precision-recall curve.

    This is reported separately from Average Precision because the two summaries
    use different interpolation conventions.
    """

    precision, recall, _ = precision_recall_curve(target, scores)
    return float(np.trapezoid(precision[::-1], recall[::-1]))


def binary_metrics(
    target: pd.Series | np.ndarray,
    scores: np.ndarray,
    threshold: float,
) -> dict[str, Any]:
    target_array = np.asarray(target, dtype=int)
    predictions = (np.asarray(scores) >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(
        target_array, predictions, labels=[0, 1]
    ).ravel()
    recall_low, recall_high = wilson_interval(int(tp), int(tp + fn))
    precision_low, precision_high = wilson_interval(int(tp), int(tp + fp))

    return {
        "threshold": float(threshold),
        "accuracy": float(accuracy_score(target_array, predictions)),
        "balanced_accuracy": float(
            balanced_accuracy_score(target_array, predictions)
        ),
        "fail_precision": float(
            precision_score(target_array, predictions, pos_label=1, zero_division=0)
        ),
        "fail_recall": float(
            recall_score(target_array, predictions, pos_label=1, zero_division=0)
        ),
        "fail_f1": float(
            f1_score(target_array, predictions, pos_label=1, zero_division=0)
        ),
        "roc_auc": float(roc_auc_score(target_array, scores)),
        "average_precision": float(average_precision_score(target_array, scores)),
        "pr_auc_trapezoid": trapezoidal_pr_auc(target_array, scores),
        "fail_prevalence": float(target_array.mean()),
        "true_negative": int(tn),
        "false_positive": int(fp),
        "false_negative": int(fn),
        "true_positive": int(tp),
        "fail_recall_wilson_low": recall_low,
        "fail_recall_wilson_high": recall_high,
        "fail_precision_wilson_low": precision_low,
        "fail_precision_wilson_high": precision_high,
    }


def evaluate_cv(
    models: Mapping[str, Pipeline],
    features_train: pd.DataFrame,
    target_train: pd.Series,
    cv_splits: list[tuple[np.ndarray, np.ndarray]],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, dict[str, np.ndarray]]]:
    scoring = {
        "fail_recall": make_scorer(recall_score, pos_label=1, zero_division=0),
        "fail_precision": make_scorer(
            precision_score, pos_label=1, zero_division=0
        ),
        "fail_f1": make_scorer(f1_score, pos_label=1, zero_division=0),
        "balanced_accuracy": "balanced_accuracy",
        "roc_auc": "roc_auc",
        "average_precision": "average_precision",
        "pr_auc_trapezoid": make_scorer(
            trapezoidal_pr_auc,
            response_method="predict_proba",
        ),
    }
    raw_scores: dict[str, dict[str, np.ndarray]] = {}
    fold_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []

    for model_name, model in models.items():
        scores = cross_validate(
            model,
            features_train,
            target_train,
            cv=cv_splits,
            scoring=scoring,
            n_jobs=1,
            return_train_score=False,
            error_score="raise",
        )
        raw_scores[model_name] = scores
        for metric in scoring:
            values = np.asarray(scores[f"test_{metric}"])
            for fold_index, value in enumerate(values, start=1):
                fold_rows.append(
                    {
                        "model": model_name,
                        "model_label": MODEL_LABELS[model_name],
                        "metric": metric,
                        "fold": fold_index,
                        "value": float(value),
                    }
                )
            summary_rows.append(
                {
                    "model": model_name,
                    "model_label": MODEL_LABELS[model_name],
                    "metric": metric,
                    "mean": float(values.mean()),
                    "std": float(values.std(ddof=1)),
                    "min": float(values.min()),
                    "max": float(values.max()),
                    "n_folds": int(len(values)),
                }
            )

    return pd.DataFrame(fold_rows), pd.DataFrame(summary_rows), raw_scores


def select_model_from_cv(
    raw_cv_scores: Mapping[str, Mapping[str, np.ndarray]],
) -> tuple[str, list[dict[str, Any]]]:
    eligible = ["logistic_balanced", "random_forest_balanced"]
    ranking = []
    for model_name in eligible:
        ranking.append(
            {
                "model": model_name,
                "cv_average_precision_mean": float(
                    np.mean(raw_cv_scores[model_name]["test_average_precision"])
                ),
                "cv_fail_recall_mean": float(
                    np.mean(raw_cv_scores[model_name]["test_fail_recall"])
                ),
            }
        )
    ranking.sort(
        key=lambda row: (
            row["cv_average_precision_mean"],
            row["cv_fail_recall_mean"],
        ),
        reverse=True,
    )
    return ranking[0]["model"], ranking


def select_quality_threshold(
    target: pd.Series,
    scores: np.ndarray,
    recall_target: float,
) -> tuple[float, dict[str, Any]]:
    precision, recall, thresholds = precision_recall_curve(target, scores)
    eligible = np.flatnonzero(recall[:-1] >= recall_target)
    if len(eligible) == 0:
        raise RuntimeError(f"No OOF threshold reaches recall target {recall_target}")

    eligible_precision = precision[:-1][eligible]
    max_precision = eligible_precision.max()
    precision_ties = eligible[
        np.isclose(eligible_precision, max_precision, rtol=1e-12, atol=1e-12)
    ]
    chosen_index = precision_ties[np.argmax(thresholds[precision_ties])]
    chosen_threshold = float(thresholds[chosen_index])
    details = {
        "rule": (
            "Among train-only OOF thresholds with FAIL recall >= target, choose "
            "the highest-precision threshold; break ties with the higher threshold."
        ),
        "recall_target_assumption": float(recall_target),
        "selected_threshold": chosen_threshold,
        "oof_precision_at_threshold": float(precision[chosen_index]),
        "oof_recall_at_threshold": float(recall[chosen_index]),
        "candidate_threshold_count": int(len(eligible)),
        "not_an_operational_optimum": True,
    }
    return chosen_threshold, details


def retained_feature_names(estimator: Pipeline, columns: Iterable[str]) -> np.ndarray:
    names = np.asarray(list(columns), dtype=object)
    support = estimator.named_steps["drop_constant"].get_support()
    return names[support]


def logistic_feature_stability(
    model: Pipeline,
    features_train: pd.DataFrame,
    target_train: pd.Series,
    cv_splits: list[tuple[np.ndarray, np.ndarray]],
    top_k: int = TOP_K,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    detail_rows: list[dict[str, Any]] = []
    all_features = list(features_train.columns)

    for fold_number, (train_indices, valid_indices) in enumerate(cv_splits, start=1):
        del valid_indices
        fitted = clone(model).fit(
            features_train.iloc[train_indices], target_train.iloc[train_indices]
        )
        retained = retained_feature_names(fitted, all_features)
        coefficients = fitted.named_steps["classifier"].coef_[0]
        coefficient_map = dict(zip(retained, coefficients, strict=True))
        top_features = set(
            retained[np.argsort(np.abs(coefficients))[::-1][:top_k]].tolist()
        )

        for feature in all_features:
            coefficient = coefficient_map.get(feature, float("nan"))
            detail_rows.append(
                {
                    "fold": fold_number,
                    "feature": feature,
                    "retained": feature in coefficient_map,
                    "standardized_coefficient": coefficient,
                    "absolute_coefficient": abs(coefficient),
                    "in_top_k": feature in top_features,
                }
            )

    details = pd.DataFrame(detail_rows)
    total_folds = details["fold"].nunique()

    def sign_consistency(series: pd.Series) -> float:
        observed = series.dropna()
        if observed.empty:
            return float("nan")
        positive_fraction = float((observed > 0).mean())
        return max(positive_fraction, 1 - positive_fraction)

    summary = (
        details.groupby("feature", as_index=False)
        .agg(
            folds_retained=("retained", "sum"),
            top_k_count=("in_top_k", "sum"),
            mean_standardized_coefficient=("standardized_coefficient", "mean"),
            mean_absolute_coefficient=("absolute_coefficient", "mean"),
            coefficient_std=("standardized_coefficient", "std"),
            positive_sign_fraction=(
                "standardized_coefficient",
                lambda values: float((values.dropna() > 0).mean())
                if not values.dropna().empty
                else float("nan"),
            ),
            sign_consistency=("standardized_coefficient", sign_consistency),
        )
        .assign(
            retained_frequency=lambda frame: frame["folds_retained"] / total_folds,
            top_k_frequency=lambda frame: frame["top_k_count"] / total_folds,
        )
        .sort_values(
            ["top_k_frequency", "mean_absolute_coefficient"],
            ascending=[False, False],
        )
    )
    return details, summary


def random_forest_permutation_stability(
    model: Pipeline,
    features_train: pd.DataFrame,
    target_train: pd.Series,
    cv_splits: list[tuple[np.ndarray, np.ndarray]],
    top_k: int = TOP_K,
    seed: int = SEED,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    detail_rows: list[dict[str, Any]] = []
    feature_names = list(features_train.columns)

    for fold_number, (train_indices, valid_indices) in enumerate(cv_splits, start=1):
        fitted = clone(model).fit(
            features_train.iloc[train_indices], target_train.iloc[train_indices]
        )
        importance = permutation_importance(
            fitted,
            features_train.iloc[valid_indices],
            target_train.iloc[valid_indices],
            scoring="average_precision",
            n_repeats=3,
            random_state=seed + fold_number,
            n_jobs=1,
        )
        top_indices = set(
            np.argsort(importance.importances_mean)[::-1][:top_k].tolist()
        )
        for index, feature in enumerate(feature_names):
            detail_rows.append(
                {
                    "fold": fold_number,
                    "feature": feature,
                    "ap_permutation_importance_mean": float(
                        importance.importances_mean[index]
                    ),
                    "ap_permutation_importance_std": float(
                        importance.importances_std[index]
                    ),
                    "in_top_k": index in top_indices,
                }
            )

    details = pd.DataFrame(detail_rows)
    total_folds = details["fold"].nunique()
    summary = (
        details.groupby("feature", as_index=False)
        .agg(
            top_k_count=("in_top_k", "sum"),
            mean_ap_drop=("ap_permutation_importance_mean", "mean"),
            ap_drop_std_across_folds=(
                "ap_permutation_importance_mean",
                "std",
            ),
        )
        .assign(top_k_frequency=lambda frame: frame["top_k_count"] / total_folds)
        .sort_values(
            ["top_k_frequency", "mean_ap_drop"], ascending=[False, False]
        )
    )
    return details, summary


def merge_feature_candidates(
    logistic_summary: pd.DataFrame,
    forest_summary: pd.DataFrame,
) -> pd.DataFrame:
    logistic = logistic_summary[
        [
            "feature",
            "top_k_frequency",
            "mean_absolute_coefficient",
            "mean_standardized_coefficient",
            "sign_consistency",
        ]
    ].rename(columns={"top_k_frequency": "logistic_top20_frequency"})
    forest = forest_summary[
        ["feature", "top_k_frequency", "mean_ap_drop", "ap_drop_std_across_folds"]
    ].rename(columns={"top_k_frequency": "rf_top20_frequency"})

    candidates = logistic.merge(forest, on="feature", how="outer")
    candidates["logistic_rank"] = candidates["mean_absolute_coefficient"].rank(
        method="min", ascending=False
    )
    candidates["rf_rank"] = candidates["mean_ap_drop"].rank(
        method="min", ascending=False
    )
    candidates["meets_either_method_60pct_rule"] = (
        (candidates["logistic_top20_frequency"] >= 0.60)
        | (candidates["rf_top20_frequency"] >= 0.60)
    )
    candidates["meets_both_methods_60pct_rule"] = (
        (candidates["logistic_top20_frequency"] >= 0.60)
        & (candidates["rf_top20_frequency"] >= 0.60)
    )
    candidates["evidence_frequency_sum"] = (
        candidates["logistic_top20_frequency"].fillna(0)
        + candidates["rf_top20_frequency"].fillna(0)
    )
    candidates["mean_rank"] = candidates[["logistic_rank", "rf_rank"]].mean(
        axis=1
    )
    return candidates.sort_values(
        [
            "meets_both_methods_60pct_rule",
            "meets_either_method_60pct_rule",
            "evidence_frequency_sum",
            "mean_rank",
        ],
        ascending=[False, False, False, True],
    )


def add_robust_deviation_columns(
    table: pd.DataFrame,
    feature_rows: pd.DataFrame,
    features_train: pd.DataFrame,
) -> pd.DataFrame:
    medians = features_train.median(axis=0, skipna=True)
    q1 = features_train.quantile(0.25)
    q3 = features_train.quantile(0.75)
    iqr = (q3 - q1).replace(0, np.nan)

    extreme_counts: list[int] = []
    top_deviations: list[str] = []
    for row_index in feature_rows.index:
        deviation = ((feature_rows.loc[row_index] - medians).abs() / iqr).dropna()
        deviation = deviation.sort_values(ascending=False)
        extreme_counts.append(int((deviation > 3).sum()))
        top_deviations.append(
            "; ".join(
                f"{feature}:{value:.2f} IQR"
                for feature, value in deviation.head(5).items()
            )
        )
    output = table.copy()
    output["observed_features_over_3_iqr_from_train_median"] = extreme_counts
    output["top_robust_deviations"] = top_deviations
    return output


def make_false_negative_outputs(
    features_train: pd.DataFrame,
    features_test: pd.DataFrame,
    target_test: pd.Series,
    metadata_test: pd.DataFrame,
    fitted_models: Mapping[str, Pipeline],
    selected_model: str,
    selected_threshold: float,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    table = metadata_test[["sample_id", "timestamp", "label"]].copy()
    table["missing_count"] = features_test.isna().sum(axis=1)
    table["missing_pct"] = table["missing_count"] / features_test.shape[1]

    for model_name, fitted in fitted_models.items():
        score = positive_scores(fitted, features_test)
        table[f"{model_name}_score"] = score
        table[f"{model_name}_prediction_0_5"] = np.where(
            score >= 0.5, "FAIL", "PASS"
        )

    selected_scores = table[f"{selected_model}_score"]
    table["selected_threshold"] = selected_threshold
    table["selected_threshold_prediction"] = np.where(
        selected_scores >= selected_threshold, "FAIL", "PASS"
    )
    table["score_minus_threshold"] = selected_scores - selected_threshold
    table["detection_outcome"] = np.select(
        [
            (target_test == 1) & (selected_scores >= selected_threshold),
            (target_test == 1) & (selected_scores < selected_threshold),
            (target_test == 0) & (selected_scores >= selected_threshold),
        ],
        ["TRUE_POSITIVE", "FALSE_NEGATIVE", "FALSE_POSITIVE"],
        default="TRUE_NEGATIVE",
    )

    fail_cases = table[target_test == 1].copy().sort_values(
        f"{selected_model}_score"
    )
    false_negatives = table[
        (target_test == 1) & (selected_scores < selected_threshold)
    ].copy()
    false_negatives = add_robust_deviation_columns(
        false_negatives,
        features_test.loc[false_negatives.index],
        features_train,
    ).sort_values(f"{selected_model}_score", ascending=False)

    true_positive_missing = table.loc[
        (target_test == 1) & (selected_scores >= selected_threshold), "missing_count"
    ]
    false_negative_missing = false_negatives["missing_count"]
    summary = {
        "selected_model": selected_model,
        "selected_threshold": selected_threshold,
        "test_fail_cases": int((target_test == 1).sum()),
        "true_positives": int(
            ((target_test == 1) & (selected_scores >= selected_threshold)).sum()
        ),
        "false_negatives": int(len(false_negatives)),
        "one_fail_case_recall_step_percentage_points": float(
            100 / (target_test == 1).sum()
        ),
        "false_negative_missing_count_median": (
            float(false_negative_missing.median())
            if not false_negative_missing.empty
            else None
        ),
        "true_positive_missing_count_median": (
            float(true_positive_missing.median())
            if not true_positive_missing.empty
            else None
        ),
        "interpretation": (
            "Exploratory error analysis only. Test-set errors were not used to "
            "refit the model or change the threshold."
        ),
    }
    return false_negatives, fail_cases, summary


def evaluate_temporal_sensitivity(
    features: pd.DataFrame,
    target: pd.Series,
    metadata: pd.DataFrame,
    selected_model: Pipeline,
    seed: int = SEED,
) -> dict[str, Any]:
    ordered_indices = metadata.sort_values("timestamp").index.to_numpy()
    split_index = int(len(ordered_indices) * (1 - TEST_SIZE))
    train_indices = ordered_indices[:split_index]
    test_indices = ordered_indices[split_index:]

    chronological_oof_cv = StratifiedKFold(
        n_splits=CV_SPLITS,
        shuffle=True,
        random_state=seed,
    )
    chronological_oof_probabilities = cross_val_predict(
        selected_model,
        features.loc[train_indices],
        target.loc[train_indices],
        cv=chronological_oof_cv,
        method="predict_proba",
        n_jobs=1,
    )
    chronological_oof_scores = positive_oof_scores(
        chronological_oof_probabilities,
        target.loc[train_indices],
    )
    chronological_threshold, threshold_details = select_quality_threshold(
        target.loc[train_indices],
        chronological_oof_scores,
        recall_target=QUALITY_RECALL_TARGET,
    )

    fitted = clone(selected_model).fit(
        features.loc[train_indices], target.loc[train_indices]
    )
    scores = positive_scores(fitted, features.loc[test_indices])
    return {
        "purpose": (
            "Secondary chronological holdout sensitivity check; not used for "
            "primary model-family or primary quality-threshold selection."
        ),
        "train_rows": int(len(train_indices)),
        "test_rows": int(len(test_indices)),
        "train_fail_count": int(target.loc[train_indices].sum()),
        "test_fail_count": int(target.loc[test_indices].sum()),
        "train_time_min": metadata.loc[train_indices, "timestamp"].min(),
        "train_time_max": metadata.loc[train_indices, "timestamp"].max(),
        "test_time_min": metadata.loc[test_indices, "timestamp"].min(),
        "test_time_max": metadata.loc[test_indices, "timestamp"].max(),
        "metrics_at_0_5": binary_metrics(
            target.loc[test_indices], scores, threshold=0.5
        ),
        "train_only_threshold_selection": {
            **threshold_details,
            "test_data_used_to_select_threshold": False,
        },
        "metrics_at_train_only_quality_threshold": binary_metrics(
            target.loc[test_indices],
            scores,
            threshold=chronological_threshold,
        ),
        "caution": (
            "Exploratory sensitivity only: the model family was selected in the "
            "primary random-split analysis, whose training period overlaps this "
            "chronological holdout period. No lot/batch identifier is available, "
            "so temporal proximity and manufacturing-group dependence cannot be "
            "fully controlled."
        ),
    }


def save_figures(
    figures_dir: Path,
    dataset_summary: Mapping[str, Any],
    feature_quality: pd.DataFrame,
    cv_summary: pd.DataFrame,
    test_metrics: pd.DataFrame,
    test_predictions: pd.DataFrame,
    target_test: pd.Series,
    selected_model: str,
    selected_threshold: float,
    feature_candidates: pd.DataFrame,
) -> None:
    figures_dir.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid", context="notebook")
    plt.rcParams.update({"figure.dpi": 140, "savefig.dpi": 200})

    # Class distribution
    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    counts = [dataset_summary["pass_count"], dataset_summary["fail_count"]]
    bars = ax.bar(["PASS", "FAIL"], counts, color=["#4C78A8", "#E45756"])
    ax.set_title("SECOM class distribution")
    ax.set_ylabel("Samples")
    for bar, count in zip(bars, counts, strict=True):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            count,
            f"{count:,}\n({count / sum(counts):.1%})",
            ha="center",
            va="bottom",
        )
    fig.tight_layout()
    fig.savefig(figures_dir / "01_class_distribution.png", bbox_inches="tight")
    plt.close(fig)

    # Missingness
    top_missing = feature_quality.nlargest(20, "missing_pct").sort_values(
        "missing_pct"
    )
    fig, ax = plt.subplots(figsize=(8, 6.5))
    ax.barh(top_missing["feature"], top_missing["missing_pct"] * 100, color="#F2CF5B")
    ax.set_title("Top 20 features by missingness")
    ax.set_xlabel("Missing values (%)")
    fig.tight_layout()
    fig.savefig(figures_dir / "02_missingness_top20.png", bbox_inches="tight")
    plt.close(fig)

    # CV metrics
    metrics_to_plot = [
        "fail_recall",
        "fail_precision",
        "fail_f1",
        "balanced_accuracy",
        "average_precision",
        "roc_auc",
    ]
    cv_plot = cv_summary[cv_summary["metric"].isin(metrics_to_plot)].copy()
    model_order = list(MODEL_LABELS.values())
    fig, ax = plt.subplots(figsize=(11, 5.5))
    sns.barplot(
        data=cv_plot,
        x="metric",
        y="mean",
        hue="model_label",
        hue_order=model_order,
        errorbar=None,
        ax=ax,
    )
    ax.set_ylim(0, 1)
    ax.set_title(f"Train-only repeated CV ({CV_SPLITS}-fold × {CV_REPEATS})")
    ax.set_xlabel("")
    ax.set_ylabel("Mean score")
    ax.tick_params(axis="x", rotation=25)
    ax.legend(title="Model", loc="upper left", bbox_to_anchor=(1.01, 1))
    fig.tight_layout()
    fig.savefig(figures_dir / "03_cv_model_comparison.png", bbox_inches="tight")
    plt.close(fig)

    # Test metric comparison
    metric_columns = [
        "fail_recall",
        "fail_precision",
        "fail_f1",
        "balanced_accuracy",
        "average_precision",
        "roc_auc",
    ]
    test_plot = test_metrics.melt(
        id_vars=["evaluation_label"],
        value_vars=metric_columns,
        var_name="metric",
        value_name="value",
    )
    fig, ax = plt.subplots(figsize=(11, 5.5))
    sns.barplot(
        data=test_plot,
        x="metric",
        y="value",
        hue="evaluation_label",
        errorbar=None,
        ax=ax,
    )
    ax.set_ylim(0, 1)
    ax.set_title("Locked stratified test metrics")
    ax.set_xlabel("")
    ax.set_ylabel("Score")
    ax.tick_params(axis="x", rotation=25)
    ax.legend(title="Evaluation", loc="upper left", bbox_to_anchor=(1.01, 1))
    fig.tight_layout()
    fig.savefig(figures_dir / "04_test_model_comparison.png", bbox_inches="tight")
    plt.close(fig)

    # Confusion matrices
    plot_rows = test_metrics.to_dict("records")
    columns = 2
    rows = math.ceil(len(plot_rows) / columns)
    fig, axes = plt.subplots(rows, columns, figsize=(8, 3.8 * rows))
    axes_array = np.atleast_1d(axes).ravel()
    for ax, record in zip(axes_array, plot_rows, strict=False):
        matrix = np.array(
            [
                [record["true_negative"], record["false_positive"]],
                [record["false_negative"], record["true_positive"]],
            ]
        )
        sns.heatmap(
            matrix,
            annot=True,
            fmt="d",
            cmap="Blues",
            cbar=False,
            xticklabels=["Pred PASS", "Pred FAIL"],
            yticklabels=["Actual PASS", "Actual FAIL"],
            ax=ax,
        )
        ax.set_title(record["evaluation_label"])
    for ax in axes_array[len(plot_rows) :]:
        ax.axis("off")
    fig.suptitle("Confusion matrices (rows=actual, columns=predicted)", y=1.01)
    fig.tight_layout()
    fig.savefig(figures_dir / "05_confusion_matrices.png", bbox_inches="tight")
    plt.close(fig)

    # PR curves
    fig, ax = plt.subplots(figsize=(7, 5.5))
    y_test_array = np.asarray(target_test)
    for model_name, model_label in MODEL_LABELS.items():
        scores = test_predictions[f"{model_name}_score"].to_numpy()
        precision, recall, _ = precision_recall_curve(y_test_array, scores)
        ap = average_precision_score(y_test_array, scores)
        ax.plot(recall, precision, label=f"{model_label} (AP={ap:.3f})")
    selected_scores = test_predictions[f"{selected_model}_score"].to_numpy()
    selected_predictions = selected_scores >= selected_threshold
    marker_precision = precision_score(
        y_test_array, selected_predictions, zero_division=0
    )
    marker_recall = recall_score(y_test_array, selected_predictions, zero_division=0)
    ax.scatter(
        [marker_recall],
        [marker_precision],
        color="black",
        marker="X",
        s=90,
        label=f"Quality threshold={selected_threshold:.3f}",
        zorder=5,
    )
    ax.axhline(y_test_array.mean(), color="gray", linestyle="--", label="FAIL prevalence")
    ax.set_xlim(0, 1.02)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("FAIL Recall")
    ax.set_ylabel("FAIL Precision")
    ax.set_title("Precision–recall curves on locked test set")
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    fig.savefig(figures_dir / "06_precision_recall_curves.png", bbox_inches="tight")
    plt.close(fig)

    # ROC curves
    fig, ax = plt.subplots(figsize=(7, 5.5))
    for model_name, model_label in MODEL_LABELS.items():
        scores = test_predictions[f"{model_name}_score"].to_numpy()
        fpr, tpr, _ = roc_curve(y_test_array, scores)
        auc = roc_auc_score(y_test_array, scores)
        ax.plot(fpr, tpr, label=f"{model_label} (AUC={auc:.3f})")
    ax.plot([0, 1], [0, 1], color="gray", linestyle="--")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate / FAIL Recall")
    ax.set_title("ROC curves on locked test set")
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(figures_dir / "07_roc_curves.png", bbox_inches="tight")
    plt.close(fig)

    # Feature candidate stability
    candidate_plot = feature_candidates.head(15).sort_values(
        "evidence_frequency_sum"
    )
    fig, ax = plt.subplots(figsize=(8.5, 7))
    positions = np.arange(len(candidate_plot))
    height = 0.38
    ax.barh(
        positions - height / 2,
        candidate_plot["logistic_top20_frequency"],
        height,
        label="Logistic top-20 frequency",
        color="#4C78A8",
    )
    ax.barh(
        positions + height / 2,
        candidate_plot["rf_top20_frequency"],
        height,
        label="RF permutation top-20 frequency",
        color="#F58518",
    )
    ax.set_yticks(positions, candidate_plot["feature"])
    ax.set_xlim(0, 1)
    ax.set_xlabel("Fraction of train-only CV folds")
    ax.set_title("Anonymous predictive-signal candidate stability")
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(figures_dir / "08_feature_candidate_stability.png", bbox_inches="tight")
    plt.close(fig)

    # FAIL scores and false negatives at selected threshold
    fail_mask = y_test_array == 1
    fail_scores = selected_scores[fail_mask]
    outcomes = np.where(fail_scores >= selected_threshold, "Detected", "Missed (FN)")
    order = np.argsort(fail_scores)
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    colors = np.where(outcomes[order] == "Detected", "#59A14F", "#E45756")
    ax.scatter(np.arange(len(fail_scores)), fail_scores[order], c=colors, s=55)
    ax.axhline(
        selected_threshold,
        color="black",
        linestyle="--",
        label=f"Threshold={selected_threshold:.3f}",
    )
    ax.set_xlabel("Test FAIL cases sorted by score")
    ax.set_ylabel("Model decision score")
    ax.set_title("Selected model scores for actual FAIL cases")
    ax.legend()
    fig.tight_layout()
    fig.savefig(figures_dir / "09_false_negative_scores.png", bbox_inches="tight")
    plt.close(fig)


def run_analysis(
    data_dir: Path = DEFAULT_DATA_DIR,
    results_dir: Path = DEFAULT_RESULTS_DIR,
    figures_dir: Path = DEFAULT_FIGURES_DIR,
    models_dir: Path = DEFAULT_MODELS_DIR,
    seed: int = SEED,
) -> dict[str, Any]:
    tables_dir = results_dir / "tables"
    metadata_dir = results_dir / "metadata"
    tables_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)

    features, target, metadata = load_secom(data_dir)
    dataset_summary, feature_quality, row_quality = audit_dataset(
        features, target, metadata
    )
    write_json(metadata_dir / "dataset_summary.json", dataset_summary)
    feature_quality.to_csv(tables_dir / "data_quality_by_feature.csv", index=False)
    row_quality.to_csv(tables_dir / "data_quality_by_sample.csv", index=False)

    if dataset_summary["duplicate_feature_rows"] > 0:
        raise RuntimeError(
            "Exact duplicate feature rows detected. Use a group-aware holdout before modeling."
        )

    train_indices, test_indices = train_test_split(
        features.index,
        test_size=TEST_SIZE,
        random_state=seed,
        stratify=target,
    )
    features_train = features.loc[train_indices].copy()
    features_test = features.loc[test_indices].copy()
    target_train = target.loc[train_indices].copy()
    target_test = target.loc[test_indices].copy()
    metadata_train = metadata.loc[train_indices].copy()
    metadata_test = metadata.loc[test_indices].copy()

    split_table = metadata[["sample_id", "timestamp", "label"]].copy()
    split_table["split"] = "train"
    split_table.loc[test_indices, "split"] = "test"
    split_table.to_csv(tables_dir / "split_assignment.csv", index=False)
    shared_timestamps = set(metadata_train["timestamp"]) & set(
        metadata_test["timestamp"]
    )
    shared_timestamp_rows = metadata[
        metadata["timestamp"].isin(shared_timestamps)
    ]
    split_summary = {
        "method": "stratified random holdout",
        "random_seed": seed,
        "test_size_requested": TEST_SIZE,
        "train_rows": int(len(train_indices)),
        "test_rows": int(len(test_indices)),
        "train_pass": int((target_train == 0).sum()),
        "train_fail": int((target_train == 1).sum()),
        "test_pass": int((target_test == 0).sum()),
        "test_fail": int((target_test == 1).sum()),
        "shared_timestamp_groups_across_train_test": int(len(shared_timestamps)),
        "rows_in_shared_timestamp_groups": int(len(shared_timestamp_rows)),
        "shared_timestamp_caution": (
            "Timestamp is not used as a feature, but repeated timestamps could be "
            "a proxy for unknown manufacturing groups. No lot/batch ID is available."
        ),
        "timestamp_used_as_model_feature": False,
        "preprocessing_fit_scope": "training fold only via sklearn Pipeline",
        "test_usage": "locked final evaluation only",
    }
    write_json(metadata_dir / "split_summary.json", split_summary)

    models = make_models(seed)
    repeated_cv = RepeatedStratifiedKFold(
        n_splits=CV_SPLITS,
        n_repeats=CV_REPEATS,
        random_state=seed,
    )
    cv_splits = list(repeated_cv.split(features_train, target_train))
    cv_folds, cv_summary, raw_cv_scores = evaluate_cv(
        models, features_train, target_train, cv_splits
    )
    cv_folds.to_csv(tables_dir / "cv_metrics_by_fold.csv", index=False)
    cv_summary.to_csv(tables_dir / "cv_metrics_summary.csv", index=False)

    selected_model_name, model_ranking = select_model_from_cv(raw_cv_scores)
    selected_model_template = models[selected_model_name]

    oof_cv = StratifiedKFold(n_splits=CV_SPLITS, shuffle=True, random_state=seed)
    oof_probability_matrix = cross_val_predict(
        selected_model_template,
        features_train,
        target_train,
        cv=oof_cv,
        method="predict_proba",
        n_jobs=1,
    )
    oof_probabilities = positive_oof_scores(
        oof_probability_matrix,
        target_train,
    )
    selected_threshold, threshold_details = select_quality_threshold(
        target_train,
        oof_probabilities,
        recall_target=QUALITY_RECALL_TARGET,
    )
    threshold_details.update(
        {
            "selected_model": selected_model_name,
            "model_selection_rule": (
                "Highest mean Average Precision among Logistic Regression and "
                "Random Forest in train-only repeated CV; mean FAIL recall breaks ties."
            ),
            "model_ranking": model_ranking,
            "oof_metrics_at_0_5": binary_metrics(
                target_train, oof_probabilities, threshold=0.5
            ),
            "oof_metrics_at_selected_threshold": binary_metrics(
                target_train, oof_probabilities, threshold=selected_threshold
            ),
            "test_data_used_to_select_threshold": False,
        }
    )
    write_json(metadata_dir / "threshold_selection.json", threshold_details)

    fitted_models: dict[str, Pipeline] = {}
    test_rows: list[dict[str, Any]] = []
    test_predictions = metadata_test[["sample_id", "timestamp", "label"]].copy()
    for model_name, model in models.items():
        fitted = clone(model).fit(features_train, target_train)
        fitted_models[model_name] = fitted
        scores = positive_scores(fitted, features_test)
        test_predictions[f"{model_name}_score"] = scores
        test_predictions[f"{model_name}_prediction_0_5"] = np.where(
            scores >= 0.5, "FAIL", "PASS"
        )
        metrics = binary_metrics(target_test, scores, threshold=0.5)
        test_rows.append(
            {
                "evaluation": model_name,
                "evaluation_label": f"{MODEL_LABELS[model_name]} @ 0.5",
                "model": model_name,
                **metrics,
            }
        )

    selected_fitted = fitted_models[selected_model_name]
    selected_test_scores = positive_scores(selected_fitted, features_test)
    selected_quality_metrics = binary_metrics(
        target_test, selected_test_scores, threshold=selected_threshold
    )
    quality_evaluation_name = f"{selected_model_name}_quality_threshold"
    test_rows.append(
        {
            "evaluation": quality_evaluation_name,
            "evaluation_label": (
                f"{MODEL_LABELS[selected_model_name]} @ {selected_threshold:.3f}"
            ),
            "model": selected_model_name,
            **selected_quality_metrics,
        }
    )
    test_predictions["selected_quality_threshold"] = selected_threshold
    test_predictions["selected_quality_prediction"] = np.where(
        selected_test_scores >= selected_threshold, "FAIL", "PASS"
    )
    test_predictions.to_csv(tables_dir / "test_predictions.csv", index=False)
    test_metrics = pd.DataFrame(test_rows)
    test_metrics.to_csv(tables_dir / "test_metrics.csv", index=False)

    # Feature stability uses train/CV data only. RF permutation analysis uses one
    # 5-fold cycle to limit runtime; logistic stability uses all repeated folds.
    logistic_details, logistic_summary = logistic_feature_stability(
        models["logistic_balanced"],
        features_train,
        target_train,
        cv_splits,
    )
    stability_cv = list(
        StratifiedKFold(n_splits=CV_SPLITS, shuffle=True, random_state=seed).split(
            features_train, target_train
        )
    )
    forest_details, forest_summary = random_forest_permutation_stability(
        models["random_forest_balanced"],
        features_train,
        target_train,
        stability_cv,
        seed=seed,
    )
    feature_candidates = merge_feature_candidates(logistic_summary, forest_summary)
    logistic_details.to_csv(
        tables_dir / "logistic_feature_stability_by_fold.csv", index=False
    )
    logistic_summary.to_csv(
        tables_dir / "logistic_feature_stability_summary.csv", index=False
    )
    forest_details.to_csv(
        tables_dir / "rf_permutation_stability_by_fold.csv", index=False
    )
    forest_summary.to_csv(
        tables_dir / "rf_permutation_stability_summary.csv", index=False
    )
    feature_candidates.to_csv(tables_dir / "feature_candidates.csv", index=False)

    rf_fitted = fitted_models["random_forest_balanced"]
    rf_retained = retained_feature_names(rf_fitted, features_train.columns)
    rf_impurity = pd.DataFrame(
        {
            "feature": rf_retained,
            "impurity_importance": rf_fitted.named_steps[
                "classifier"
            ].feature_importances_,
        }
    ).sort_values("impurity_importance", ascending=False)
    rf_impurity.to_csv(
        tables_dir / "rf_impurity_importance_secondary.csv", index=False
    )

    false_negatives, fail_cases, fn_summary = make_false_negative_outputs(
        features_train,
        features_test,
        target_test,
        metadata_test,
        fitted_models,
        selected_model_name,
        selected_threshold,
    )
    false_negatives.to_csv(tables_dir / "false_negatives.csv", index=False)
    fail_cases.to_csv(tables_dir / "test_fail_cases.csv", index=False)
    write_json(metadata_dir / "false_negative_summary.json", fn_summary)

    temporal_sensitivity = evaluate_temporal_sensitivity(
        features,
        target,
        metadata,
        selected_model_template,
        seed=seed,
    )
    write_json(metadata_dir / "temporal_sensitivity.json", temporal_sensitivity)

    joblib.dump(selected_fitted, models_dir / "selected_model.joblib")
    write_json(
        models_dir / "selected_model_metadata.json",
        {
            "model": selected_model_name,
            "default_threshold": 0.5,
            "quality_threshold": selected_threshold,
            "feature_count_raw": int(features_train.shape[1]),
            "retained_feature_count_after_train_fit": int(
                fitted_models[selected_model_name]
                .named_steps["drop_constant"]
                .get_support()
                .sum()
            ),
            "trained_on_rows": int(len(features_train)),
            "training_sample_ids": metadata_train["sample_id"].tolist(),
        },
    )

    save_figures(
        figures_dir,
        dataset_summary,
        feature_quality,
        cv_summary,
        test_metrics,
        test_predictions,
        target_test,
        selected_model_name,
        selected_threshold,
        feature_candidates,
    )

    run_summary = {
        "status": "completed",
        "seed": seed,
        "selected_model": selected_model_name,
        "selected_model_label": MODEL_LABELS[selected_model_name],
        "selected_quality_threshold": selected_threshold,
        "dataset": dataset_summary,
        "split": split_summary,
        "selected_test_metrics_0_5": next(
            row for row in test_rows if row["evaluation"] == selected_model_name
        ),
        "selected_test_metrics_quality_threshold": next(
            row for row in test_rows if row["evaluation"] == quality_evaluation_name
        ),
        "false_negative_summary": fn_summary,
        "temporal_sensitivity": temporal_sensitivity,
        "top_feature_candidates": feature_candidates.head(20).to_dict("records"),
        "interpretation_limits": [
            "The 590 inputs are anonymized; predictive association is not causation.",
            "The stratified test set contains few FAIL cases, so one case changes recall materially.",
            "No lot, equipment, recipe, or batch identifier is available.",
            "External and prospective validation are required before operational use.",
        ],
    }
    write_json(results_dir / "run_summary.json", run_summary)
    write_json(
        metadata_dir / "runtime_versions.json",
        {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
            "scipy": scipy.__version__,
            "joblib": joblib.__version__,
            "matplotlib": matplotlib.__version__,
            "seaborn": sns.__version__,
        },
    )
    return run_summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument("--figures-dir", type=Path, default=DEFAULT_FIGURES_DIR)
    parser.add_argument("--models-dir", type=Path, default=DEFAULT_MODELS_DIR)
    parser.add_argument("--seed", type=int, default=SEED)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="X does not have valid feature names",
            category=UserWarning,
        )
        summary = run_analysis(
            data_dir=args.data_dir,
            results_dir=args.results_dir,
            figures_dir=args.figures_dir,
            models_dir=args.models_dir,
            seed=args.seed,
        )
    selected = summary["selected_test_metrics_quality_threshold"]
    print("SECOM analysis completed")
    print(f"Selected model: {summary['selected_model_label']}")
    print(f"Quality threshold: {summary['selected_quality_threshold']:.6f}")
    print(
        "Locked test: "
        f"Recall={selected['fail_recall']:.3f}, "
        f"Precision={selected['fail_precision']:.3f}, "
        f"F1={selected['fail_f1']:.3f}, "
        f"FN={selected['false_negative']}"
    )


if __name__ == "__main__":
    main()
