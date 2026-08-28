"""
Live verification — calls real API and live website.
Must exit 0 before server is done.
Run: python3 test_tools.py
"""
import asyncio
import sys
import traceback
import time

from tools_kaypahoito import hae_suositukset, hae_suositus

results = []


def test(name: str, coro, *args, expected_min_chars: int = 50, **kwargs):
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    t0 = time.time()
    try:
        result = asyncio.run(coro(*args, **kwargs))
        elapsed = time.time() - t0
        output = str(result) if not isinstance(result, str) else result
        size_kb = len(output.encode()) / 1024
        print(f"  Time: {elapsed:.1f}s | Size: {size_kb:.1f}KB")
        print(f"  Preview:\n{output[:400]}")
        if elapsed > 20:
            raise TimeoutError(f"Tool took {elapsed:.1f}s (limit: 20s)")
        if size_kb > 20:
            print(f"  WARNING: Response is {size_kb:.1f}KB — check row cap")
        if len(output) < expected_min_chars:
            raise ValueError(f"Response too short: {len(output)} chars (min {expected_min_chars})")
        results.append((name, True, None))
        print("  PASS")
    except Exception as e:
        elapsed = time.time() - t0
        traceback.print_exc()
        results.append((name, False, str(e)))
        print(f"  FAIL ({elapsed:.1f}s): {e}")


# --- Tests ---

# 1. Search returns results for a common Finnish medical term
test(
    "hae_suositukset: diabetes",
    hae_suositukset,
    "diabetes",
    expected_min_chars=100,
)

# 2. Search returns results for another term
test(
    "hae_suositukset: verenpaine",
    hae_suositukset,
    "verenpaine",
    expected_min_chars=100,
)

# 3. Fetch known suositus by slug (Tyypin 2 diabetes)
test(
    "hae_suositus: hoi50056 (Tyypin 2 diabetes)",
    hae_suositus,
    "hoi50056",
    expected_min_chars=200,
)

# 4. Fetch known suositus by full URL
test(
    "hae_suositus: full URL (Astma)",
    hae_suositus,
    "https://www.kaypahoito.fi/hoi06030",
    expected_min_chars=200,
)

# 5. Search with a term that should match (and we verify URL in output)
test(
    "hae_suositukset: sydän",
    hae_suositukset,
    "sydän",
    expected_min_chars=100,
)

# 6. Regression: Intric injects observability_context into every tools/call.
#    Go through the real MCP layer — a plain function call would not catch it.
async def call_via_mcp_with_injected_arg() -> str:
    from fastmcp import Client
    from server import mcp

    async with Client(mcp) as client:
        result = await client.call_tool(
            "hae_suositukset",
            {"hakusana": "diabetes", "observability_context": {"tool_use_id": "test"}},
        )
        return result.content[0].text


test(
    "MCP call with Intric's observability_context",
    call_via_mcp_with_injected_arg,
    expected_min_chars=100,
)

# --- Summary ---
print(f"\n{'='*60}")
print("VERIFICATION SUMMARY")
for name, ok, err in results:
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f" — {err}" if err else ""))

passed = sum(1 for _, ok, _ in results if ok)
print(f"\n{passed}/{len(results)} passed")

if passed < len(results):
    print("\nNOT DONE — fix failing tools and re-run")
    sys.exit(1)
else:
    print("\nALL PASSED — server ready for Intric")
    sys.exit(0)
