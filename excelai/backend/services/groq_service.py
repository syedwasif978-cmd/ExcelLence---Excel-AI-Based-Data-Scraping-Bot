from __future__ import annotations

import os
from typing import Any

from backend.models.schemas import ColumnSchema
from backend.utils.helpers import build_fallback_table, parse_ai_payload, safe_json_loads

SYSTEM_PROMPT = """You are ExcelAI, a precision data extraction engine. Your sole job is to extract structured tabular data from user input and return it as valid JSON.

RULES:
1. Always return ONLY a valid JSON object. No markdown, no backticks, no explanations.
2. Infer column names intelligently. Normalize them (Title Case, no special chars).
3. Infer data types: "number", "currency", "date", "text", "percentage"
4. If data is ambiguous, make the best inference and flag it in warnings.
5. Never hallucinate data. If you cannot extract a value, use null.
6. Calculate a confidence score (0.0 to 1.0) based on data clarity.

RETURN FORMAT (strict JSON):
{
  "columns": [
    { "name": "Rank", "type": "number" },
    { "name": "Company", "type": "text" }
  ],
  "rows": [
    [1, "Apple"],
    [2, "Microsoft"]
  ],
  "confidence": 0.97,
  "warnings": ["Row 3 revenue value may be in billions — assumed USD billions"],
  "table_title": "Top 10 Tech Companies by Revenue 2024"
}
"""

MODEL_NAME = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


def _compose_user_prompt(source_label: str, content: str, clarification: str | None = None) -> str:
    if source_label == "URL":
        return (
            f"Here is the content scraped from a URL. Identify the most relevant table based on user intent: '{clarification or 'extract the primary table'}'. "
            f"Extract it into the JSON format above.\n\nCONTENT:\n{content}"
        )
    if source_label == "IMAGE":
        return (
            "Here is text extracted via OCR from a screenshot/image. Parse it into a structured table. "
            "Flag any values that may be OCR misreads (e.g. 'S' vs '5', 'l' vs '1').\n\n"
            f"CONTENT:\n{content}"
        )
    return f"Extract the tabular data from the user input into the strict JSON format above.\n\nCONTENT:\n{content}"


def _extract_groq_content(client: Any, messages: list[dict[str, str]]) -> str:
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    choice = response.choices[0]
    message = getattr(choice, "message", None)
    content = getattr(message, "content", None)
    if not content and isinstance(choice, dict):
        content = choice.get("message", {}).get("content")
    return content or "{}"


def generate_table(
    source_label: str,
    content: str,
    clarification: str | None = None,
    instruction: str | None = None,
) -> dict[str, Any]:
    fallback = build_fallback_table(content, hint=clarification or "Extracted Data")
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        fallback["warnings"] = fallback.get("warnings", []) + ["GROQ_API_KEY is not configured. Fallback extraction was used."]
        return fallback

    try:
        from groq import Groq
    except Exception:
        fallback["warnings"] = fallback.get("warnings", []) + ["Groq SDK is unavailable. Fallback extraction was used."]
        return fallback

    try:
        client = Groq(api_key=api_key)
        user_prompt = _compose_user_prompt(source_label, content, clarification)
        if instruction:
            user_prompt += f"\n\nAdditional instruction: {instruction}"
        raw = _extract_groq_content(
            client,
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        payload = safe_json_loads(raw)
        return parse_ai_payload(payload, content, hint=clarification or fallback.get("table_title") or "Extracted Data")
    except Exception as exc:
        fallback["warnings"] = fallback.get("warnings", []) + [f"LLM extraction failed. Fallback parsing was used. ({exc.__class__.__name__})"]
        return fallback
