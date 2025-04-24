"""
Agent card and discovery routes
"""
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from ..core.rpc import (
    create_success_response, create_error_response,
    JSONRPCException, JSONRPCMethodNotFound, ErrorCodes
)
from ..db.registry import AgentCardRepo
from ..card import JSONRPCResponse, JSONRPCError, JSONRPCErrorData

def create_card_router(card_data: Dict[str, Any]) -> APIRouter:
    """
    Create router for card-related endpoints
    
    Args:
        card_data: The agent card data
        
    Returns:
        FastAPI router
    """
    router = APIRouter()
    repo = AgentCardRepo()
    
    @router.get("/agentCard", response_model=Dict[str, Any])
    async def get_agent_card() -> Dict[str, Any]:
        """Get the agent card"""
        return card_data
    
    @router.get("/search")
    async def search_query(
        skill: Optional[str] = None, 
        domain: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for agents by skill or domain using URL parameters with pagination
        
        Args:
            skill: Optional skill name to search for
            domain: Optional domain to search for
            limit: Maximum number of results to return (pagination)
            offset: Number of results to skip (pagination)
            
        Returns:
            List of matching agent cards
        """
        return repo.search(skill=skill, domain=domain, limit=limit, offset=offset)
    
    @router.post("/search")
    async def search_jsonrpc(request: Request) -> JSONResponse:
        """
        Search for skills using JSON-RPC skills/search method
        
        This endpoint accepts a JSON-RPC request with method=skills/search
        and returns a list of agent cards matching the query
        """
        try:
            # Parse incoming JSON request
            data = await request.json()
            request_id = data.get("id", "")
            method = data.get("method", "")
            
            if method != "skills/search":
                raise JSONRPCMethodNotFound()
                
            # Extract search params
            params = data.get("params", {})
            query = params.get("query", "")
            domain = params.get("domain", None)
            limit = params.get("limit", None)
            offset = params.get("offset", None)
            
            # Perform search with pagination
            results = repo.search(
                skill=query, 
                domain=domain,
                limit=limit,
                offset=offset
            )
            
            # Return JSON-RPC formatted response
            return create_success_response(request_id, {"agents": results})
            
        except JSONRPCException as e:
            return e.to_response(data.get("id", "") if 'data' in locals() else "")
        except Exception as e:
            error = JSONRPCError(
                code=ErrorCodes.INTERNAL_ERROR,
                message="Internal error",
                data=JSONRPCErrorData(error=str(e))
            )
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": data.get("id", "") if 'data' in locals() else "",
                "error": error.dict(exclude_none=True)
            })
    
    return router