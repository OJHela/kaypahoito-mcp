"""HTTP client for kaypahoito.fi — WP Search API + HTML scraping."""

import asyncio
import random
import re
import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://www.kaypahoito.fi"
SEARCH_API = f"{BASE_URL}/wp-json/wp/v2/search"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; intric-mcp/1.0)",
    "Accept": "text/html,application/json",
}


async def search_wp(query: str, per_page: int = 20) -> list[dict]:
    """Call WP Search API and return list of result dicts."""
    params = {
        "search": query,
        "type": "post",
        "per_page": min(per_page, 20),
    }
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        r = await client.get(SEARCH_API, params=params, headers=HEADERS)
        r.raise_for_status()
        return r.json()


async def fetch_suositus_html(url: str) -> str:
    """Fetch HTML for a single suositus page."""
    await asyncio.sleep(0.5 + random.random() * 0.5)  # polite jitter
    if not url.startswith("http"):
        url = f"{BASE_URL}/{url.lstrip('/')}"
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        r = await client.get(url, headers=HEADERS)
        r.raise_for_status()
        return r.text


def parse_suositus(html: str, url: str) -> dict:
    """
    Extract title, metadata and section text from a suositus HTML page.
    Returns dict with keys: title, authors, updated, url, sections (list), full_text.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Remove noise
    for tag in soup.find_all(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    article = soup.find("article", class_="article")
    if not article:
        # Fallback: try to get any meaningful text
        body = soup.find("body") or soup
        text = body.get_text(separator="\n", strip=True)
        return {
            "title": soup.title.get_text(strip=True) if soup.title else url,
            "authors": "",
            "updated": "",
            "url": url,
            "sections": [],
            "full_text": text[:8000],
        }

    # Title
    h1 = article.find("h1")
    title = h1.get_text(strip=True) if h1 else url

    # Metadata
    authors = ""
    updated = ""
    header_div = article.find("div", class_="duo-article-header")
    if header_div:
        authors_el = header_div.find("div", class_="duo-authors")
        if authors_el:
            authors = authors_el.get_text(strip=True)
        updated_el = header_div.find("div", class_="duo-updated")
        if updated_el:
            updated = updated_el.get("datetime") or updated_el.get_text(strip=True)

    # Extract sections — h2 headings + their content
    sections = []
    current_heading = None
    current_texts = []

    for el in article.descendants:
        if el.name == "h2":
            if current_heading is not None:
                text = " ".join(current_texts).strip()
                if text:
                    sections.append({"heading": current_heading, "text": text[:1500]})
            current_heading = el.get_text(strip=True)
            current_texts = []
        elif el.name == "p" and current_heading is not None:
            t = el.get_text(strip=True)
            if t:
                current_texts.append(t)
        elif el.name == "li" and current_heading is not None:
            t = el.get_text(strip=True)
            if t:
                current_texts.append(f"• {t}")

    if current_heading is not None:
        text = " ".join(current_texts).strip()
        if text:
            sections.append({"heading": current_heading, "text": text[:1500]})

    # Compact full text — clean whitespace
    raw_text = article.get_text(separator="\n", strip=True)
    # Remove repeated whitespace/newlines
    full_text = re.sub(r"\n{3,}", "\n\n", raw_text)
    full_text = re.sub(r" {2,}", " ", full_text)

    return {
        "title": title,
        "authors": authors,
        "updated": updated,
        "url": url,
        "sections": sections[:30],  # max 30 sections
        "full_text": full_text[:8000],
    }
