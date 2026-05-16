from __future__ import annotations

import base64
import csv
import datetime as dt
import hashlib
import io
import json
import re
from dataclasses import dataclass
from typing import Any

from backend.models.schemas import ColumnSchema


SOURCE_TYPE_MAP = {"TEXT": "TEXT", "IMAGE": "IMAGE", "URL": "URL"}


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def utc_now_iso() -> str:
    return utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalize_column_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", " ", name).strip()
    if not cleaned:
        return "Column"
    return " ".join(part.capitalize() for part in cleaned.split())


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")
    return cleaned.lower() or "excelai_export"


def safe_json_loads(raw: str) -> dict[str, Any]:
    text = raw.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to extract JSON from markdown code blocks
        for marker in ("```json", "```", '"""'):
            if marker in text:
                start = text.find(marker) + len(marker)
                end = text.find(marker, start)
                if end > start:
                    extracted = text[start:end].strip()
                    try:
                        return json.loads(extracted)
                    except json.JSONDecodeError:
                        continue
        # Try greedy regex extraction
        match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    raise ValueError("Response was not valid JSON")


def ensure_columns(columns: list[Any]) -> list[ColumnSchema]:
    normalized: list[ColumnSchema] = []
    for index, column in enumerate(columns or []):
        if isinstance(column, dict):
            normalized.append(
                ColumnSchema(
                    name=normalize_column_name(str(column.get("name") or f"Column {index + 1}")),
                    type=column.get("type") or "text",
                )
            )
        else:
            normalized.append(ColumnSchema(name=normalize_column_name(str(column)), type="text"))
    return normalized


def coerce_rows(rows: list[Any], column_count: int) -> list[list[Any]]:
    normalized_rows: list[list[Any]] = []
    for row in rows or []:
        if isinstance(row, dict):
            values = list(row.values())
        elif isinstance(row, (list, tuple)):
            values = list(row)
        else:
            values = [str(row)]
        if len(values) < column_count:
            values.extend([None] * (column_count - len(values)))
        # Ensure all values are properly stringified for safety
        normalized_rows.append([str(v) if v is not None else None for v in values[:column_count]])
    return normalized_rows


DATE_PATTERNS = (
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%b %d, %Y",
    "%d %b %Y",
    "%B %d, %Y",
    "%d %B %Y",
)


def infer_scalar_type(value: Any) -> str:
    if value is None:
        return "text"
    if isinstance(value, bool):
        return "text"
    if isinstance(value, (int, float)):
        return "number"
    text = normalize_whitespace(str(value))
    if not text:
        return "text"
    lowered = text.lower()
    if re.fullmatch(r"\$?\(?-?[\d,]+(?:\.\d+)?\)?", text):
        return "currency" if "$" in text else "number"
    if re.fullmatch(r"-?[\d.]+%", text):
        return "percentage"
    for pattern in DATE_PATTERNS:
        try:
            dt.datetime.strptime(text, pattern)
            return "date"
        except ValueError:
            continue
    if any(token in lowered for token in ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")) and any(char.isdigit() for char in text):
        return "date"
    if any(char.isdigit() for char in text) and not any(char.isalpha() for char in text):
        return "number"
    return "text"


def guess_column_type(values: list[Any]) -> str:
    counts: dict[str, int] = {"number": 0, "currency": 0, "date": 0, "percentage": 0, "text": 0}
    for value in values:
        counts[infer_scalar_type(value)] += 1
    order = ["currency", "date", "percentage", "number", "text"]
    return max(order, key=lambda item: (counts[item], -order.index(item)))


def build_fallback_table(source_text: str, hint: str | None = None) -> dict[str, Any]:
    lines = [normalize_whitespace(line) for line in source_text.splitlines() if normalize_whitespace(line)]
    if not lines:
        return {
            "columns": [
                {"name": "Value", "type": "text"},
            ],
            "rows": [[hint or "No structured content detected"]],
            "confidence": 0.18,
            "warnings": ["The source did not contain enough structure. Review the extracted table manually."],
            "table_title": hint or "Extracted Data",
        }

    # Try to detect headers from first line
    header_candidates = re.split(r"\s{2,}|\t|\|", lines[0])
    if len(header_candidates) > 1:
        headers = [normalize_column_name(part) for part in header_candidates if part.strip()]
        data_lines = lines[1:]
    else:
        # Look for key:value pairs
        pair_matches = [line for line in lines if ":" in line and len(line.split(":")) == 2]
        if len(pair_matches) >= 2:
            headers = ["Field", "Value"]
            rows = []
            for line in pair_matches[:100]:
                key, _, value = line.partition(":")
                rows.append([normalize_whitespace(key), normalize_whitespace(value)])
            return {
                "columns": [{"name": "Field", "type": "text"}, {"name": "Value", "type": "text"}],
                "rows": rows,
                "confidence": 0.42,
                "warnings": ["Fallback parser used because the input was not a clean table."],
                "table_title": hint or "Extracted Data",
            }
        
        # Try to detect comma/tab-separated values even without explicit headers
        # Check if most lines have consistent separator patterns
        first_line_parts = re.split(r"\s{2,}|\t|,", lines[0])
        if len(first_line_parts) > 1:
            # Might be a header or first data row
            headers = [normalize_column_name(f"Column {i+1}") for i in range(len(first_line_parts))]
            data_lines = lines
        else:
            headers = ["Content"]
            data_lines = lines

    rows: list[list[Any]] = []
    max_rows = 1000  # Increased from 200 to handle large datasets
    for line in data_lines[:max_rows]:
        cells = [normalize_whitespace(part) for part in re.split(r"\s{2,}|\t|,", line) if normalize_whitespace(part)]
        if not cells:
            continue
        if len(headers) == 1:
            rows.append([line])
        else:
            row = cells[: len(headers)]
            if len(row) < len(headers):
                row.extend([None] * (len(headers) - len(row)))
            rows.append(row)

    if not rows:
        # Fallback: treat each line as a row
        rows = [[line] for line in lines[:100]]
        headers = ["Content"]

    columns = []
    for index, header in enumerate(headers):
        column_values = [row[index] if index < len(row) else None for row in rows]
        columns.append({"name": header, "type": guess_column_type(column_values)})

    return {
        "columns": columns,
        "rows": rows,
        "confidence": 0.35,
        "warnings": ["Fallback parser used because the LLM response was unavailable or invalid."],
        "table_title": hint or "Extracted Data",
    }


def parse_ai_payload(payload: dict[str, Any], fallback_source: str, hint: str | None = None) -> dict[str, Any]:
    columns = ensure_columns(payload.get("columns", []))
    rows = coerce_rows(payload.get("rows", []), len(columns))
    confidence = payload.get("confidence", 0.5)
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.5
    warnings = [str(item) for item in payload.get("warnings", []) if str(item).strip()]
    table_title = payload.get("table_title") or hint
    if not columns or not rows:
        return build_fallback_table(fallback_source, hint=hint)
    return {
        "columns": [column.model_dump() for column in columns],
        "rows": rows,
        "confidence": max(0.0, min(1.0, confidence)),
        "warnings": warnings,
        "table_title": table_title,
    }


def csv_bytes(columns: list[ColumnSchema], rows: list[list[Any]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([column.name for column in columns])
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue().encode("utf-8")


def sha256_token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def b64_json_payload(token: str) -> dict[str, Any]:
    return {"token": token}


def decode_base64url(segment: str) -> dict[str, Any]:
    padded = segment + "=" * (-len(segment) % 4)
    decoded = base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
    return json.loads(decoded)
