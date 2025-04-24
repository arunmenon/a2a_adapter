from typing import Callable, Dict, Any, List, Optional, AsyncGenerator, Union, TypeVar
from functools import wraps
import inspect, uuid, asyncio, os, time
from fastapi import FastAPI, HTTPException, Request, Response, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
from .card import (
    Skill, AgentCardData, AgentCard, 
    JSONRPCRequest, JSONRPCResponse, JSONRPCError, 
    TaskResponse, JSONRPCErrorData, SearchRequest
)
from .registry import AgentCardRepo
import json
from typing import Dict, Set, Callable, Any, Optional, List, Type, TypeVar, cast

# Type variable for generic function
F = TypeVar('F', bound=Callable[..., Any])

# Global store of active tasks and their state
_active_tasks: Dict[str, Dict[str, Any]] = {}

# JSON-RPC Error codes
class ErrorCodes:
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    SERVER_ERROR_START = -32000
    SERVER_ERROR_END = -32099
    TASK_NOT_FOUND = -32001
    SKILL_NOT_FOUND = -32002

class JSONRPCException(Exception):
    """Base exception for JSON-RPC errors with proper error handling"""
    def __init__(self, code: int, message: str, data: Optional[Dict[str, Any]] = None):
        self.code = code
        self.message = message
        self.data = JSONRPCErrorData(error=message, details=data)
        super().__init__(message)
    
    def to_response(self, request_id: Union[str, int]) -> JSONResponse:
        """Convert exception to proper JSON-RPC response"""
        error = JSONRPCError(code=self.code, message=self.message, data=self.data)
        response = JSONRPCResponse(jsonrpc="2.0", id=request_id, error=error)
        return JSONResponse(content=response.dict(exclude_none=True))

class JSONRPCInvalidRequest(JSONRPCException):
    def __init__(self, message: str = "Invalid Request"):
        super().__init__(code=ErrorCodes.INVALID_REQUEST, message=message)

class JSONRPCMethodNotFound(JSONRPCException):
    def __init__(self, message: str = "Method not found"):
        super().__init__(code=ErrorCodes.METHOD_NOT_FOUND, message=message)

class JSONRPCSkillNotFound(JSONRPCException):
    def __init__(self, skill_name: str):
        super().__init__(
            code=ErrorCodes.SKILL_NOT_FOUND, 
            message=f"Skill '{skill_name}' not found"
        )

class JSONRPCTaskNotFound(JSONRPCException):
    def __init__(self, task_id: str):
        super().__init__(
            code=ErrorCodes.TASK_NOT_FOUND,
            message=f"Task '{task_id}' not found"
        )

def skill(name: str, inputTypes: List[str], outputTypes: List[str]) -> Callable[[F], F]:
    """
    Decorator to mark a function as an A2A skill
    
    Args:
        name: Name of the skill
        inputTypes: List of accepted input types
        outputTypes: List of output types produced by the skill
    """
    def decorator(fn: F) -> F:
        skill_def = Skill(
            name=name,
            description=fn.__doc__ or "",
            inputTypes=inputTypes,
            outputTypes=outputTypes
        )
        
        # Store skills in function's attribute to avoid global registry
        if not hasattr(fn, "_a2a_skills"):
            fn._a2a_skills = []
        fn._a2a_skills.append(skill_def)
        
        # Mark the function with skill name for discovery
        fn._a2a_skill = name
        
        @wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            """Wraps the function to handle both sync and async functions"""
            if inspect.iscoroutinefunction(fn):
                return await fn(*args, **kwargs)
            else:
                return fn(*args, **kwargs)
        
        # Copy skill attributes to wrapper
        wrapper._a2a_skill = name
        wrapper._a2a_skills = fn._a2a_skills
        
        return cast(F, wrapper)
    return decorator

def build_app(agent_obj: Any, *, card_data: AgentCardData) -> FastAPI:
    """
    Build a FastAPI application for the given agent
    
    This function extracts the API building logic from register_agent
    to allow more flexibility and testing
    
    Args:
        agent_obj: The agent object with skills
        card_data: The agent card data
        
    Returns:
        FastAPI application
    """
    app = FastAPI(
        title=agent_obj.name,
        description=getattr(agent_obj, "description", ""),
        version=getattr(agent_obj, "version", "0.0.1")
    )
    
    # Add CORS middleware for better interoperability
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Extract skills from agent
    agent_skills = _extract_skills(agent_obj)
    
    # API endpoints definition
    @app.get("/agentCard", response_model=Dict[str, Any])
    async def get_agent_card() -> Dict[str, Any]:
        """Get the agent card"""
        return card_data.__dict__
    
    @app.post("/tasks/send", status_code=status.HTTP_202_ACCEPTED)
    async def send_task(request: JSONRPCRequest) -> TaskResponse:
        """
        Send a task to the agent
        
        This endpoint accepts a JSON-RPC request with method=tasks/send
        and returns a taskId that can be used to get the task events
        """
        if request.method != "tasks/send":
            raise JSONRPCInvalidRequest("Method must be 'tasks/send'")
        
        skill_name = request.params.agentSkill
        args = request.params.input
        
        # Find the skill function
        fn = next((
            f for f in _extract_functions(agent_obj) 
            if getattr(f, "_a2a_skill", None) == skill_name
        ), None)
        
        if fn is None:
            raise JSONRPCSkillNotFound(skill_name)
        
        # Create a task ID and store the task
        task_id = str(uuid.uuid4())
        _active_tasks[task_id] = {
            "status": "accepted",
            "request_id": request.id,
            "function": fn,
            "args": args,
            "result": None,
            "error": None,
            "created_at": time.time(),
            "last_update": time.time()
        }
        
        # Start task execution in background
        asyncio.create_task(_execute_task(task_id))
        
        # Return a JSON-RPC response with the task ID
        return TaskResponse(
            jsonrpc="2.0",
            id=request.id,
            result={"taskId": task_id, "status": "accepted"}
        )
    
    async def _execute_task(task_id: str) -> None:
        """
        Execute a task
        
        This function is called in the background to execute a task
        and update its status
        """
        if task_id not in _active_tasks:
            return
            
        task = _active_tasks[task_id]
        fn = task["function"]
        args = task["args"]
        
        try:
            # Update task status to running
            task["status"] = "running"
            task["last_update"] = time.time()
            
            # Execute function
            result = await fn(args) if inspect.iscoroutinefunction(fn) else fn(args)
            
            # Update task with result
            task["result"] = result
            task["status"] = "completed"
            task["last_update"] = time.time()
        except Exception as e:
            # Handle exceptions and update task status
            task["error"] = str(e)
            task["status"] = "failed"
            task["last_update"] = time.time()
    
    @app.get("/tasks/{task_id}/events")
    async def task_events(task_id: str) -> EventSourceResponse:
        """
        Get the events for a task
        
        This endpoint returns a Server-Sent Events stream with the task events
        """
        if task_id not in _active_tasks:
            raise JSONRPCTaskNotFound(task_id)
        
        async def event_generator() -> AsyncGenerator[Dict[str, Any], None]:
            """Generate SSE events for the task"""
            task = _active_tasks[task_id]
            request_id = task["request_id"]
            heartbeat_interval = 10  # seconds
            last_heartbeat = time.time()
            
            # Send initial accepted event
            yield {
                "event": "accepted", 
                "data": json.dumps({
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"status": "accepted"}
                })
            }
            
            # Wait for task to start running with timeout
            timeout_start = time.time()
            while task["status"] == "accepted":
                # Send heartbeat if needed
                if time.time() - last_heartbeat > heartbeat_interval:
                    yield {
                        "event": "heartbeat",
                        "data": json.dumps({
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "result": {"status": "accepted", "timestamp": time.time()}
                        })
                    }
                    last_heartbeat = time.time()
                    
                # Check timeout (30 seconds)
                if time.time() - timeout_start > 30:
                    task["status"] = "failed"
                    task["error"] = "Task execution timed out waiting to start"
                    break
                    
                await asyncio.sleep(0.1)
            
            # Send running event if task didn't fail during startup
            if task["status"] == "running":
                yield {
                    "event": "running", 
                    "data": json.dumps({
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {"status": "running"}
                    })
                }
                
                # Wait for task to complete or fail, sending heartbeats
                while task["status"] == "running":
                    # Send heartbeat if needed
                    if time.time() - last_heartbeat > heartbeat_interval:
                        yield {
                            "event": "heartbeat",
                            "data": json.dumps({
                                "jsonrpc": "2.0",
                                "id": request_id,
                                "result": {"status": "running", "timestamp": time.time()}
                            })
                        }
                        last_heartbeat = time.time()
                        
                    await asyncio.sleep(0.1)
            
            # Send final event
            if task["status"] == "completed":
                yield {
                    "event": "completed", 
                    "data": json.dumps({
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {"status": "completed", "data": task["result"]}
                    })
                }
            else:
                # Build proper error response
                error_data = JSONRPCErrorData(error=task["error"])
                yield {
                    "event": "failed", 
                    "data": json.dumps({
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": ErrorCodes.SERVER_ERROR_START,
                            "message": "Task execution failed",
                            "data": error_data.dict(exclude_none=True)
                        }
                    })
                }
                
        return EventSourceResponse(event_generator())
    
    @app.post("/search")
    async def skill_search(request: Request) -> JSONResponse:
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
            
            # Perform search
            repo = AgentCardRepo()
            results = repo.search(skill=query, domain=domain)
            
            # Return JSON-RPC formatted response
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"agents": results}
            })
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
    
    return app

def register_agent(agent_obj: Any, *, host: str = "127.0.0.1", port: int = 8080) -> None:
    """
    Register an agent and start the API server
    
    Args:
        agent_obj: The agent object with skills
        host: Host to bind the server to
        port: Port to bind the server to
    """
    # Generate base URL for the agent
    base_url = f"http://{host}:{port}"
    
    # Extract skills from agent
    skills = _extract_skills(agent_obj)
    
    # Create agent card data
    card_data = AgentCardData(
        id=f"urn:agent:{agent_obj.name.replace(' ','_').lower()}",
        name=agent_obj.name,
        version=getattr(agent_obj, "version", "0.0.1"),
        description=getattr(agent_obj, "description", ""),
        skills=skills,
        url=base_url,
        endpoints={
            "tasks": f"{base_url}/tasks/send",
            "events": f"{base_url}/tasks/{{taskId}}/events"
        },
        capabilities={"streaming": True},
        authentication={"schemes": ["none"]},
        defaultInputModes=["text"],
        defaultOutputModes=["text"],
        extra={"framework": agent_obj.__class__.__module__}
    )
    
    # Save agent card to registry
    repo = AgentCardRepo()
    repo.upsert(AgentCard.from_data(card_data))
    
    # Build and run the FastAPI application
    app = build_app(agent_obj, card_data=card_data)
    
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="info")

def _extract_skills(agent_obj: Any) -> List[Skill]:
    """
    Extract skills from an agent object
    
    Args:
        agent_obj: The agent object
        
    Returns:
        List of skills
    """
    functions = _extract_functions(agent_obj)
    skills: List[Skill] = []
    
    for fn in functions:
        if hasattr(fn, "_a2a_skills"):
            skills.extend(fn._a2a_skills)
    
    return skills

def _extract_functions(agent_obj: Any) -> List[Callable]:
    """
    Extract functions from an agent object
    
    This function tries to extract functions from common agent frameworks
    
    Args:
        agent_obj: The agent object
        
    Returns:
        List of functions
    """
    funcs = []
    
    # Extract functions from CrewAI agent
    if hasattr(agent_obj, "tasks"):
        for t in agent_obj.tasks:
            fn = getattr(t, "fn", None) or t
            funcs.append(fn)
    
    # Extract functions from LangGraph agent (might have tools attribute)
    elif hasattr(agent_obj, "tools"):
        for t in agent_obj.tools:
            if callable(t):
                funcs.append(t)
            elif hasattr(t, "fn"):
                funcs.append(t.fn)
    
    return funcs