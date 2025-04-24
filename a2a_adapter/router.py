from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any, Callable, Optional
from .registry import AgentCardRepo
from .card import JSONRPCResponse, JSONRPCError

repo = AgentCardRepo()
router = APIRouter()

@router.get("/search")
async def search(skill: Optional[str] = None, domain: Optional[str] = None):
    """Legacy URL parameter-based search endpoint"""
    return repo.search(skill=skill, domain=domain)

@router.post("/search")
async def json_rpc_search(request: Request):
    """JSON-RPC compliant skills/search endpoint"""
    try:
        # Parse incoming JSON request
        data = await request.json()
        request_id = data.get("id", "")
        method = data.get("method", "")
        
        if method != "skills/search":
            error = JSONRPCError(code=-32601, message="Method must be 'skills/search'")
            return JSONRPCResponse(id=request_id, error=error)
        
        # Extract search params from request
        params = data.get("params", {})
        query = params.get("query", "")
        domain = params.get("domain", None)
        
        # Perform search
        results = repo.search(skill=query, domain=domain)
        
        # Return JSON-RPC formatted response
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"agents": results}
        }
    except Exception as e:
        return JSONRPCResponse(
            id=data.get("id", "") if 'data' in locals() else "",
            error=JSONRPCError(
                code=-32000,
                message="Internal error",
                data={"error": str(e)}
            )
        )