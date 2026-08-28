from contextlib import asynccontextmanager

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from middleware_compat import DropUnknownArgumentsMiddleware

INSTRUCTION_STRING = """
You are connected to Käypä hoito — Finland's national evidence-based clinical
guideline database (Finnish language). 139 guidelines covering all major conditions.

WORKFLOW:
1. hae_suositukset(hakusana=<Finnish keyword>)
   → USE FIRST when user asks about any medical topic
   → Returns actual guideline documents with URLs
   → If results found: call hae_suositus with URL from results
   → If no results: try shorter word or synonym

2. hae_suositus(url=<hoi-URL>)
   → USE when you have a URL (e.g. hoi50056)
   → Returns title, update date, and all clinical sections

SEARCH TIPS — use Finnish terms:
  diabetes, verenpaine, astma, sydän, masennus, kipu, syöpä, unettomuus
  Guideline IDs start with "hoi" (e.g. hoi50056 = Tyypin 2 diabetes)

CANNOT DO:
  - Guidelines from other countries
  - Personal medical advice
  - Paid Duodecim content

Source: https://www.kaypahoito.fi | Language: Finnish
"""

@asynccontextmanager
async def lifespan(server):
    """Warm the catalog cache on startup so the first search is instant."""
    from kaypahoito_client import get_catalog
    catalog = await get_catalog()
    print(f"[startup] Catalog warmed: {len(catalog)} suositukset")
    yield


mcp = FastMCP(
    name="Kaypa hoito",
    instructions=INSTRUCTION_STRING,
    version="1.1.1",
    website_url="https://www.kaypahoito.fi/suositukset",
    lifespan=lifespan,
    # Intric adds observability_context to every tools/call payload; without this
    # FastMCP rejects the call before the tool runs.
    middleware=[DropUnknownArgumentsMiddleware()],
)

from tools_kaypahoito import hae_suositukset, hae_suositus

# meta={"requires_permission": False} — prevents Intric from prompting the user on every call
mcp.tool(name="hae_suositukset", meta={"requires_permission": False})(hae_suositukset)
mcp.tool(name="hae_suositus", meta={"requires_permission": False})(hae_suositus)


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> PlainTextResponse:
    return PlainTextResponse("OK")


app = mcp.http_app()
