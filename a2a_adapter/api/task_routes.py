"""
Task execution and event routes
"""
from typing import Dict, Any, List, Callable, Optional, Union
from fastapi import APIRouter, Request, Response, status, HTTPException
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from ..core.rpc import (
    JSONRPCRequest, create_task_accepted_response,
    JSONRPCException, JSONRPCInvalidRequest, JSONRPCSkillNotFound, JSONRPCTaskNotFound,
    ErrorCodes, create_error_response
)
from ..core.lifecycle import create_task, task_exists, generate_task_events
from ..core.skills import extract_functions

def create_task_router(agent_obj: Any) -> APIRouter:
    """
    Create router for task-related endpoints
    
    Args:
        agent_obj: The agent object
        
    Returns:
        FastAPI router
    """
    router = APIRouter()
    
    # Extract agent functions
    agent_functions = extract_functions(agent_obj)
    
    @router.post("/tasks/send", status_code=status.HTTP_202_ACCEPTED)
    async def send_task(request: Request) -> JSONResponse:
        """
        Send a task to the agent
        
        This endpoint accepts a JSON-RPC request with method=tasks/send
        and returns a taskId that can be used to get the task events
        """
        try:
            # Parse the JSON-RPC request
            data = await request.json()
            # Validate with Pydantic model
            json_rpc_req = JSONRPCRequest.parse_obj(data)
            
            if json_rpc_req.method != "tasks/send":
                raise JSONRPCInvalidRequest("Method must be 'tasks/send'")
                
            skill_name = json_rpc_req.params.agentSkill
            args = json_rpc_req.params.input
            
            # Find the skill function
            fn = next((
                f for f in agent_functions
                if getattr(f, "_a2a_skill", None) == skill_name
            ), None)
            
            if fn is None:
                raise JSONRPCSkillNotFound(skill_name)
            
            # Create a task and get its ID
            task_id = await create_task(fn, args, json_rpc_req.id)
            
            # Return a JSON-RPC response with the task ID
            return create_task_accepted_response(json_rpc_req.id, task_id)
            
        except JSONRPCException as e:
            # Handle JSON-RPC exceptions
            return e.to_response(data.get("id", "") if 'data' in locals() else "")
        except Exception as e:
            # Handle unexpected exceptions
            return create_error_response(
                data.get("id", "") if 'data' in locals() else "",
                ErrorCodes.INTERNAL_ERROR,
                "Internal error",
                {"error": str(e)}
            )
    
    @router.get("/tasks/{task_id}/events")
    async def task_events(task_id: str) -> EventSourceResponse:
        """
        Get the events for a task
        
        This endpoint returns a Server-Sent Events stream with the task events
        """
        if not await task_exists(task_id):
            raise JSONRPCTaskNotFound(task_id)
            
        return EventSourceResponse(generate_task_events(task_id))
    
    return router