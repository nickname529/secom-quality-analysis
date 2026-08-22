# Gemma 4 독립 리뷰 evidence와 선택적 재현 방법

**확인 기준일: 2026-08-23.** 사용자는 별도 환경에서 실제 `gemma-4-26b-a4b-it` API 독립 리뷰를 수행했고, [`원본 출력`](../results/gemma_review.md)을 변경 없이 제공했다. [`GEMMA_REVIEW_DECISIONS.md`](GEMMA_REVIEW_DECISIONS.md)는 그 원본에 대한 사람의 판정이다. Gemma는 이 저장소의 수치 분석·모델 학습에 사용되지 않았다.

공개 v1은 Freeze되었으므로 아래 경로는 **재현 참고용**이다. 추가 Gemma 실행이나 그에 따른 신규 모델링은 frozen v1에 반영하지 않으며, 필요하면 명시적으로 승인된 별도 버전에서만 다룬다.

## 가장 간단한 방법: Google AI Studio

설치 없이 [Google AI Studio](https://aistudio.google.com/)에서 `gemma-4-26b-a4b-it`를 선택하고 `prompts/gemma_review_prompt.md`와 `results/run_summary.json`을 붙여 넣는다. Google 공식 시작 문서는 범용 출발점으로 Gemma 4 26B A4B를 권장한다.

- [Gemma 공식 시작 문서](https://ai.google.dev/gemma/docs/get_started)
- [Gemma release 기록](https://ai.google.dev/gemma/docs/releases)

2026-08-22 기준 최신 core 계열은 Gemma 4이며, 공식 release 기록에는 2026-03-31 E2B/E4B/26B A4B/31B, 2026-06-03 12B Unified가 기재되어 있다.

## 원문과 같은 출력 형식을 만드는 API 방식

Gemini API가 공식 지원하는 Gemma 4 model ID는 `gemma-4-26b-a4b-it`와 `gemma-4-31b-it`다. 이 프로젝트는 전자를 기본값으로 둔다.

```bash
python -m pip install -r requirements-gemma.txt
export GEMINI_API_KEY="AI_Studio에서_발급한_키"
python scripts/gemma_review.py --include-code \
  --output results/gemma_review_reproduction.md
```

재현 결과는 `results/gemma_review_reproduction.md`에 저장해 동결된 원본 `results/gemma_review.md`를 덮어쓰지 않는다. helper의 기본 출력도 재현 파일로 분리했다. API key를 코드·README·notebook·Git에 넣지 않는다. [Google 공식 Gemma API 문서](https://ai.google.dev/gemma/docs/core/gemma_on_gemini_api)는 `thinking_level="high"`와 `"minimal"`을 지원하며, 코드·방법론 검토에는 이 프로젝트가 `high`를 사용한다.

현재 [공식 가격표](https://ai.google.dev/gemini-api/docs/pricing)는 Gemma 4의 free tier 입출력을 무료, paid tier를 미제공으로 표시하고 free tier 입력이 제품 개선에 사용될 수 있다고 명시한다. 따라서 공개 SECOM 결과와 공개 가능한 코드만 전송하고 개인정보·지원서 원문·기업 비공개 데이터는 보내지 않는다. 제한과 가격은 바뀔 수 있으므로 실행 직전에 다시 확인한다.

[공식 API key 안내](https://ai.google.dev/gemini-api/docs/api-key)에 따르면 새 AI Studio key는 auth key가 기본이며, Standard key는 2026년 9월부터 거부될 예정이다.

## 로컬 대안: Ollama

공개 API로 자료를 보내지 않는 것이 더 중요할 때만 로컬을 고려한다. 설치와 모델 다운로드가 필요하므로 이번 프로젝트에서는 실행하지 않았다.

```bash
ollama pull gemma4:e4b
ollama run gemma4:e4b "이 분석에서 데이터 누수와 과대해석 가능성을 검토해줘."
```

Google의 [Ollama 실행 안내](https://ai.google.dev/gemma/docs/integrations/ollama)는 `gemma4:e2b`, `gemma4:e4b`, `gemma4:26b`, `gemma4:31b` 태그를 명시한다. 로컬 양자화 모델은 자원 사용을 줄이는 대신 출력 품질이 낮아질 수 있다.

## 역할 경계

Gemma에게 맡길 수 있는 일:

- 분석 계획의 누수 위험 지적
- 코드 리뷰와 빠진 검증 제안
- 결론의 반론과 대안 가설 생성
- 익명 변수 과대해석 문장 탐지

Gemma에게 맡기지 않는 일:

- PASS/FAIL 수와 지표 계산
- 임의의 공정 의미·센서명·원인 생성
- Python 출력과 다른 숫자를 보고서에 넣기
- 모델 결과를 현장 효과나 실무 경험으로 바꾸기
