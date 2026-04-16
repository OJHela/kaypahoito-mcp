"""Käypä hoito MCP tools."""

from kaypahoito_client import search_wp, fetch_suositus_html, parse_suositus

BASE_URL = "https://www.kaypahoito.fi"


async def hae_suositukset(hakusana: str) -> str:
    """
    Hae Käypä hoito -suosituksia hakusanalla WP Search -rajapinnasta.

    KÄYTÄ TÄTÄ TYÖKALUA KUN:
    - Käyttäjä kysyy Käypä hoito -suosituksista aihepiirin perusteella
    - Käyttäjä pyytää listauksen suosituksista tiettyyn sairauteen tai oireeseen liittyen
    - Käyttäjä kysyy "mitä suosituksia on X:stä?"
    - Haluat etsiä suosituksia ennen yksityiskohtien hakemista

    TYÖNKULKU:
    → Löytyikö tuloksia? → kutsu hae_suositus löydetyn URL:n perusteella
    → Ei tuloksia? → kokeile lyhyempää hakusanaa tai synonyymejä

    ÄLÄ KÄYTÄ KUN:
    - Sinulla on jo URL tai tunnus (esim. hoi50056) → käytä hae_suositus suoraan

    Parameters:
    - hakusana: hakusana suomeksi, esim. "diabetes", "verenpaine", "astma", "sydäninfarkti"
    """
    results = await search_wp(hakusana, per_page=20)

    if not results:
        return f"Hakusanalla '{hakusana}' ei löytynyt tuloksia. Kokeile lyhyempää tai yleisempää hakusanaa."

    lines = [f"Hakutulokset ({len(results)}) hakusanalle '{hakusana}':\n"]
    for item in results[:20]:
        title = item.get("title", "Ei otsikkoa")
        url = item.get("url", "")
        lines.append(f"**{title}**")
        lines.append(f"  URL: {url}")
        lines.append("")

    lines.append(
        f"Vinkki: Hae yksittäisen suosituksen sisältö kutsumalla hae_suositus(url=...) "
        f"jollakin yllä listatulla URL:lla."
    )
    return "\n".join(lines)


async def hae_suositus(url: str) -> str:
    """
    Hae yksittäisen Käypä hoito -suosituksen sisältö URL:n perusteella.

    KÄYTÄ TÄTÄ TYÖKALUA KUN:
    - Sinulla on suosituksen URL (esim. https://www.kaypahoito.fi/hoi50056 tai hoi50056)
    - Käyttäjä pyytää suosituksen sisältöä, hoito-ohjeita tai suosituksen keskeistä sanomaa
    - Haluat lukea suosituksen osiot ja lääketieteellisen sisällön

    TYÖNKULKU:
    → Ensin hae_suositukset-työkalulla → saat URL:n → kutsu tätä URL:lla

    ÄLÄ KÄYTÄ KUN:
    - Et tiedä URL:ia → kutsu ensin hae_suositukset

    Parameters:
    - url: suosituksen URL tai tunnus, esim. "https://www.kaypahoito.fi/hoi50056",
      "hoi50056", "hoi50068", "https://www.kaypahoito.fi/kht00070"
    """
    # Normalize URL
    if not url.startswith("http"):
        url = f"{BASE_URL}/{url.lstrip('/')}"

    html = await fetch_suositus_html(url)
    data = parse_suositus(html, url)

    if not data["title"]:
        return f"Suositusta ei löydy osoitteesta: {url}"

    lines = [
        f"# {data['title']}",
        "",
    ]

    if data["updated"]:
        lines.append(f"**Päivitetty:** {data['updated']}")
    if data["authors"]:
        lines.append(f"**Tekijät:** {data['authors'][:200]}")
    lines.append(f"**URL:** {url}")
    lines.append("")

    if data["sections"]:
        lines.append("## Osiot\n")
        for section in data["sections"][:20]:
            lines.append(f"### {section['heading']}")
            lines.append(section["text"][:800])
            lines.append("")
    else:
        # Fallback: plain text
        lines.append(data["full_text"][:6000])

    return "\n".join(lines)
