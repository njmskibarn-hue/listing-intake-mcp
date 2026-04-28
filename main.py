import os
from typing import Any, Dict, Optional

import httpx
from fastmcp import FastMCP

MCP_ACCESS_TOKEN = os.getenv("MCP_ACCESS_TOKEN")
BACKEND_BASE_URL = os.getenv(
    "BACKEND_BASE_URL",
    "https://listing-intake-backend-production.up.railway.app",
).rstrip("/")
BACKEND_API_KEY = os.getenv("BACKEND_API_KEY")

if not MCP_ACCESS_TOKEN:
    raise RuntimeError("MCP_ACCESS_TOKEN must be set in environment variables")

mcp = FastMCP("listing-intake-mcp")


def _headers() -> Dict[str, str]:
    h = {"Accept": "application/json"}
    if BACKEND_API_KEY:
        h["X-API-Key"] = BACKEND_API_KEY
    return h


async def _get(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(BACKEND_BASE_URL + path, headers=_headers(), params=params)
        resp.raise_for_status()
        try:
            return resp.json()
        except ValueError:
            return {"raw": resp.text, "status_code": resp.status_code}


async def _patch(path: str, payload: Dict[str, Any]) -> Any:
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.patch(BACKEND_BASE_URL + path, headers=_headers(), json=payload)
        resp.raise_for_status()
        try:
            return resp.json()
        except ValueError:
            return {"raw": resp.text, "status_code": resp.status_code}


@mcp.tool()
async def health_check() -> dict:
    """Check health of the listing intake backend."""
    return await _get("/health")


@mcp.tool()
async def list_items(status: Optional[str] = None) -> dict:
    """List intake items. Pass status='ready', 'pending', or omit for all."""
    params = {"status": status} if status else {}
    return await _get("/v1/intake/items", params=params)


@mcp.tool()
async def get_item(item_number: str) -> dict:
    """Fetch a single intake item by its item number."""
    return await _get(f"/v1/intake/items/{item_number}")


@mcp.tool()
async def mark_item_complete(item_number: str) -> dict:
    """Mark an intake item as completed after a successful sheet write."""
    return await _patch(f"/v1/intake/items/{item_number}", {"status": "completed"})


@mcp.tool()
async def mark_item_listed(item_number: str) -> dict:
    """Mark an intake item as listed on eBay."""
    return await _patch(f"/v1/intake/items/{item_number}", {"status": "listed"})


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
    )
