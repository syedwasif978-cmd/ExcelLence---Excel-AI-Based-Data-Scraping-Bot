from __future__ import annotations

import os
from typing import Any

from backend.models.schemas import ColumnSchema
from backend.utils.helpers import build_fallback_table, normalize_whitespace, parse_ai_payload, safe_json_loads

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
MAX_PROMPT_CHARS = 50000  # Increased to handle large datasets (40-50 columns/rows)


def _truncate_for_llm(content: str) -> str:
    """Truncate content while preserving table structure and headers."""
    lines = content.split("\n")
    normalized = normalize_whitespace(content)
    if len(normalized) <= MAX_PROMPT_CHARS:
        return normalized
    
    # For large tables: keep headers + as many rows as possible
    header_lines = []
    data_lines = []
    found_data = False
    
    for line in lines:
        if not found_data:
            # Treat first 2 lines as potential headers
            if len(header_lines) < 2:
                header_lines.append(line)
                continue
            found_data = True
        data_lines.append(line)
    
    # Build result starting with headers
    result = "\n".join(header_lines)
    for line in data_lines:
        test = result + "\n" + line
        if len(test) <= MAX_PROMPT_CHARS - 100:  # Leave 100 char buffer for LLM formatting
            result = test
        else:
            # Add row count info instead of truncating silently
            remaining = len(data_lines) - len(result.split("\n")[2:])
            result += f"\n... ({remaining} more rows)"
            break
    
    return result


def _compose_user_prompt(source_label: str, content: str, clarification: str | None = None) -> str:
    content = _truncate_for_llm(content)
    if source_label == "URL":
        return (
            f"Here is the content scraped from a URL. Identify the most relevant table based on user intent: '{clarification or 'extract the primary table'}'. "
            f"Extract it into the JSON format above.\n\nCONTENT:\n{content}"
        )
    if source_label == "IMAGE":
        return (
            "Here is text extracted via OCR from a screenshot/image or PDF. Parse it into a structured table. "
            "Flag any values that may be OCR misreads (e.g. 'S' vs '5', 'l' vs '1').\n\n"
            f"CONTENT:\n{content}"
        )
    return f"Extract the tabular data from the user input into the strict JSON format above.\n\nCONTENT:\n{content}"


def _extract_groq_content(client: Any, messages: list[dict[str, str]], strict_json: bool = True) -> str:
    request_kwargs: dict[str, Any] = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.1,
    }
    if strict_json:
        request_kwargs["response_format"] = {"type": "json_object"}
    response = client.chat.completions.create(**request_kwargs)
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

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        # First attempt: strict JSON mode with full prompt
        raw = _extract_groq_content(client, messages, strict_json=True)
        try:
            payload = safe_json_loads(raw)
            # Validate that we got actual data (not empty)
            if payload.get("columns") and payload.get("rows"):
                return parse_ai_payload(payload, content, hint=clarification or fallback.get("table_title") or "Extracted Data")
        except Exception as e1:
            pass  # Continue to retry

        # Second attempt: relaxed JSON mode with explicit strict instruction
        retry_prompt = (
            user_prompt
            + "\n\n[STRICT] You MUST return valid JSON. Return ONLY JSON, nothing else. "
            + "Ensure 'columns' array is not empty and 'rows' array has at least 1 element."
        )
        raw = _extract_groq_content(
            client,
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": retry_prompt},
            ],
            strict_json=False,
        )
        try:
            payload = safe_json_loads(raw)
            if payload.get("columns") and payload.get("rows"):
                return parse_ai_payload(payload, content, hint=clarification or fallback.get("table_title") or "Extracted Data")
        except Exception as e2:
            pass  # Continue to retry

        # Third attempt: simplified system prompt with chunked data (first 3000 chars)
        chunk_size = 3000
        content_chunk = content[:chunk_size]
        if len(content) > chunk_size:
            content_chunk += f"\n... [Total input: {len(content)} characters, showing first {chunk_size}]"
        
        simple_system = (
            "Return ONLY valid JSON. Extract all columns and rows from data. "
            "CRITICAL: columns array MUST have at least 1 item. rows array MUST have at least 1 item. "
            'Format: {"columns": [{"name": "Col1", "type": "text"}], "rows": [["value1"]], "confidence": 0.8, "warnings": []}'
        )
        raw = _extract_groq_content(
            client,
            [
                {"role": "system", "content": simple_system},
                {"role": "user", "content": f"Extract this table data:\n{content_chunk}"},
            ],
            strict_json=False,
        )
        try:
            payload = safe_json_loads(raw)
            if payload.get("columns") and payload.get("rows"):
                return parse_ai_payload(payload, content, hint=clarification or fallback.get("table_title") or "Extracted Data")
        except Exception as e3:
            pass

        # Fourth attempt: ask LLM to first identify structure, then extract
        identify_structure_prompt = (
            "First, identify the structure of this data (how many columns, what are they named). "
            "Then extract all rows into JSON format. "
            f"Data:\n{content[:2000]}"
        )
        raw = _extract_groq_content(
            client,
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": identify_structure_prompt},
            ],
            strict_json=False,
        )
        try:
            payload = safe_json_loads(raw)
            if payload.get("columns") and payload.get("rows"):
                return parse_ai_payload(payload, content, hint=clarification or fallback.get("table_title") or "Extracted Data")
        except Exception as e4:
            pass

        # All LLM attempts failed - add details to fallback warning
        fallback["warnings"] = fallback.get("warnings", []) + ["LLM extraction attempts failed. Using fallback parser."]
        return fallback
        
    except Exception as exc:
        fallback["warnings"] = fallback.get("warnings", []) + [f"LLM extraction failed. Fallback parsing was used. ({exc.__class__.__name__})"]
        return fallback
