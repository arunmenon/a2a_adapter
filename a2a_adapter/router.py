from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any, Callable, Optional, List, Union
from pydantic import BaseModel
from .registry import AgentCardRepo
from .card import JSONRPCResponse, JSONRPCError, JSONRPCErrorData, SearchParams, SearchRequest

class Router:
    """Router class for handling A2A API endpoints"""
    
    def __init__(self):
        self.router = APIRouter()
        self.repo = AgentCardRepo()
        
        # Register routes
        self.router.add_api_route("/search", self.search_query, methods=["GET"])
        self.router.add_api_route("/search", self.search_jsonrpc, methods=["POST"])
    
    async def search_query(self, skill: Optional[str] = None, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search for agents by skill or domain using URL parameters
        
        Args:
            skill: Optional skill name to search for
            domain: Optional domain to search for
            
        Returns:
            List of matching agent cards
        """
        return self.repo.search(skill=skill, domain=domain)
    
    async def search_jsonrpc(self, request: SearchRequest) -> Dict[str, Any]:
        """
        Search for agents by skill or domain using JSON-RPC
        
        Args:
            request: JSON-RPC request
            
        Returns:
            JSON-RPC response
        """
        # Verify method is skills/search
        if request.method != "skills/search":
            return JSONRPCResponse(
                id=request.id,
                error=JSONRPCError(
                    code=-32601,
                    message="Method not found",
                    data=JSONRPCErrorData(error="Method must be 'skills/search'")
                )
            ).dict(exclude_none=True)
        
        # Extract query parameters
        query = request.params.query
        domain = request.params.domain
        
        # Perform search
        results = self.repo.search(skill=query, domain=domain)
        
        # Return results
        return {
            "jsonrpc": "2.0",
            "id": request.id,
            "result": {"agents": results}
        }


# Create router instance for FastAPI app
router = Router().router