from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import PlainTextResponse

INSTRUCTION_STRING = """
Olet yhteydessä Käypä hoito -tietokantaan — Suomen kansalliseen lääketieteelliseen
suositustietokantaan, joka sisältää näyttöön perustuvat hoitosuositukset.

TYÖNKULKU:
1. hae_suositukset — KÄYTÄ ENSIN kun käyttäjä kysyy suosituksesta aihepiirin perusteella
   → Löytyikö tuloksia? → kutsu hae_suositus URL:lla
   → Ei tuloksia? → kokeile lyhyempää hakusanaa

2. hae_suositus — KÄYTÄ kun sinulla on URL tai suositustunnus (esim. hoi50056)
   → Palauttaa suosituksen otsikon, päivityspäivän, tekijät ja osioiden sisällöt

HAKUVINKKEJÄ:
- Käytä suomenkielisiä hakusanoja: "diabetes", "astma", "verenpaine", "sydän"
- Lyhyet sanat toimivat paremmin kuin pitkät
- Suositustunnukset alkavat "hoi" (esim. hoi50056 = Tyypin 2 diabetes)

MITÄ TÄMÄ PALVELIN EI VOI TEHDÄ:
- Hakea muiden maiden hoitosuosituksia
- Antaa henkilökohtaisia lääkärinohjeita
- Käyttää Duodecim-palvelun maksullista sisältöä

Tietolähde: https://www.kaypahoito.fi | Kieli: suomi
"""

mcp = FastMCP(
    name="Käypä hoito",
    instructions=INSTRUCTION_STRING,
    version="1.0.0",
    website_url="https://www.kaypahoito.fi/suositukset",
)

from tools_kaypahoito import hae_suositukset, hae_suositus

# CRITICAL: meta={"requires_permission": False} — prevents Intric from prompting user per call
mcp.tool(name="hae_suositukset", meta={"requires_permission": False})(hae_suositukset)
mcp.tool(name="hae_suositus", meta={"requires_permission": False})(hae_suositus)


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> PlainTextResponse:
    return PlainTextResponse("OK")


app = mcp.http_app()
