# AI 사용 기록

## 이번 산출물에서 실제로 한 일

- Python이 데이터 수, 결측, 분할, 모델, 지표, 혼동행렬, FN, 변수 후보, 그래프를 계산했다.
- Codex가 프로젝트 구조·코드·문서 초안을 보조했고, 별도 검토 과정에서 지표를 원본 예측으로 재계산하고 누수·시간 일반화·과대해석 위험을 점검했다.
- 최종 수치의 source of truth는 `results/` 아래 Python 산출물이다. AI가 새 숫자를 계산하거나 추정한 값을 결과로 사용하지 않았다.

## AI 제안과 검증을 분리한 증거

| 항목 | AI 보조 | 사실 확인 방법 |
|---|---|---|
| 분석 구조 | 불균형 평가, 누수 점검, FN 검토 순서 제안 | `src/secom_analysis.py` 실행과 자동 테스트 |
| 코드 검토 | 혼동행렬 방향, threshold 선택 위치, 과대해석 위험 검토 | 예측 CSV에서 지표 독립 재계산 |
| Gemma 4 26B A4B 독립 리뷰 | 시간 일반화·표본 불확실성·timestamp·변수 안정성에 대한 공격적 반론 | 변경 없는 [`원본 출력`](../results/gemma_review.md), Python sensitivity 산출물, [`GEMMA_REVIEW_DECISIONS.md`](GEMMA_REVIEW_DECISIONS.md)의 사람 판정 |
| 문서 | README·보고서 문장 초안과 반론 보조 | 원본·JSON·CSV와 문장별 대조 |
| 수치 산출 | 사용하지 않음 | Python 실행 결과만 기록 |
| 공정 의미 추정 | 사용하지 않음 | 익명 변수는 후보명으로만 유지 |

실행 완료 Notebook은 12개 코드 셀이 모두 실행됐고 error output이 0개인지 테스트로 확인한다. 저장된 test 지표는 `test_predictions.csv`에서 다시 계산해 원값과 `1e-12` 이내로 비교한다. 실제 명령, 경고, 테스트 결과는 [`VALIDATION_LOG.md`](VALIDATION_LOG.md)에 남겼다.

## Gemma 상태와 Human Decision

- 실제 독립 리뷰: **수행됨**. 사용자가 별도 환경에서 Gemma API를 실행했다.
- 원문 표기 모델: `gemma-4-26b-a4b-it` (Gemma 4 26B A4B)
- 원문 생성 시각: `2026-08-22T13:59:07.631883+00:00` UTC
- 원본 evidence: [`results/gemma_review.md`](../results/gemma_review.md)
- 원본 무결성: 5,143 bytes, SHA-256 `68fde4ed803ce0c6f5de40fa90b9dfabfab5bf39122c4b198de9997ffa14ce9d`
- 실행 경계: Gemma 원문은 내용 변경 없이 보존했다. Gemma는 이 저장소의 데이터 처리·모델 학습·지표 계산에 사용되지 않았고, Python 산출물을 비판하는 독립 리뷰 역할만 했다.

사람은 Gemma의 주장을 그대로 따르지 않았다. 시간순 성능 저하는 수용했지만 **spurious correlation이 원인이고 미래 예측에 사용할 수 없다는 단정**은 distribution shift 또는 temporal instability 가능성으로 완화했다. FAIL 21개의 불확실성은 수용했지만 **모든 지표가 무효라는 단정**은 기각했다. Precision `10.49%`와 FP `145`개의 trade-off는 수용했지만 비용자료 없이 **공정중단 비용이 발생하고 현장 도입이 불가능하다는 단정**은 기각했다.

수용한 검증 의제 중 사용자가 지정한 세 항목만 Python으로 재검증했다.

1. 변수 후보의 시간 안정성
2. 잠금 test 지표의 bootstrap 불확실성
3. shared timestamp 영향 민감도

원본이 제안한 FAIL clustering은 승인된 검증 범위에 포함되지 않아 수행하지 않았다. cost-optimal threshold는 실제 FP/FN 비용·검사시간·운영 규칙이 없어 수행하지 않고 Future Work로 남겼다. 지적별 원문 매핑, `ACCEPT / REJECT / PARTIAL ACCEPT / MAINTAIN`, 실제 조치는 [`GEMMA_REVIEW_DECISIONS.md`](GEMMA_REVIEW_DECISIONS.md)에 기록했다. 원문의 시간순 ROC-AUC `0.514`는 정렬 보정 전 당시 입력에 대한 역사적 기록이고, 현재 source of truth는 `timestamp → sample_id` 정렬을 고정한 Python 결과 `0.539909`다.

이 evidence PR을 Freeze checkpoint로 삼아 공개 v1을 `FROZEN` 상태로 두고 추가 모델링을 중단한다. 이 PR에서는 신규 분석·재학습·모델 튜닝을 수행하지 않았다.

## 지원서 사용 전 사람의 확인

이 프로젝트가 AI-assisted로 만들어졌다는 사실을 숨기지 않는다. 지원자는 다음을 직접 할 수 있을 때만 프로젝트 수행 경험으로 사용해야 한다.

1. 원본 데이터와 라벨을 다시 내려받고 hash를 확인한다.
2. 왜 Accuracy 대신 FAIL Recall·Precision·AP·혼동행렬을 함께 봤는지 설명한다.
3. 전처리를 Pipeline 안에 둔 이유와 test를 잠근 이유를 설명한다.
4. threshold 0.060939가 확률이나 운영 최적값이 아닌 이유를 설명한다.
5. FN 4건, 오탐 145건, 시간순 성능 저하를 숨기지 않고 말한다.
6. bootstrap 구간이 고정 test·유병률에 조건부이며 외부 성능 보장이 아님을 설명한다.
7. `feature_059`를 원인이 아닌 random-CV 조사 후보로 표현하고 시간 안정성은 확인되지 않았다고 밝힌다.
8. 비용자료 없이 cost-optimal threshold를 주장하지 않는다.
