#!/usr/bin/env python3
"""Optionally ask hosted Gemma to critique completed, public analysis artifacts."""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = "gemma-4-26b-a4b-it"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--include-code",
        action="store_true",
        help="Also send src/secom_analysis.py for a code-level review.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "results" / "gemma_review.md",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not os.environ.get("GEMINI_API_KEY"):
        raise SystemExit(
            "GEMINI_API_KEY is not set. Create a key in Google AI Studio and "
            "store it only in your shell environment."
        )

    try:
        from google import genai
        from google.genai import types
    except ImportError as error:
        raise SystemExit(
            "Optional dependency missing. Install requirements-gemma.txt first."
        ) from error

    prompt = (PROJECT_ROOT / "prompts" / "gemma_review_prompt.md").read_text(
        encoding="utf-8"
    )
    run_summary = (PROJECT_ROOT / "results" / "run_summary.json").read_text(
        encoding="utf-8"
    )
    content_parts = [prompt, "\n\n# 실제 Python 실행 요약\n", run_summary]
    if args.include_code:
        source = (PROJECT_ROOT / "src" / "secom_analysis.py").read_text(
            encoding="utf-8"
        )
        content_parts.extend(["\n\n# 분석 코드\n", source])

    client = genai.Client()
    response = client.models.generate_content(
        model=args.model,
        contents="".join(content_parts),
        config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_level="high")
        ),
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    args.output.write_text(
        f"# Gemma review\n\n"
        f"- Model: `{args.model}`\n"
        f"- Generated at (UTC): `{timestamp}`\n"
        f"- Status: AI critique; not a numerical source of truth\n\n"
        f"{response.text}\n",
        encoding="utf-8",
    )
    print(f"Saved Gemma critique to: {args.output}")


if __name__ == "__main__":
    main()
