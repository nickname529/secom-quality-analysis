# Gemma 4 26B A4B 독립 리뷰에 대한 Human Decision Log

## 목적과 출처 경계

이 문서는 실제 Gemma API 독립 리뷰를 그대로 채택한 기록이 아니라, 보존된 원문을 Python 결과와 대조해 사람이 판정한 기록이다. 최종 판단 권한은 사람에게 있으며 모든 수치의 source of truth는 `results/`의 Python JSON·CSV다.

- 원문 evidence: [`results/gemma_review.md`](../results/gemma_review.md)
- 원문 표기 모델: `gemma-4-26b-a4b-it` (Gemma 4 26B A4B)
- 원문 생성 시각: `2026-08-22T13:59:07.631883+00:00` UTC
- 실행 provenance: 사용자가 별도 환경에서 실제 Gemma API 독립 리뷰를 수행해 원본 출력 파일을 제공했다. 이 저장소의 Python 수치 산출 파이프라인에는 Gemma가 참여하지 않았다.
- 원문 무결성: 5,143 bytes, SHA-256 `68fde4ed803ce0c6f5de40fa90b9dfabfab5bf39122c4b198de9997ffa14ce9d`. 원문은 내용 변경·교정·미화 없이 수록했다.
- 수치 시점 경계: 원문은 당시 시간순 ROC-AUC `0.514`를 검토했다. 이후 동일 timestamp 내부 정렬을 `timestamp → sample_id`로 고정한 최종 Python 재계산값은 `0.539909`이며, 원문을 소급 수정하지 않았다.
- 변경 금지선: 잠금 test를 보고 1차 모델 family나 임계값을 다시 선택하지 않았다. 이번 evidence PR에서는 신규 분석·재학습·튜닝을 하지 않는다.

## 판정 기준

- `ACCEPT`: 지적의 관찰 또는 위험이 로컬 근거와 일치해 반영한다.
- `REJECT`: 원인·비용·적용 가능성처럼 현재 자료로 입증할 수 없는 단정은 반영하지 않는다.
- `PARTIAL ACCEPT`: 위험 가능성은 인정하지만 확인 가능한 범위로 좁혀 반영한다.
- `MAINTAIN`: 이미 적용된 통제를 그대로 유지한다.

## 판정 요약

| ID | 원본 Gemma 리뷰의 대응 지적 | 인간 판정 | 핵심 이유 | 실제 조치 |
|---|---|---|---|---|
| G-01 | §1 Fatal Issues의 **모델의 시간적 일반화 능력 상실**, §5 결론 | 성능 저하 `ACCEPT`; spurious correlation·미래 사용 불가 단정 `REJECT` | 저하는 실측됐지만 원인을 식별할 lot·장비·recipe·변수 의미가 없다. | distribution shift 또는 temporal instability 가능성으로 표현을 제한했다. |
| G-02 | §1의 **통계적 유의성 결여**, §4 Priority 2, §5 결론 | 불확실성 `ACCEPT`; 모든 지표 무효 `REJECT` | 고정 test의 조건부 추정치는 유효하지만 구간이 넓고 외부 일반화 근거는 아니다. | 10,000회 bootstrap 95% CI를 추가했다. |
| G-03 | §1의 **임계값 선택의 불균형**, §4 Priority 4, §5 결론 | trade-off `ACCEPT`; 현장 불가능·비용 발생 단정 `REJECT` | 후보 수와 FP는 확인되지만 검사·공정중단 비용 자료가 없다. | 후보 수와 FP를 기록하고 cost-optimal threshold는 Future Work로 남겼다. |
| G-04 | §2의 **데이터 누수 가능성 (Timestamp Overlap)**, §4 Priority 5 | `PARTIAL ACCEPT` | timestamp가 batch라는 증거는 없지만 알려진 11개 중복 그룹의 영향은 점검할 수 있다. | 중복 test 행 제외 및 양쪽 purge/refit 민감도 검사를 추가했다. |
| G-05 | §2의 **변수 안정성 과장**, §4 Priority 1 | `ACCEPT` | 기존 후보는 random-train CV의 반복성만 보여 시간 안정성을 입증하지 않았다. | 두 holdout을 보호한 development-only expanding-time 검증을 추가했다. |
| G-06 | §2의 **인과관계 오인 위험** | `ACCEPT · MAINTAIN` | 변수명·단위·장비·recipe 정보가 없고 예측 연관성은 인과가 아니다. | 기존 인과 과대해석 금지 문구를 유지하고 시간 결과에도 같은 제한을 적용했다. |

## G-01. 시간순 성능 저하와 원인 표현

**원본 대응:** §1 치명적 문제의 “모델의 시간적 일반화 능력 상실 (Temporal Collapse)”과 §5 결론 문장.

### 지적 요약

시간순 holdout 결과가 무작위 holdout보다 크게 약하며, 이를 spurious correlation의 결과이자 미래 사용 불가의 근거로 단정한 지적이다.

### Python 근거

원본 리뷰에는 당시 출력의 시간순 ROC-AUC `0.514`가 적혀 있다. 이후 tie-order 재현성을 위해 동일 timestamp 내부 순서를 `sample_id`로 고정한 최종 [`temporal_sensitivity.json`](../results/metadata/temporal_sensitivity.json)의 결과는 Recall `0.411765`, Precision `0.052632`, Balanced Accuracy `0.493761`, ROC-AUC `0.539909`, AP `0.079034`다. 무작위 잠금 test의 Recall `0.809524`, Precision `0.104938`, ROC-AUC `0.759142`, AP `0.228697`보다 낮다. 최종 수치가 달라졌어도 성능 저하 방향은 유지되며, 원본 evidence는 당시 출력 그대로 보존한다.

### 인간 판정과 조치

- 성능 저하 관찰: `ACCEPT`
- spurious correlation이 원인이라는 단정: `REJECT`
- 이유: 성능 저하는 실제지만 원인은 분포 변화, 시간 불안정성, 미관측 장비·lot·recipe 변화, 표본 변동 등 여러 가능성이 있다. 공개 데이터에는 이를 구분할 근거가 없다.
- 문서 조치: “spurious correlation이 원인” 대신 **distribution shift 또는 temporal instability 가능성**으로 제한한다.
- 1차 모델·임계값 변경: 없음

## G-02. FAIL 21개의 불확실성

**원본 대응:** §1의 “통계적 유의성 결여”, §4 Priority 2 “Bootstrapping for Confidence Intervals”, §5 결론 문장.

### 지적 요약

잠금 test의 FAIL이 21개뿐이어서 지표 불확실성이 크며, 이를 이유로 모든 지표를 무효로 볼 수 있다는 취지다.

### Python 근거

고정 RF score와 고정 임계값 `0.0609387335`에 대해 PASS 293개와 FAIL 21개를 각각 복원추출하는 true-label-stratified paired bootstrap을 `10,000`회 수행했다. seed는 `20260822`, 구간은 95% percentile CI다. 모델 재학습과 임계값 재선택은 하지 않았다.

| 지표 | 점추정 | 95% bootstrap CI |
|---|---:|---:|
| FAIL Recall | 0.8095 | 0.6190–0.9524 |
| FAIL Precision | 0.1049 | 0.0818–0.1268 |
| FAIL F1 | 0.1858 | 0.1444–0.2235 |
| Balanced Accuracy | 0.6573 | 0.5621–0.7390 |
| ROC-AUC | 0.7591 | 0.6439–0.8632 |
| AP | 0.2287 | 0.1402–0.4267 |

정확한 값은 [`test_metric_bootstrap_ci.csv`](../results/tables/test_metric_bootstrap_ci.csv), 방법·seed·조건은 [`test_metric_uncertainty.json`](../results/metadata/test_metric_uncertainty.json)에 있다.

### 인간 판정과 조치

- 불확실성이 크다는 지적: `ACCEPT`
- 모든 지표가 무효라는 표현: `REJECT`
- 이유: 지표는 이 고정 test에서 계산된 조건부 추정치로서 유효하다. 다만 구간이 넓고 학습·모델선택·임계값선택 불확실성이나 외부 기간 변동은 포함하지 않는다.
- 1차 모델·임계값 변경: 없음

## G-03. Precision·False Positive와 비용 주장

**원본 대응:** §1의 “임계값 선택의 불균형”, §4 Priority 4 “Precision-Recall Curve Cost Analysis”, §5 결론 문장.

### 지적 요약

후보 임계값의 Precision `10.49%`와 FP `145`개가 운영 trade-off를 만들며, 현장 도입이 어렵거나 공정중단 비용을 유발할 수 있다는 취지다.

### Python 근거

잠금 test 314건 중 162건이 FAIL 후보로 분류됐고, 그중 실제 FAIL은 17건, PASS 오탐은 145건이다. 따라서 추가확인 후보 중 실제 FAIL 비율은 `17/162 = 10.49%`다.

### 인간 판정과 조치

- 누락 감소와 추가확인 후보 증가의 trade-off: `ACCEPT`
- “현장 도입 불가능”, “공정중단 비용 발생” 단정: `REJECT`
- 이유: 검사 단가, 처리시간, 공정중단 규칙, FAIL 유출 비용, 수율 영향 자료가 없다.
- 임의 비용을 넣은 cost-optimal threshold 계산: 수행하지 않음
- Future Work: 실제 비용행렬과 운영 제약을 먼저 확보한 뒤 threshold를 검토한다.

## G-04. Shared timestamp 영향

**원본 대응:** §2의 “데이터 누수 가능성 (Timestamp Overlap)”과 §4 Priority 5 “Shared Timestamp Impact Test”.

### 지적 요약

무작위 train/test 양쪽에 같은 timestamp가 있어 미지의 제조 그룹 의존성이 성능에 영향을 줬을 가능성이 있다는 취지다.

### Python 근거

[`shared_timestamp_sensitivity.json`](../results/metadata/shared_timestamp_sensitivity.json)에 따르면 정확히 같은 timestamp가 양쪽에 걸친 그룹은 11개이며 train 11행과 test 11행은 모두 PASS다. 고정 모델·고정 임계값에서 해당 test 11행을 제외한 결과는 다음과 같다.

| 평가 | Recall | Precision | Balanced Acc. | ROC-AUC | AP | TN / FP / FN / TP |
|---|---:|---:|---:|---:|---:|---:|
| 전체 잠금 test | 0.8095 | 0.1049 | 0.6573 | 0.7591 | 0.2287 | 148 / 145 / 4 / 17 |
| shared timestamp test 행 제외 | 0.8095 | 0.1090 | 0.6583 | 0.7595 | 0.2325 | 143 / 139 / 4 / 17 |

제외된 11행은 TN 5개와 FP 6개였다. 알려진 exact timestamp 중복을 제외해도 Recall과 FN은 변하지 않았고 다른 지표는 극소폭 좋아졌다. 별도로 양쪽 shared 그룹을 제거해 재학습하고 purged-train OOF에서만 임계값을 다시 정한 민감도도 JSON에 기록했지만, 이는 1차 결과를 대체하지 않는다.

### 인간 판정과 조치

- exact timestamp 영향 가능성: `PARTIAL ACCEPT`
- 알려진 11개 중복이 1차 성능을 낙관적으로 부풀렸다는 주장: 이번 민감도에서는 근거 없음
- 남은 위험: timestamp가 다른 동일 lot/batch 의존성은 식별자가 없어 통제할 수 없다. timestamp 자체가 batch라는 주장도 하지 않는다.
- 1차 모델·임계값 변경: 없음

## G-05. 변수 후보의 시간 안정성

**원본 대응:** §2의 “변수 안정성 과장 (Feature Stability Illusion)”과 §4 Priority 1 “Feature Importance Temporal Stability Check”.

### 지적 요약

기존 `feature_059` 후보는 random-train CV 반복성만 확인됐고 시간에 따른 안정성이 검증되지 않았다는 취지다.

### Python 근거와 누수 통제

[`temporal_feature_stability.json`](../results/metadata/temporal_feature_stability.json)은 다음 범위만 사용한다.

- primary random test 314행과 chronological future holdout 314행을 보호한다.
- 두 보호 집합의 합집합 557행(FAIL 37)은 사용하지 않는다.
- 보호 집합과 timestamp가 같은 development 후보 7행도 추가 제외한다.
- 최종 strict development pool은 1,003행(FAIL 67), unique timestamp 987개다.
- unique timestamp를 4개 연속 block으로 나누고 3개 expanding-time fold를 만든다.
- 각 fold는 `max(train time) < min(validation time)`이며 공유 timestamp는 0개다.
- Logistic은 과거 학습 구간의 표준화 계수 top-20, RF는 바로 다음 validation 구간의 **양수 AP permutation drop** top-20을 기록한다.

세 fold의 validation FAIL은 각각 15, 9, 9개다. 두 방법에서 모두 2/3회 이상 top-20에 든 변수는 **0개**였다. `feature_059`는 Logistic 1/3, RF 1/3이었다. 상세 결과는 [`temporal_feature_candidates.csv`](../results/tables/temporal_feature_candidates.csv)에 있다.

### 인간 판정과 조치

- 시간 안정성 미확인 지적: `ACCEPT`
- 기존 random-CV 예측 연관성 자체의 소급 무효화: 하지 않음
- 새 결론: `feature_059`는 기존 random-CV 후속 조사 후보지만, 이번 development-only 검사에서는 **시간 안정성이 확인되지 않았다**.
- 원인 해석: 금지 유지
- 1차 모델·임계값 변경: 없음

## G-06. 익명 feature의 인과 해석

**원본 대응:** §2의 “인과관계 오인 위험”.

### 지적 요약

익명 변수를 특정 센서·온도·압력·식각 조건이나 FAIL 원인으로 해석하면 안 된다는 취지다.

### 인간 판정과 조치

- 판정: `ACCEPT · MAINTAIN`
- 기존 README·보고서·코드 산출물은 `feature_059`를 예측 연관성의 후속 조사 후보로만 다뤘다.
- 신규 시간 안정성 결과에도 같은 경계를 적용한다. 안정성은 인과가 아니며, 불안정성도 spurious correlation의 원인을 입증하지 않는다.

## 원본의 추가 검증 제안 처리

원본 §4의 다섯 제안을 전부 수행한 것은 아니다. 사람이 근거·우선순위·허용 범위를 검토한 뒤 다음처럼 처리했다.

| 원본 제안 | 대응 판정 | 처리 상태 |
|---|---|---|
| Priority 1: Feature Importance Temporal Stability Check | G-05 `ACCEPT` | 완료. 보호 holdout을 쓰지 않은 expanding-time 검증으로 제한했다. |
| Priority 2: Bootstrapping for Confidence Intervals | G-02 `ACCEPT` | 완료. 고정 score·고정 threshold의 조건부 95% CI만 계산했다. |
| Priority 3: FAIL Clustering Analysis | 별도 채택 안 함 | 수행하지 않았다. 사용자가 승인한 세 우선 검증에 포함되지 않았고, 시간 집중이 공정 변화를 뜻한다는 인과 구분도 공개 변수만으로 할 수 없다. |
| Priority 4: Precision-Recall Curve Cost Analysis | G-03의 비용 단정 `REJECT` | 수행하지 않았다. 실제 FP/FN 비용·검사시간·중단 규칙 없이 임의 비용 최적화를 하지 않고 Future Work로 남겼다. |
| Priority 5: Shared Timestamp Impact Test | G-04 `PARTIAL ACCEPT` | 완료. 알려진 exact timestamp 중복 범위만 민감도 검사했다. |

원본 §3의 “잘 통제된 점” 세 항목은 G-01~G-06 비판 ID의 직접 대응 항목이 아니라 보조 평가다. Pipeline 내부 전처리, 불확실성 공개, 기본 임계값과 후보 임계값의 분리 원칙은 그대로 유지했다.

## 종합 Human Decision

- 1차 Random Forest 선택: 유지
- 1차 train-only OOF 후보 임계값 `0.0609387335`: 유지
- 잠금 test 수치: 변경 없음
- test 결과를 본 뒤 모델·임계값 재선택: 없음
- 임의 비용 기반 threshold 최적화: 없음
- 추가된 근거: bootstrap CI, shared timestamp 민감도, development-only 시간 변수 안정성
- 강화된 한계: 작은 FAIL 표본, distribution shift/temporal instability 가능성, 변수 시간 안정성 미확인, 미관측 lot/batch 의존성
- Freeze: 이 evidence PR을 checkpoint로 공개 v1을 `FROZEN` 상태로 두고 추가 모델링·튜닝·임계값 재선택을 중단한다.

Gemma 지적은 분석의 반론 입력으로 사용했지만, 최종 결론과 문구는 Python 결과와 사람이 결정했다.
