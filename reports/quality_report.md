# SECOM 공개 데이터 품질분석 보고서

**범위:** 공개·익명 반도체 제조 데이터의 탐색적 FAIL 스크리닝

**작성 기준일:** 2026-08-22

**상태:** 분석 `COMPLETE` / 공개 v1 결과 `FROZEN` (2026-08-23) / 생산 적용 근거 아님

## 1. 목적과 데이터 품질

의사결정 질문은 “높은 Accuracy가 아니라 실제 FAIL을 얼마나 놓치지 않으면서 추가확인 후보 수를 함께 볼 것인가?”다. [UCI SECOM](https://archive.ics.uci.edu/dataset/179/secom) 공식 원본 1,567건을 사용했다. UCI 메타데이터는 591 features라고 적지만 `secom.data`의 모든 행은 실제 590개 값을 가지므로 원본 구조를 따랐다. 라벨은 PASS 1,463건과 FAIL 104건으로 FAIL 비율이 6.64%다.

전체 924,530개 입력 셀 중 결측은 41,951개(4.54%)였고, 590개 변수 중 538개에 결측이 있었다. 관측값 기준 상수 변수는 116개, 전부 결측인 변수와 무한값, exact duplicate feature row는 각각 0개였다. 변수명·단위·장비·lot/batch 정보는 공개되지 않았다.

## 2. 누수 방지와 평가 설계

seed 42로 train 1,253건(FAIL 83)과 잠금 test 314건(FAIL 21)을 80/20 층화 분리했다. timestamp는 입력에서 제외했다. median 결측 대치, 분산 0 변수 제거, Logistic 표준화는 모두 Pipeline 안에서 각 학습 fold에만 fit했다.

Dummy, class-weighted Logistic Regression, class-weighted Random Forest를 train-only 5-fold × 3회 반복 CV의 동일 fold에서 비교했다. 모델 family는 mean Average Precision(AP) 기준으로 정했으며 RF 0.193±0.062, Logistic 0.161±0.062였다. RF가 paired 15 fold 중 8개에서만 더 높았으므로 압도적 우위가 아니라 **사전 규칙에 따른 선택**이다. 이후 RF의 train-only 5-fold OOF score에서 “FAIL Recall 0.80 이상을 만족하는 임계값 중 Precision 최대”라는 분석 가정으로 후보 임계값 0.060939를 정했다. test는 모델·임계값 선택에 사용하지 않았다.

단, 동일 timestamp 11개 그룹(22행)이 무작위 train/test 양쪽에 걸쳤다. timestamp가 batch라는 근거는 없지만 제조 군집 proxy일 가능성을 배제할 수 없으며, 이를 확인할 lot/batch ID가 없다.

## 3. 잠금 테스트 결과

| 평가 | FAIL Precision | FAIL Recall | FAIL F1 | Balanced Acc. | ROC-AUC | AP | PR-AUC¹ | TN / FP / FN / TP |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Dummy @ 0.5 | 0.000 | 0.000 | 0.000 | 0.500 | 0.500 | 0.067 | 0.533 | 293 / 0 / 21 / 0 |
| Logistic @ 0.5 | 0.154 | 0.286 | 0.200 | 0.587 | 0.647 | 0.122 | 0.108 | 260 / 33 / 15 / 6 |
| RF @ 0.5 | 0.000 | 0.000 | 0.000 | 0.500 | 0.759 | 0.229 | 0.207 | 293 / 0 / 21 / 0 |
| RF @ 0.060939 | 0.105 | 0.810 | 0.186 | 0.657 | 0.759 | 0.229 | 0.207 | 148 / 145 / 4 / 17 |

¹ AP와 사다리꼴 PR-AUC는 보간 정의가 다르다. 모든 score가 같은 Dummy의 PR-AUC 0.533은 끝점 선형 보간의 영향이 커 비교 주지표로 쓰지 않았고 AP를 우선했다.

RF @ 0.5는 Accuracy 93.31%였지만 FAIL 21건을 모두 놓쳤다. 후보 임계값은 FAIL 17건을 찾아 Recall 80.95%를 만들었으나 PASS 145건을 오탐해 314건 중 162건을 추가확인 후보로 분류했다. Precision은 10.49%에 그쳤다. 즉, 이 결과는 성능 향상 주장이 아니라 **FN 감소와 추가확인 후보 증가의 trade-off**다. 테스트 FAIL 한 건이 Recall을 4.76%p 바꾸며 Recall Wilson 구간도 60.00~92.33%로 넓다.

고정 test 예측의 true-label-stratified bootstrap 10,000회 95% 구간은 Recall 0.619~0.952, Precision 0.082~0.127, Balanced Accuracy 0.562~0.739, ROC-AUC 0.644~0.863, AP 0.140~0.427이었다. 작은 FAIL 표본 때문에 불확실성이 크지만 모든 지표가 무효인 것은 아니다. 이 구간은 고정 모델·임계값과 관측 test 유병률에 조건부이며 학습·선택 불확실성이나 외부 기간 변동은 포함하지 않는다.

![혼동행렬](../figures/05_confusion_matrices.png)

## 4. False Negative와 변수 후보

후보 임계값에서 FN은 `sample_0231`, `sample_0154`, `sample_0795`, `sample_1189` 4건이었다. FN의 결측 수 중앙값은 26, TP는 24였지만 FN이 4건뿐이라 결측과 누락의 관계를 주장하지 않았다. 각 FN의 score, 임계값 거리, 학습 중앙값 대비 robust deviation을 기록했으며 이 오류를 보고 모델을 다시 fit하거나 같은 test 임계값을 조정하지 않았다.

변수 후보는 test가 아닌 train CV에서만 산출했다. Logistic top-20 15/15와 RF permutation top-20 3/5를 동시에 만족한 `feature_059`가 두 방법에서 가장 반복적으로 나타났다. 그러나 이는 익명 변수의 **예측 연관성 후보**이며 특정 센서, 온도, 압력, 식각 조건, 불량 원인이라고 해석할 근거가 없다.

시간 안정성은 별도로 검사했다. primary test와 미래 holdout 557행을 보호하고 같은 timestamp의 development 후보 7행도 제외한 1,003행만 사용했다. 세 expanding-time fold에서 두 방법 모두 2/3회 이상 top-20에 든 변수는 0개였고, `feature_059`도 Logistic과 RF에서 각각 1/3회였다. 따라서 기존 random-CV 연관성 후보는 유지하되 **시간 안정성이 확인됐다고 주장하지 않는다**.

## 5. 시간 일반화와 결론

동일 timestamp의 순서를 `sample_id`로 고정한 뒤, 시간순 학습 1,253건(FAIL 87)의 OOF에서 별도 후보 임계값 0.068235를 정해 이후 314건(FAIL 17)에 적용했다. 결과는 TN 171 / FP 126 / FN 10 / TP 7, Recall 0.412, Precision 0.053, Balanced Accuracy 0.494, ROC-AUC 0.540, AP 0.079였다. 무작위 holdout보다 약화돼 distribution shift 또는 temporal instability 가능성을 보였지만 spurious correlation이 원인이라고 단정하지 않는다. 모델 family가 1차 무작위 분석에서 이미 선택됐으므로 이 검사는 완전 독립 prospective 평가가 아닌 탐색적 민감도 검사다.

동일 timestamp 11개 그룹의 test 11행은 모두 PASS였다. 고정 모델·임계값에서 이를 제외해도 Recall 0.810과 FN 4건은 동일했고 Precision은 0.105에서 0.109로 소폭 높아졌다. 알려진 중복이 결과를 낙관적으로 부풀린 정황은 없지만 timestamp가 다른 동일 lot/batch 의존성은 식별자 부재로 통제할 수 없다.

**결론:** 공개 익명 데이터에서 FAIL score의 일부 분리 가능성과 임계값 trade-off를 확인했지만, FP 145건·작은 FAIL 표본·시간 성능 저하·변수 시간 안정성 미확인·batch 정보 부재 때문에 운영 적용 근거는 부족하다. 비용자료가 없으므로 임의 비용으로 cost-optimal threshold를 계산하지 않았다. 실제 비용 기준, lot/batch 그룹 분할, 외부 기간 검증, 확률 calibration, 변수 정의 확인은 동결된 v1에서 수행하지 않은 후속 연구 제안이다. 현재 결과로 SK하이닉스 공정 원인 규명, 수율 개선, 현장 적용을 주장하지 않는다.

## 6. AI 반론과 사람의 판정

사용자는 별도 환경에서 실제 Gemma 4 26B A4B API 독립 리뷰를 수행했다. [`원본 출력`](../results/gemma_review.md)은 내용 변경 없이 evidence로 보존했고, 사람은 각 지적을 `ACCEPT / REJECT / PARTIAL ACCEPT / MAINTAIN`으로 판정했다. spurious correlation·모든 지표 무효·현장 도입 불가능 단정은 기각하거나 완화했으며, 수용한 검증 의제 중 지정된 세 항목만 Python으로 확인했다. 상세 원문 매핑과 조치는 [`GEMMA_REVIEW_DECISIONS.md`](../docs/GEMMA_REVIEW_DECISIONS.md)에 있다. Gemma가 수치를 계산하거나 최종 결론을 결정하지 않았다.
