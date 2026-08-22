# 재현·검증 로그

## 공개 Git 이력 구성

- 공개 저장소는 `secom-quality-analysis/` 폴더를 별도의 저장소 루트로 구성해 상위 작업 폴더와 이전 ZIP을 포함하지 않았다.
- 변경은 `portfolio-build` 브랜치에서 단계별로 기록하고, 작업 완료 후에만 공개 기본 브랜치 `main`으로 이름을 바꿨다.
- commit author email은 개인 메일 대신 GitHub noreply 형식을 사용했다.
- 이력은 데이터 원본 고정 → 탐색·품질 점검 → 누수 방지 분할 → baseline 모델링 → FN·시간순 분석 → Notebook·문서화 순서로 분리했다.

## 핵심 실행 명령과 결과

아래에는 상태를 바꾸거나 최종 결과를 검증한 핵심 명령을 기록했다. API key·token·cookie는 사용하거나 출력하지 않았다.

```text
git init -b portfolio-build
git commit -m "chore: pin reproducible UCI SECOM source"
git commit -m "feat: add data exploration and quality audit"
git commit -m "feat: record leakage-safe preprocessing and split"
git commit -m "feat: add explainable baseline modeling and evaluation"
git commit -m "feat: add false-negative and temporal robustness analysis"
git commit -m "docs: add executed notebook and portfolio evidence"
git branch -M main

git switch -c gemma-human-review-validation

env MPLCONFIGDIR=work/matplotlib-cache XDG_CACHE_HOME=work/cache JOBLIB_TEMP_FOLDER=work/joblib-temp \
  work/.venv/bin/python work/secom-quality-analysis-github/src/secom_analysis.py

env MPLCONFIGDIR=work/matplotlib-cache XDG_CACHE_HOME=work/cache \
  work/.venv/bin/python work/secom-quality-analysis-github/scripts/build_notebook.py

work/.venv/bin/python -m pytest -q work/secom-quality-analysis-github/tests

env UV_CACHE_DIR=work/uv-cache uv venv work/.venv --python 3.12
env UV_CACHE_DIR=work/uv-cache uv pip install --python work/.venv/bin/python -r outputs/secom-quality-analysis/requirements.txt

work/.venv/bin/python outputs/secom-quality-analysis/scripts/download_data.py

env MPLCONFIGDIR=work/matplotlib-cache XDG_CACHE_HOME=work/cache JOBLIB_TEMP_FOLDER=work/joblib-temp \
  work/.venv/bin/python outputs/secom-quality-analysis/src/secom_analysis.py

env MPLCONFIGDIR=work/matplotlib-cache XDG_CACHE_HOME=work/cache \
  work/.venv/bin/python outputs/secom-quality-analysis/scripts/build_notebook.py

env MPLCONFIGDIR=work/matplotlib-cache XDG_CACHE_HOME=work/cache \
  work/.venv/bin/python -m pytest -q outputs/secom-quality-analysis/tests

work/.venv/bin/python -m py_compile \
  outputs/secom-quality-analysis/src/secom_analysis.py \
  outputs/secom-quality-analysis/scripts/download_data.py \
  outputs/secom-quality-analysis/scripts/gemma_review.py \
  outputs/secom-quality-analysis/scripts/build_notebook.py

git diff --check

zip -r outputs/secom-quality-analysis-complete.zip \
  outputs/secom-quality-analysis -x '*/__pycache__/*' '*.pyc'

shasum -a 256 outputs/secom-quality-analysis-complete.zip
```

Human Decision 검증 추가 후 최종 자동 테스트는 `17 passed in 15.13s`였다. 실행 Notebook은 29셀 중 코드 셀 12개 모두 execution count가 있고 error output은 0개였으며 절대 로컬 경로가 포함되지 않았는지 자동 확인했다. 동일 입력으로 연속 생성한 최종 Notebook SHA-256은 두 번 모두 `e4fff09f44106b41611bd7a30c4d69ba302fd9a890985bcb9f6475135ba708b7`였다. 잠금 test의 기존 TN/FP/FN/TP와 모델·임계값은 변하지 않았다. 신규 bootstrap은 10,000회 모두 유효했고, strict temporal feature pool은 두 보호 holdout의 행·timestamp와 교집합이 0인지 테스트했다. 모든 Markdown 로컬 링크, Python 문법, Git diff whitespace도 자동 검사한다.

## 발생한 실패와 처리

| 단계 | 실패/경고 | 처리 | 결과 영향 |
|---|---|---|---|
| Git 초기화 | sandbox가 `.git` 쓰기를 처음 차단 | 사용자 승인 경로로 `git init` 실행 | 없음 |
| 작업 브랜치 | `feature/secom-quality-analysis` ref 디렉터리 생성 차단 | 승인 후 `feature-secom-quality-analysis`로 전환 | 없음 |
| `uv` 환경 | 기본 사용자 cache 쓰기 권한 없음 | workspace의 `work/uv-cache` 사용 | 없음 |
| 패키지 설치 | sandbox DNS 차단 | 승인된 네트워크로 workspace venv에만 설치 | 없음 |
| label 파싱 | regex whitespace separator가 quoted timestamp를 잘못 분리 | `sep=" "`, `skipinitialspace=True`, `quotechar`로 수정 | 원본 1,567행 정합성 재검증 |
| 첫 분석 병렬화 | sandbox에서 process semaphore 정보 접근 차단 | 모든 sklearn job을 `n_jobs=1`로 고정 | 계산 내용·seed·fold 변화 없음, 시간만 증가 |
| matplotlib cache | 기본 home/cache 쓰기 경고 | workspace cache 환경변수 사용 | 그래프/수치 영향 없음 |
| AP/PR-AUC 용어 | 초기에는 AP만 기록 | AP와 사다리꼴 PR-AUC를 별도 계산 | 모델 선택은 사전 규칙대로 AP 유지 |
| 시간순 민감도 | 초기에는 0.5 임계값만 평가 | 시간순 train OOF 후보 임계값을 별도 선택 | 시간 일반화 한계를 더 엄격히 기록 |
| 동일 timestamp 정렬 | 기본 정렬은 같은 timestamp 내부 순서를 명시하지 않아 구현에 따라 시간순 경계 결과가 달라질 수 있었음 | `timestamp → sample_id` stable 정렬을 코드에 고정하고 전체 산출물 재계산 | 잠금 random test는 불변, 시간순 수치는 새 실행값으로 교체 |
| 원본 hash | 최초 스크립트는 받은 파일 hash만 manifest에 기록 | 공식 취득본의 ZIP·추출 파일 SHA-256을 코드에 고정하고 불일치 시 중단 | 이후 원본 변경·오염을 자동 차단 |
| Notebook 첫 실행 | sandbox가 Jupyter 로컬 커널 포트 생성을 차단 | 승인된 로컬 커널로 모든 셀 실행 | 외부 전송 없음, 계산 결과 영향 없음 |
| Notebook 재실행 경로 | `notebooks/`에서 직접 Run All하면 처음에는 cwd assertion 실패 | 현재 폴더와 상위 폴더에서 프로젝트 루트를 탐색 | 프로젝트 루트와 notebook 폴더 양쪽에서 재실행 통과 |
| Jupyter 경고 | 로컬 커널의 임시 TCP 연결이 암호화되지 않았다는 경고 | localhost에서만 일회성 실행하고 결과에 secret·로컬 경로가 없는지 scan | 수치 영향 없음 |
| Human Decision Notebook 첫 실행 | sandbox가 로컬 Jupyter kernel port bind를 차단 | 승인된 localhost 커널로 29셀을 다시 실행 | 외부 전송 없음, 수치 영향 없음 |

## 최종 검증 범위

- 공식 원본 SHA-256과 feature/label 행 수
- 원본 ZIP·추출 파일이 코드에 고정한 SHA-256과 일치하는지 여부
- PASS/FAIL 라벨 매핑과 결측·상수·중복·무한값
- 고정 split 재현성과 train/test ID·label·timestamp 정합성
- confusion matrix 순서 `[[TN, FP], [FN, TP]]`
- Precision, Recall, F1, Balanced Accuracy, ROC-AUC, AP, PR-AUC 재계산
- threshold가 train-only OOF에서 선택됐는지 여부
- FN 4개 ID와 score/threshold 관계
- 시간순 threshold와 TN/FP/FN/TP
- 고정 test 예측의 10,000회 true-label-stratified bootstrap CI
- shared timestamp test 행 제외와 양쪽 purge/refit 민감도
- 두 holdout과 보호 timestamp를 제외한 1,003행의 expanding-time 변수 안정성
- temporal Logistic/RF raw fold table과 2-of-3 집계 재계산
- 변수 후보 익명 이름과 both/either 60% 규칙
- 모든 Markdown 로컬 링크
- Python 문법 compile
- Notebook 코드 셀 12개 실행 완료와 error output 0건

## 정확한 사용자 산출물 파일

```text
.gitattributes
.gitignore
README.md
requirements.txt
requirements-lock.txt
requirements-gemma.txt

data/raw/README.md
data/raw/secom.data
data/raw/secom.names
data/raw/secom.zip
data/raw/secom_labels.data
data/raw/source_manifest.json

docs/AI_USAGE.md
docs/GEMMA_OPTIONAL.md
docs/GEMMA_REVIEW_DECISIONS.md
docs/VALIDATION_LOG.md

figures/01_class_distribution.png
figures/02_missingness_top20.png
figures/03_cv_model_comparison.png
figures/04_test_model_comparison.png
figures/05_confusion_matrices.png
figures/06_precision_recall_curves.png
figures/07_roc_curves.png
figures/08_feature_candidate_stability.png
figures/09_false_negative_scores.png
figures/10_temporal_feature_stability.png

models/selected_model.joblib
models/selected_model_metadata.json

notebooks/secom_quality_analysis.ipynb

prompts/gemma_review_prompt.md

reports/application_sentences.md
reports/quality_report.md

scripts/build_notebook.py
scripts/download_data.py
scripts/gemma_review.py

src/secom_analysis.py

tests/conftest.py
tests/test_secom_analysis.py

results/run_summary.json
results/metadata/dataset_summary.json
results/metadata/false_negative_summary.json
results/metadata/runtime_versions.json
results/metadata/split_summary.json
results/metadata/shared_timestamp_sensitivity.json
results/metadata/temporal_feature_stability.json
results/metadata/temporal_sensitivity.json
results/metadata/test_metric_uncertainty.json
results/metadata/threshold_selection.json
results/tables/cv_metrics_by_fold.csv
results/tables/cv_metrics_summary.csv
results/tables/data_quality_by_feature.csv
results/tables/data_quality_by_sample.csv
results/tables/false_negatives.csv
results/tables/feature_candidates.csv
results/tables/logistic_feature_stability_by_fold.csv
results/tables/logistic_feature_stability_summary.csv
results/tables/rf_impurity_importance_secondary.csv
results/tables/rf_permutation_stability_by_fold.csv
results/tables/rf_permutation_stability_summary.csv
results/tables/split_assignment.csv
results/tables/test_fail_cases.csv
results/tables/test_metrics.csv
results/tables/test_predictions.csv
results/tables/test_metric_bootstrap_ci.csv
results/tables/temporal_feature_candidates.csv
results/tables/temporal_logistic_feature_stability_by_fold.csv
results/tables/temporal_logistic_feature_stability_summary.csv
results/tables/temporal_rf_permutation_stability_by_fold.csv
results/tables/temporal_rf_permutation_stability_summary.csv
```

프로젝트 밖의 사용자 파일은 수정하거나 삭제하지 않았다. 생성된 Python cache만 압축 전에 제거했다.

## 남은 선택 작업

- 필수 분석·문서 작업은 완료했다.
- 프로젝트 환경의 Gemma 설치/API 호출은 하지 않았다. 사용자가 외부 검토의 6개 요약을 제공해 Human Decision Log로 판정했으며, 원문 `results/gemma_review.md`는 제공되지 않아 복원하지 않았다.
- 지원자는 제출 전에 코드를 직접 재실행하고, 지원서 문장을 자신의 판단과 표현으로 검토해야 한다.
