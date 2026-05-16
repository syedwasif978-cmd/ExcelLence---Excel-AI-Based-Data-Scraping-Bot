from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup


async def scrape_url(url: str) -> dict[str, Any]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
    }
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers=headers) as client:
        response = await client.get(url)
        response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else urlparse(url).netloc

    tables: list[str] = []
    for index, table in enumerate(soup.find_all("table")[:5]):
        rows: list[str] = []
        for tr in table.find_all("tr")[:100]:
            cells = [cell.get_text(" ", strip=True) for cell in tr.find_all(["th", "td"])]
            if cells:
                rows.append(" | ".join(cells))
        table_html = "\n".join(rows)
        if table_html:
            tables.append(f"TABLE {index + 1}:\n{table_html}")

    body_text = "\n".join(
        line.strip()
        for line in soup.get_text("\n", strip=True).splitlines()
        if line.strip()
    )

    content_parts = [f"TITLE: {title}"]
    if tables:
        content_parts.append("\n\n".join(tables))
    content_parts.append(body_text[:40000])
    return {
        "title": title,
        "content": "\n\n".join(content_parts),
        "table_count": len(tables),
    }
