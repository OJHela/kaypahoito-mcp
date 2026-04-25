"""Käypä hoito MCP tools."""

from __future__ import annotations

from kaypahoito_client import (
    BASE_URL,
    fetch_suositus_html,
    get_catalog,
    parse_suositus,
    search_catalog,
    search_wp,
)


async def hae_suositukset(hakusana: str) -> str:
    """
    Search Käypä hoito guidelines by keyword. Returns actual guideline documents.

    USE THIS TOOL WHEN:
    - User asks about a medical condition or symptom in Finnish
    - User wants to find guidelines before reading details

    THEN CALL:
    → Found results? → call hae_suositus(url=<URL from results>)
    → No results? → try a shorter Finnish term or synonym

    DO NOT USE WHEN:
    - You already have a URL like hoi50056 → call hae_suositus directly

    Parameters:
    - hakusana: Finnish keyword, e.g. "diabetes", "verenpaine", "astma", "sydän", "masennus"
    """
    # Primary: search the embedded catalog — returns actual suositus documents
    catalog = await get_catalog()
    matches = search_catalog(catalog, hakusana)

    if matches:
        lines = [f"Löytyi {len(matches)} suositusta: '{hakusana}'\n"]
        for item in matches:
            nimi = item["nimi"]
            otsikko = item.get("otsikko") or nimi
            kuvaus = item.get("kuvaus") or ""
            updated = (item.get("sisaltopvm") or item.get("paivityspvm") or "")[:10]
            erikoisalat = ", ".join(
                e["erikoisala"] for e in item.get("Erikoisalat", [])[:3]
            )
            url = f"{BASE_URL}/{nimi}"

            lines.append(f"**{otsikko}**")
            lines.append(f"  URL: {url}")
            if kuvaus:
                lines.append(f"  {kuvaus[:180]}")
            if erikoisalat:
                lines.append(f"  Erikoisalat: {erikoisalat}")
            if updated:
                lines.append(f"  Päivitetty: {updated}")
            lines.append("")

        lines.append(
            f"Seuraava askel: hae_suositus(url='https://www.kaypahoito.fi/hoi...')"
        )
        return "\n".join(lines)

    # Fallback: WP full-text search (returns news, not the guidelines themselves)
    wp_results = await search_wp(hakusana, per_page=10)
    if not wp_results:
        return (
            f"Ei suosituksia hakusanalla '{hakusana}'. "
            f"Kokeile: diabetes, astma, verenpaine, sydän, masennus, kipu, syöpä."
        )

    lines = [
        f"Suositusluettelossa ei osumia. Löytyi {len(wp_results)} artikkelia: '{hakusana}'\n"
    ]
    for item in wp_results[:10]:
        lines.append(f"**{item.get('title', '')}**")
        lines.append(f"  URL: {item.get('url', '')}")
        lines.append("")
    return "\n".join(lines)


async def hae_suositus(url: str) -> str:
    """
    Fetch the full content of a single Käypä hoito guideline by URL.

    USE THIS TOOL WHEN:
    - You have a guideline URL (e.g. hoi50056 or https://www.kaypahoito.fi/hoi50056)
    - User wants the actual clinical recommendations, treatment steps, or key messages

    WORKFLOW:
    → First call hae_suositukset to get the URL, then call this tool

    DO NOT USE WHEN:
    - You don't have a URL yet → call hae_suositukset first

    Parameters:
    - url: guideline slug or full URL, e.g. "hoi50056", "hoi50068",
      "https://www.kaypahoito.fi/hoi50056"
    """
    if not url.startswith("http"):
        url = f"{BASE_URL}/{url.lstrip('/')}"

    html = await fetch_suositus_html(url)
    data = parse_suositus(html, url)

    if not data["title"]:
        return f"Suositusta ei löydy: {url}"

    # Build compact, token-efficient output
    lines: list[str] = [f"# {data['title']}", ""]

    meta_parts: list[str] = []
    if data["updated"]:
        meta_parts.append(f"Päivitetty: {data['updated']}")
    if data["authors"]:
        # Trim long author strings — the working group name can be very long
        authors = data["authors"]
        if len(authors) > 120:
            authors = authors[:120] + "…"
        meta_parts.append(f"Tekijät: {authors}")
    meta_parts.append(f"Lähde: {url}")
    lines.append(" | ".join(meta_parts))
    lines.append("")

    sections = data["sections"]
    if not sections:
        return "\n".join(lines) + "\n(Sisältöä ei voitu poimia tältä sivulta.)"

    # Prioritize: show "keskeinen sanoma" first if present
    priority_keywords = ("keskeinen", "sanoma", "tiivistelmä", "johdanto", "tavoite")
    priority = [s for s in sections if any(k in s["heading"].lower() for k in priority_keywords)]
    rest = [s for s in sections if s not in priority]

    ordered = priority[:3] + rest  # lead with the most useful sections
    output_chars = 0
    for section in ordered[:15]:
        block = f"## {section['heading']}\n{section['text']}\n"
        if output_chars + len(block) > 10_000:
            break
        lines.append(block)
        output_chars += len(block)

    return "\n".join(lines)
