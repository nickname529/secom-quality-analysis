# 사용자 제공 Gemma 지적 요약에 대한 Human Decision Log

## 목적과 출처 경계

이 문서는 AI 출력을 그대로 채택한 기록이 아니라, 사용자가 전달한 Gemma 지적을 Python 결과와 대조해 사람이 판정한 기록이다. 최종 판단 권한은 사람에게 있으며 모든 신규 수치의 source of truth는 `results/`의 JSON·CSV다.

- 사용자 제공 진술상 검토 모델: Gemma 4 26B A4B
- 전달된 근거: 사용자가 2026-08-22 메시지에서 제공한 6개 지적 요약과 판정 기준
- 원문 상태: 요청에 언급된 `results/gemma_review.md`는 작업공간과 GitHub `main`에 존재하지 않았다.
- 인용 상태: 아래 “지적 요약”은 Gemma 원문의 인용·복원이 아니라 **사용자 제공 요약의 재서술**이다.
- 로컬 실행 상태: 이 프로젝트 환경에서 Gemma를 설치하거나 API로 호출하지 않았다.
- 변경 금지선: 잠금 test를 보고 1차 모델 family나 임계값을 다시 선택하지 않았다.

## 판정 기준

- `ACCEPT`: 지적의 관찰 또는 위험이 로컬 근거와 일치해 반영한다.
- `REJECT`: 원인·비용·적용 가능성처럼 현재 자료로 입증할 수 없는 단정은 반영하지 않는다.
- `PARTIAL ACCEPT`: 위험 가능성은 인정하지만 확인 가능한 범위로 좁혀 반영한다.
- `MAINTAIN`: 이미 적용된 통제를 그대로 유지한다.

## 판정 요약

| ID | 사용자 제공 지적 요약(원문 아님) | 인간 판정 | 핵심 이유 | 실제 조치 |
|---|---|---|---|---|
| G-01 | 시간순 holdout 성능 저하는 중요하며 spurious correlation일 수 있다. | 성능 저하 `ACCEPT`; 원인 단정 `REJECT` | 저하는 실측됐지만 원인을 식별할 lot·장비·recipe·변수 의미가 없다. | distribution shift 또는 temporal instability 가능성으로 표현을 제한했다. |
| G-02 | 잠금 test FAIL 21개라 불확실성이 크고 지표 신뢰가 제한된다. | 불확실성 `ACCEPT`; 모든 지표 무효 `REJECT` | 고정 test의 조건부 추정치는 유효하지만 구간이 넓고 외부 일반화 근거는 아니다. | 10,000회 bootstrap 95% CI를 추가했다. |
| G-03 | Precision 10.49%, FP 145개는 운영 trade-off 검토가 필요하다. | trade-off `ACCEPT`; 현장 불가능·비용 발생 단정 `REJECT` | 추가확인 후보가 많다는 사실은 확인되지만 검사·공정중단 비용 자료가 없다. | 후보 수를 정량 기록하고 cost-optimal threshold는 Future Work로 남겼다. |
| G-04 | train/test에 같은 timestamp가 있어 미지의 그룹 의존성이 있을 수 있다. | `PARTIAL ACCEPT` | timestamp가 batch라는 증거는 없지만 알려진 11개 중복 그룹의 영향은 점검할 수 있다. | 중복 test 행 제외 및 양쪽 purge/refit 민감도 검사를 추가했다. |
| G-05 | 변수 후보의 시간 안정성이 확인되지 않았다. | `ACCEPT` | 기존 후보는 random-train CV의 반복성만 보여 시간 안정성을 입증하지 않았다. | 두 holdout을 보호한 development-only expanding-time 검증을 추가했다. |
| G-06 | 익명 feature를 공정 원인으로 해석하면 안 된다. | `ACCEPT · MAINTAIN` | 변수명·단위·장비·recipe 정보가 없고 예측 연관성은 인과가 아니다. | 기존 인과 과대해석 금지 문구를 유지하고 시간 결과에도 같은 제한을 적용했다. |

## G-01. 시간순 성능 저하와 원인 표현

### 지적 요약

시간순 holdout 결과가 무작위 holdout보다 크게 약하며, 이를 spurious correlation의 증거로 볼 수 있다는 취지다.

### Python 근거

[`temporal_sensitivity.json`](../results/metadata/temporal_sensitivity.json)의 시간순 후보 임계값 결과는 Recall `0.411765`, Precision `0.052632`, Balanced Accuracy `0.493761`, ROC-AUC `0.539909`, AP `0.079034`다. 동일 timestamp 내부 순서는 `sample_id`로 고정했다. 무작위 잠금 test의 Recall `0.809524`, Precision `0.104938`, ROC-AUC `0.759142`, AP `0.228697`보다 낮다.

### 인간 판정과 조치

- 성능 저하 관찰: `ACCEPT`
- spurious correlation이 원인이라는 단정: `REJECT`
- 이유: 성능 저하는 실제지만 원인은 분포 변화, 시간 불안정성, 미관측 장비·lot·recipe 변화, 표본 변동 등 여러 가능성이 있다. 공개 데이터에는 이를 구분할 근거가 없다.
- 문서 조치: “spurious correlation이 원인” 대신 **distribution shift 또는 temporal instability 가능성**으로 제한한다.
- 1차 모델·임계값 변경: 없음

## G-02. FAIL 21개의 불확실성

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

### 지적 요약

익명 변수를 특정 센서·온도·압력·식각 조건이나 FAIL 원인으로 해석하면 안 된다는 취지다.

### 인간 판정과 조치

- 판정: `ACCEPT · MAINTAIN`
- 기존 README·보고서·코드 산출물은 `feature_059`를 예측 연관성의 후속 조사 후보로만 다뤘다.
- 신규 시간 안정성 결과에도 같은 경계를 적용한다. 안정성은 인과가 아니며, 불안정성도 spurious correlation의 원인을 입증하지 않는다.

## 종합 Human Decision

- 1차 Random Forest 선택: 유지
- 1차 train-only OOF 후보 임계값 `0.0609387335`: 유지
- 잠금 test 수치: 변경 없음
- test 결과를 본 뒤 모델·임계값 재선택: 없음
- 임의 비용 기반 threshold 최적화: 없음
- 추가된 근거: bootstrap CI, shared timestamp 민감도, development-only 시간 변수 안정성
- 강화된 한계: 작은 FAIL 표본, distribution shift/temporal instability 가능성, 변수 시간 안정성 미확인, 미관측 lot/batch 의존성

Gemma 지적은 분석의 반론 입력으로 사용했지만, 최종 결론과 문구는 Python 결과와 사람이 결정했다.
