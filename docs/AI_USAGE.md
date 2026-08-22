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
| 외부 Gemma 지적 요약 | 시간 일반화·표본 불확실성·timestamp·변수 안정성에 대한 반론 | Python sensitivity 산출물과 [`GEMMA_REVIEW_DECISIONS.md`](GEMMA_REVIEW_DECISIONS.md)의 사람 판정 |
| 문서 | README·보고서 문장 초안과 반론 보조 | 원본·JSON·CSV와 문장별 대조 |
| 수치 산출 | 사용하지 않음 | Python 실행 결과만 기록 |
| 공정 의미 추정 | 사용하지 않음 | 익명 변수는 후보명으로만 유지 |

실행 완료 Notebook은 9개 코드 셀이 모두 실행됐고 error output이 0개인지 테스트로 확인한다. 저장된 test 지표는 `test_predictions.csv`에서 다시 계산해 원값과 `1e-12` 이내로 비교한다. 실제 명령, 경고, 테스트 결과는 [`VALIDATION_LOG.md`](VALIDATION_LOG.md)에 남겼다.

## Gemma 상태와 Human Decision

- 프로젝트 환경의 Gemma 설치: **없음**
- 프로젝트 환경의 Gemma API 호출: **없음**
- 로컬 Gemma 실행 결과 파일: **없음**
- 요청에 언급된 `results/gemma_review.md` 원문: **로컬·GitHub에 없음**
- 사용자 제공 정보: 외부에서 Gemma 4 26B A4B 검토를 완료했다는 진술과 6개 지적 요약
- 사용 방식: 사용자 요약을 반론 입력으로만 사용하고 Python 재계산과 사람의 판정으로 수용 범위를 결정

원문이 없으므로 Gemma 발언을 인용하거나 복원하지 않았다. 지적별 `ACCEPT/REJECT/PARTIAL ACCEPT`, 실제 계산, 문서 조치는 [`GEMMA_REVIEW_DECISIONS.md`](GEMMA_REVIEW_DECISIONS.md)에 기록했다. `scripts/gemma_review.py`와 `prompts/gemma_review_prompt.md`는 별도의 선택적 실행 경로이며 이번 사용자 요약의 원문 생성 경로라고 주장하지 않는다.

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
