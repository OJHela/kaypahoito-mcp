"""HTTP client for kaypahoito.fi — catalog cache + HTML scraping."""

from __future__ import annotations

import asyncio
import base64
import json
import random
import re

import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://www.kaypahoito.fi"
SEARCH_API = f"{BASE_URL}/wp-json/wp/v2/search"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; intric-mcp/1.0)",
    "Accept": "text/html,application/json",
}

# ---------------------------------------------------------------------------
# Catalog cache — 139 suositus items, fetched once from the listing page
# ---------------------------------------------------------------------------

_catalog: list[dict] | None = None


async def get_catalog() -> list[dict]:
    """Return the full suositus catalog, fetching once and caching forever."""
    global _catalog
    if _catalog is None:
        _catalog = await _fetch_catalog()
    return _catalog


async def _fetch_catalog() -> list[dict]:
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        r = await client.get(f"{BASE_URL}/suositukset", headers=_HEADERS)
        r.raise_for_status()
        html = r.text
    m = re.search(r"khdata\s*=\s*JSON\.parse\(atob\('([^']+)'\)", html)
    if not m:
        return []
    data = json.loads(base64.b64decode(m.group(1)))
    return data.get("items", [])


def search_catalog(items: list[dict], query: str) -> list[dict]:
    """
    Score-rank catalog items by relevance to query.
    Returns up to 20 matches sorted by score descending.
    """
    q = query.lower().strip()
    scored: list[tuple[int, dict]] = []

    for item in items:
        otsikko = (item.get("otsikko") or "").lower()
        kuvaus = (item.get("kuvaus") or "").lower()
        erikoisalat = " ".join(
            e.get("erikoisala", "") for e in (item.get("Erikoisalat") or [])
        ).lower()
        tila = item.get("tila", "")

        # Skip discontinued guidelines
        if tila == "ylläpito lopetettu" or item.get("korvattu") == "k":
            continue

        score = 0
        if q == otsikko:
            score += 10
        elif q in otsikko:
            score += 5
        elif any(w in otsikko for w in q.split() if len(w) > 3):
            score += 3
        if q in kuvaus:
            score += 2
        elif any(w in kuvaus for w in q.split() if len(w) > 3):
            score += 1
        if q in erikoisalat:
            score += 1

        if score > 0:
            scored.append((score, item))

    scored.sort(key=lambda x: -x[0])
    return [item for _, item in scored[:20]]


# ---------------------------------------------------------------------------
# WP Search fallback (returns news/announcements mentioning the query)
# ---------------------------------------------------------------------------

async def search_wp(query: str, per_page: int = 10) -> list[dict]:
    """Call WP Search API. Returns news posts, not suositus documents."""
    params = {"search": query, "type": "post", "per_page": min(per_page, 20)}
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        r = await client.get(SEARCH_API, params=params, headers=_HEADERS)
        r.raise_for_status()
        return r.json()


# ---------------------------------------------------------------------------
# Suositus page scraping
# ---------------------------------------------------------------------------

async def fetch_suositus_html(url: str, max_bytes: int = 400_000) -> str:
    """Fetch a suositus page with polite jitter and a size cap."""
    await asyncio.sleep(0.3 + random.random() * 0.4)
    if not url.startswith("http"):
        url = f"{BASE_URL}/{url.lstrip('/')}"
    timeout = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=5.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        # Stream to avoid downloading entire 500KB+ page if not needed
        chunks: list[bytes] = []
        total = 0
        async with client.stream("GET", url, headers=_HEADERS) as r:
            r.raise_for_status()
            async for chunk in r.aiter_bytes():
                chunks.append(chunk)
                total += len(chunk)
                if total >= max_bytes:
                    break
        return b"".join(chunks).decode("utf-8", errors="replace")


def parse_suositus(html: str, url: str) -> dict:
    """
    Extract title, metadata and sections from a suositus HTML page.
    Returns: {title, authors, updated, url, sections: [{heading, text}]}
    """
    soup = BeautifulSoup(html, "html.parser")

    # Strip all noise before any other work
    for tag in soup.find_all(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    article = soup.find("article", class_="article")
    if not article:
        body = soup.find("body") or soup
        text = " ".join(body.get_text().split())
        return {
            "title": soup.title.get_text(strip=True) if soup.title else url,
            "authors": "",
            "updated": "",
            "url": url,
            "sections": [{"heading": "Sisältö", "text": text[:4000]}],
        }

    # --- Metadata ---
    h1 = article.find("h1")
    title = " ".join(h1.get_text().split()) if h1 else url

    authors, updated = "", ""
    hdr = article.find("div", class_="duo-article-header")
    if hdr:
        a = hdr.find("div", class_="duo-authors")
        u = hdr.find("div", class_="duo-updated")
        if a:
            authors = " ".join(a.get_text().split())
        if u:
            updated = u.get("datetime") or " ".join(u.get_text().split())

    # --- Sections ---
    # Walk h2 elements in document order.
    # For each h2, collect text from p/li in its nearest duo-section parent,
    # but skip any elements that belong to a *nested* duo-section.
    sections: list[dict] = []
    seen_headings: set[str] = set()

    for h2 in article.find_all("h2"):
        heading = " ".join(h2.get_text().split())
        if not heading or heading in seen_headings:
            continue
        seen_headings.add(heading)

        parent = h2.find_parent("div", class_="duo-section")
        if not parent:
            continue

        lines: list[str] = []
        for el in parent.find_all(["p", "li"]):
            # Skip if inside a *child* duo-section (would duplicate in a later iteration)
            is_nested = False
            for anc in el.parents:
                if anc is parent:
                    break
                if anc.name == "div" and "duo-section" in (anc.get("class") or []):
                    is_nested = True
                    break
            if is_nested:
                continue
            t = " ".join(el.get_text().split())  # collapse all whitespace
            if t and len(t) > 5:
                lines.append(t)

        # Cap: max 10 bullets, 600 chars per section
        text = "\n".join(lines[:10])[:600]
        if text:
            sections.append({"heading": heading, "text": text})

    return {
        "title": title,
        "authors": authors,
        "updated": updated,
        "url": url,
        "sections": sections[:20],  # hard cap: 20 sections
    }
