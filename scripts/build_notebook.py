#!/usr/bin/env python3
"""Build and execute the portfolio evidence notebook with the project venv."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = PROJECT_ROOT / "notebooks" / "secom_quality_analysis.ipynb"


def build_notebook() -> nbformat.NotebookNode:
    cells = [
        new_markdown_cell(
            """# UCI SECOM 반도체 제조 품질분석 — 실행 증거 Notebook

이 Notebook은 공개·익명화된 [UCI SECOM](https://archive.ics.uci.edu/dataset/179/secom) 원본을 다시 읽고, 고정된 train/test split에서 Dummy·Logistic Regression·Random Forest를 재학습해 저장된 결과와 일치하는지 확인한다.

목적은 높은 수치를 과장하는 것이 아니라 **데이터 품질, leakage 통제, FAIL Recall–Precision trade-off, 지표 불확실성, False Negative, 시간 일반화·변수 안정성 한계**를 채용담당자가 빠르게 검토할 수 있게 하는 것이다. 생산 적용이나 공정 원인 규명을 주장하지 않는다."""
        ),
        new_code_cell(
            """from pathlib import Path
import json
import platform
import sys

import numpy as np
import pandas as pd
from IPython.display import Image, Markdown, display
from sklearn.base import clone
from sklearn.model_selection import train_test_split

def find_project_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "src" / "secom_analysis.py").exists():
            return candidate
    raise FileNotFoundError("Could not locate project root from current directory")

ROOT = find_project_root(Path.cwd().resolve())
sys.path.insert(0, str(ROOT / "src"))

import secom_analysis as analysis

print(f"Python: {platform.python_version()}")
print("Project-local analysis environment loaded.")
print("Project root located successfully.")"""
        ),
        new_markdown_cell("## 1. 공식 원본과 데이터 품질"),
        new_code_cell(
            """X, y, metadata = analysis.load_secom(ROOT / "data" / "raw")
dataset_summary, feature_quality, row_quality = analysis.audit_dataset(X, y, metadata)

audit_view = pd.DataFrame({
    "item": [
        "rows", "actual input features", "PASS", "FAIL", "FAIL rate",
        "missing cells", "missing cell rate", "features with missing",
        "observed constant features", "exact duplicate feature rows",
    ],
    "value": [
        dataset_summary["rows"], dataset_summary["input_features_actual"],
        dataset_summary["pass_count"], dataset_summary["fail_count"],
        f"{dataset_summary['fail_pct']:.2%}", dataset_summary["missing_cells"],
        f"{dataset_summary['missing_cell_pct']:.2%}",
        dataset_summary["features_with_missing"],
        dataset_summary["observed_constant_features_full_data"],
        dataset_summary["duplicate_feature_rows"],
    ],
})
display(audit_view)

assert X.shape == (1567, 590)
assert y.value_counts().sort_index().to_dict() == {0: 1463, 1: 104}
assert int(X.isna().sum().sum()) == 41_951
assert dataset_summary["observed_constant_features_full_data"] == 116"""
        ),
        new_code_cell(
            """display(Image(filename=str(ROOT / "figures" / "01_class_distribution.png")))
display(Image(filename=str(ROOT / "figures" / "02_missingness_top20.png")))"""
        ),
        new_markdown_cell(
            """UCI 웹 메타데이터는 591 features라고 설명하지만, 공식 `secom.data`의 모든 행에는 실제 값이 590개다. 분석은 임의의 변수를 추가하지 않고 원본 파일 구조를 따른다. 라벨은 UCI `-1=PASS`, `1=FAIL`을 코드 내부 `0=PASS`, `1=FAIL`로 매핑한다."""
        ),
        new_markdown_cell("## 2. Leakage 방지 설계와 고정 split"),
        new_code_cell(
            """split_summary = json.loads((ROOT / "results" / "metadata" / "split_summary.json").read_text())
display(pd.DataFrame([split_summary]).T.rename(columns={0: "recorded value"}))

models = analysis.make_models(analysis.SEED)
pipeline_steps = {
    name: " → ".join(model.named_steps.keys())
    for name, model in models.items()
}
display(pd.Series(pipeline_steps, name="train-fold-only pipeline").to_frame())

assert split_summary["train_rows"] == 1253
assert split_summary["test_rows"] == 314
assert split_summary["train_fail"] == 83
assert split_summary["test_fail"] == 21
assert split_summary["timestamp_used_as_model_feature"] is False"""
        ),
        new_markdown_cell(
            """결측 대치, 분산 0 변수 제거, Logistic 표준화는 모두 `sklearn Pipeline` 내부에서 각 학습 fold에만 fit된다. timestamp는 모델 입력에서 제외했다. 동일 timestamp 11개 그룹(22행)이 무작위 train/test 양쪽에 걸쳐 있어 미지의 batch proxy 가능성은 한계로 남긴다."""
        ),
        new_markdown_cell("## 3. Baseline 재학습과 잠금 테스트 지표 재계산"),
        new_code_cell(
            """train_indices, test_indices = train_test_split(
    X.index,
    test_size=analysis.TEST_SIZE,
    random_state=analysis.SEED,
    stratify=y,
)
X_train, X_test = X.loc[train_indices], X.loc[test_indices]
y_train, y_test = y.loc[train_indices], y.loc[test_indices]

threshold_record = json.loads(
    (ROOT / "results" / "metadata" / "threshold_selection.json").read_text()
)
quality_threshold = threshold_record["selected_threshold"]
selected_model = threshold_record["selected_model"]

fitted = {}
evaluation_rows = []
for model_name, model in models.items():
    estimator = clone(model).fit(X_train, y_train)
    fitted[model_name] = estimator
    score = analysis.positive_scores(estimator, X_test)
    evaluation_rows.append({
        "evaluation": model_name,
        "model": model_name,
        **analysis.binary_metrics(y_test, score, threshold=0.5),
    })

selected_score = analysis.positive_scores(fitted[selected_model], X_test)
evaluation_rows.append({
    "evaluation": f"{selected_model}_quality_threshold",
    "model": selected_model,
    **analysis.binary_metrics(y_test, selected_score, threshold=quality_threshold),
})

recomputed = pd.DataFrame(evaluation_rows)
saved = pd.read_csv(ROOT / "results" / "tables" / "test_metrics.csv")

for row in recomputed.to_dict("records"):
    expected = saved.loc[saved["evaluation"] == row["evaluation"]].iloc[0]
    for key in ["true_negative", "false_positive", "false_negative", "true_positive"]:
        assert int(row[key]) == int(expected[key])
    for key in [
        "fail_precision", "fail_recall", "fail_f1", "balanced_accuracy",
        "roc_auc", "average_precision", "pr_auc_trapezoid",
    ]:
        assert np.isclose(row[key], expected[key], atol=1e-12)

display(recomputed[[
    "evaluation", "threshold", "fail_precision", "fail_recall", "fail_f1",
    "balanced_accuracy", "roc_auc", "average_precision", "pr_auc_trapezoid",
    "true_negative", "false_positive", "false_negative", "true_positive",
]].round(4))
print("Saved metrics and notebook recomputation match.")"""
        ),
        new_code_cell(
            """display(Image(filename=str(ROOT / "figures" / "05_confusion_matrices.png")))"""
        ),
        new_markdown_cell(
            """Random Forest @ 0.5는 Accuracy 93.31%지만 실제 FAIL 21건을 전부 놓쳤다. train-only OOF에서 정한 후보 임계값 `0.060939`에서는 17/21을 찾아 Recall 80.95%가 되었지만, PASS 145건을 오탐해 Precision은 10.49%였다. 이 값은 보정된 불량확률이나 운영 최적점이 아니라 FN 감소와 추가확인 후보 증가의 **분석 가정**이다."""
        ),
        new_markdown_cell("### 잠금 test 지표의 bootstrap 불확실성"),
        new_code_cell(
            """bootstrap_ci = pd.read_csv(
    ROOT / "results" / "tables" / "test_metric_bootstrap_ci.csv"
).set_index("metric")
display(bootstrap_ci.loc[[
    "fail_precision", "fail_recall", "fail_f1", "balanced_accuracy",
    "roc_auc", "average_precision",
], ["point_estimate", "ci_low", "ci_high", "valid_replicates"]].round(4))

assert bootstrap_ci.loc["fail_recall", "valid_replicates"] == 10_000
assert np.isclose(bootstrap_ci.loc["fail_recall", "point_estimate"], 17 / 21)
assert np.isclose(bootstrap_ci.loc["fail_recall", "ci_low"], 13 / 21)
assert np.isclose(bootstrap_ci.loc["fail_recall", "ci_high"], 20 / 21)"""
        ),
        new_markdown_cell("## 4. False Negative 4건"),
        new_code_cell(
            """false_negatives = pd.read_csv(ROOT / "results" / "tables" / "false_negatives.csv")
display(false_negatives[[
    "sample_id", "timestamp", "missing_count",
    "random_forest_balanced_score", "selected_threshold",
    "score_minus_threshold", "top_robust_deviations",
]])

assert set(false_negatives["sample_id"]) == {
    "sample_0154", "sample_0231", "sample_0795", "sample_1189"
}
assert (false_negatives["random_forest_balanced_score"] < quality_threshold).all()

display(Image(filename=str(ROOT / "figures" / "09_false_negative_scores.png")))"""
        ),
        new_markdown_cell(
            """테스트 FAIL은 21건뿐이므로 한 건이 Recall을 4.76%p 바꾼다. FN 4건의 패턴은 후속 가설 생성용이며, 이 오류를 보고 같은 test로 재학습하거나 임계값을 바꾸지 않았다."""
        ),
        new_markdown_cell("## 5. 익명 변수 후보 — 원인 아님"),
        new_code_cell(
            """candidates = pd.read_csv(ROOT / "results" / "tables" / "feature_candidates.csv")
candidate_view = candidates[[
    "feature", "logistic_top20_frequency", "rf_top20_frequency",
    "mean_absolute_coefficient", "mean_ap_drop",
    "meets_both_methods_60pct_rule",
]].head(10)
display(candidate_view.round(4))

both_methods = candidates.loc[
    candidates["meets_both_methods_60pct_rule"], "feature"
].tolist()
assert both_methods == ["feature_059"]

display(Image(filename=str(ROOT / "figures" / "08_feature_candidate_stability.png")))"""
        ),
        new_markdown_cell(
            """`feature_059`는 Logistic top-20 15/15, RF permutation top-20 3/5로 두 방법의 60% 반복 기준을 동시에 만족했다. 그러나 변수 의미·단위가 익명화되어 있으므로 특정 센서·온도·압력·식각 조건·불량 원인으로 해석할 수 없다."""
        ),
        new_markdown_cell("### Development-only 시간 변수 안정성"),
        new_code_cell(
            """temporal_feature = json.loads(
    (ROOT / "results" / "metadata" / "temporal_feature_stability.json").read_text()
)
temporal_candidates = pd.read_csv(
    ROOT / "results" / "tables" / "temporal_feature_candidates.csv"
)
display(temporal_candidates.head(10).round(4))

feature_059_temporal = temporal_candidates.loc[
    temporal_candidates["feature"] == "feature_059"
].iloc[0]
assert temporal_feature["strict_development_pool_rows"] == 1003
assert temporal_feature["primary_test_used"] is False
assert temporal_feature["chronological_holdout_used"] is False
assert temporal_candidates["meets_both_methods_2_of_3"].sum() == 0
assert feature_059_temporal["logistic_top20_count"] == 1
assert feature_059_temporal["rf_positive_top20_count"] == 1

display(Image(filename=str(ROOT / "figures" / "10_temporal_feature_stability.png")))"""
        ),
        new_markdown_cell("## 6. 시간순 민감도 — 일반화 경고"),
        new_code_cell(
            """temporal = json.loads(
    (ROOT / "results" / "metadata" / "temporal_sensitivity.json").read_text()
)
temporal_metrics = temporal["metrics_at_train_only_quality_threshold"]
display(pd.DataFrame([temporal_metrics]).round(4))

assert temporal["train_only_threshold_selection"]["test_data_used_to_select_threshold"] is False
assert temporal_metrics["true_positive"] == 7
assert temporal_metrics["false_negative"] == 10
assert np.isclose(temporal_metrics["fail_recall"], 7 / 17)
assert np.isclose(temporal_metrics["fail_precision"], 7 / 133)"""
        ),
        new_markdown_cell(
            """동일 timestamp 내부 순서를 `sample_id`로 고정하고, 시간순 학습 데이터에서만 정한 후보 임계값 `0.068235`를 이후 기간에 적용했을 때 Recall 41.18%, Precision 5.26%, ROC-AUC 0.540, AP 0.079로 약화됐다. 이는 distribution shift 또는 temporal instability 가능성을 보여주지만 spurious correlation이 원인이라고 단정할 근거는 없다. 모델 family는 1차 무작위 분석에서 이미 선택됐으므로 완전 독립 prospective 검증은 아니다."""
        ),
        new_markdown_cell("### Shared timestamp 영향 민감도"),
        new_code_cell(
            """shared_timestamp = json.loads(
    (ROOT / "results" / "metadata" / "shared_timestamp_sensitivity.json").read_text()
)
comparison = pd.DataFrame([
    shared_timestamp["primary_full_test_metrics"],
    shared_timestamp["primary_model_on_nonshared_test_at_primary_threshold"],
], index=["full locked test", "exclude shared-timestamp test rows"])
display(comparison[[
    "fail_precision", "fail_recall", "fail_f1", "balanced_accuracy",
    "roc_auc", "average_precision", "true_negative", "false_positive",
    "false_negative", "true_positive",
]].round(4))

assert shared_timestamp["shared_timestamp_group_count"] == 11
assert shared_timestamp["removed_test_fail_count"] == 0
assert comparison.loc["full locked test", "false_negative"] == 4
assert comparison.loc["exclude shared-timestamp test rows", "false_negative"] == 4"""
        ),
        new_markdown_cell(
            """## 7. 결론과 AI 역할 경계

- 공개 익명 데이터에서 일부 FAIL score 분리 가능성은 보였으나 높은 오탐, 작은 FAIL 표본, 시간 성능 저하, batch 정보 부재로 현장 적용 근거는 부족하다.
- AI는 코드·방법론 검토와 문서 초안을 보조했다. 데이터 수·지표·혼동행렬·그래프는 Python 실행값만 사용했다.
- 사용자는 별도 환경에서 실제 Gemma 4 26B A4B API 독립 리뷰를 수행했다. [원본 출력](../results/gemma_review.md)은 변경 없이 보존했고, 과도한 단정은 사람이 기각·완화한 뒤 수용한 세 검증 의제만 Python으로 확인했다.
- 실제 비용자료가 없어 cost-optimal threshold는 계산하지 않았다.
- 없는 반도체 실무 경험, SK하이닉스 공정 분석, 수율 개선, 원인 규명은 주장하지 않는다.
- 공개 v1은 2026-08-23 Freeze했으며 추가 모델링·튜닝을 중단한다.

상세 내용은 [README](../README.md), [Quality Report](../reports/quality_report.md), [Human Decision Log](../docs/GEMMA_REVIEW_DECISIONS.md), [AI 사용 기록](../docs/AI_USAGE.md), [검증 로그](../docs/VALIDATION_LOG.md)에서 확인할 수 있다."""
        ),
    ]

    return new_notebook(
        cells=cells,
        metadata={
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "version": platform_version(),
            },
        },
    )


def platform_version() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def normalize_executed_notebook(notebook: nbformat.NotebookNode) -> None:
    font_cache_message = "Matplotlib is building the font cache; this may take a moment.\n"
    for index, cell in enumerate(notebook.cells, start=1):
        cell["id"] = f"cell-{index:02d}"
        cell.setdefault("metadata", {}).pop("execution", None)
        if cell.cell_type != "code":
            continue
        cell["outputs"] = [
            output
            for output in cell.get("outputs", [])
            if not (
                output.get("output_type") == "stream"
                and output.get("name") == "stderr"
                and "".join(output.get("text", "")) == font_cache_message
            )
        ]


def main() -> None:
    NOTEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    notebook = build_notebook()

    # The bundled python kernelspec launches `python`; ensure it resolves to the
    # exact interpreter running this builder (the project-local venv).
    interpreter_dir = str(Path(sys.executable).resolve().parent)
    os.environ["PATH"] = interpreter_dir + os.pathsep + os.environ.get("PATH", "")
    cache_root = PROJECT_ROOT / ".cache"
    for directory in (
        cache_root,
        cache_root / "matplotlib",
        cache_root / "ipython",
        cache_root / "jupyter",
    ):
        directory.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(cache_root / "matplotlib"))
    os.environ.setdefault("XDG_CACHE_HOME", str(cache_root))
    os.environ.setdefault("IPYTHONDIR", str(cache_root / "ipython"))
    os.environ.setdefault(
        "JUPYTER_CONFIG_DIR", str(cache_root / "jupyter")
    )

    client = NotebookClient(
        notebook,
        timeout=1200,
        kernel_name="python3",
        resources={"metadata": {"path": str(PROJECT_ROOT)}},
        allow_errors=False,
    )
    executed = client.execute()
    normalize_executed_notebook(executed)
    nbformat.write(executed, NOTEBOOK_PATH)
    print(f"Executed notebook saved to: {NOTEBOOK_PATH}")
    print(f"Cells: {len(executed.cells)}")


if __name__ == "__main__":
    main()
