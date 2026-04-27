import os
from typing import Any, Dict, Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
import httpx

MCP_ACCESS_TOKEN = os.getenv("MCP_ACCESS_TOKEN")
BACKEND_BASE_URL = os.getenv(
    "BACKEND_BASE_URL",
    "https://listing-intake-backend-production.up.railway.app",
)
BACKEND_API_KEY = os.getenv("BACKEND_API_KEY")

if not MCP_ACCESS_TOKEN:
    raise RuntimeError("MCP_ACCESS_TOKEN must be set in environment variables")


app = FastAPI(
    title="Listing Intake MCP",
    version="1.0.0",
    description="MCP wrapper for the Listing Intake v5 backend",
)


def check_mcp_auth(authorization: Optional[str]) -> None:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    try:
        scheme, token = authorization.split(" ", 1)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Authorization header")

    if scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid auth scheme")

    if token.strip() != MCP_ACCESS_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")


def backend_headers() -> Dict[str, str]:
    headers: Dict[str, str] = {
        "Accept": "application/json",
    }
    if BACKEND_API_KEY:
        headers["X-API-Key"] = BACKEND_API_KEY
    return headers


async def call_backend_get(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    url = BACKEND_BASE_URL.rstrip("/") + path
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(url, headers=backend_headers(), params=params)
        resp.raise_for_status()
        try:
            return resp.json()
        except ValueError:
            return {"raw": resp.text, "status_code": resp.status_code}


@app.post("/mcp")
async def mcp_endpoint(
    request: Request,
    authorization: Optional[str] = Header(None, alias="Authorization"),
):
    """
    Expected JSON:

    List tools:
      { "type": "list_tools" }

    Call tool:
      { "type": "call_tool", "tool": "health_check", "params": {} }
      { "type": "call_tool", "tool": "get_item", "params": { "itemNumber": "12345" } }
    """
    check_mcp_auth(authorization)

    body = await request.json()
    msg_type = body.get("type")

    if msg_type == "list_tools":
        tools = [
            {
                "name": "health_check",
                "description": "Check health of listing intake backend",
                "params_schema": {},
            },
            {
                "name": "list_items",
                "description": "List intake items (optional status filter)",
                "params_schema": {
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "description": "Filter by status (e.g. 'ready', 'pending')",
                        }
                    },
                    "required": [],
                },
            },
            {
                "name": "get_item",
                "description": "Get a specific intake item by itemNumber",
                "params_schema": {
                    "type": "object",
                    "properties": {
                        "itemNumber": {
                            "type": "string",
                            "description": "Item number to fetch",
                        }
                    },
                    "required": ["itemNumber"],
                },
            },
        ]
        return JSONResponse({"tools": tools})

    if msg_type == "call_tool":
        tool = body.get("tool")
        params = body.get("params") or {}

        if tool == "health_check":
            result = await call_backend_get("/health")
            return JSONResponse({"result": result})

        if tool == "list_items":
            status = params.get("status")
            query_params: Dict[str, Any] = {}
            if status:
                query_params["status"] = status
            result = await call_backend_get("/v1/intake/items", params=query_params)
            return JSONResponse({"result": result})

        if tool == "get_item":
            item_number = params.get("itemNumber")
            if not item_number:
                raise HTTPException(status_code=400, detail="itemNumber is required")
            path = f"/v1/intake/items/{item_number}"
            result = await call_backend_get(path)
            return JSONResponse({"result": result})

        raise HTTPException(status_code=400, detail=f"Unknown tool: {tool}")

    raise HTTPException(status_code=400, detail="Unsupported MCP message type")


@app.get("/")
async def root():
    return {"status": "ok", "message": "Listing Intake MCP is running"}
