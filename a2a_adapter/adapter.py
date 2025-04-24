from typing import Callable, Dict, Any, List, Optional, AsyncGenerator
from functools import wraps
import inspect, uuid, asyncio, os
from fastapi import FastAPI, HTTPException, Request, Response, Depends, status
from sse_starlette.sse import EventSourceResponse
from .card import Skill, AgentCardData, AgentCard, JSONRPCRequest, JSONRPCResponse, JSONRPCError, TaskResponse
from .registry import AgentCardRepo
import json

_skill_registry: List[Skill] = []
_active_tasks = {}  # Store task executions

class JSONRPCException(Exception):
    def __init__(self, code: int, message: str, data: Optional[Dict[str, Any]] = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)

class JSONRPCInvalidRequest(JSONRPCException):
    def __init__(self, message: str = "Invalid Request"):
        super().__init__(code=-32600, message=message)

class JSONRPCMethodNotFound(JSONRPCException):
    def __init__(self, message: str = "Method not found"):
        super().__init__(code=-32601, message=message)

def skill(name: str, inputTypes: List[str], outputTypes: List[str]):
    def decorator(fn: Callable):
        _skill_registry.append(Skill(
            name=name,
            description=fn.__doc__ or "",
            inputTypes=inputTypes,
            outputTypes=outputTypes
        ))
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            return await fn(*args, **kwargs) if inspect.iscoroutinefunction(fn) else fn(*args, **kwargs)
        wrapper._a2a_skill = name
        return wrapper
    return decorator

def register_agent(agent_obj, *, host: str = "127.0.0.1", port: int = 8080):
    base_url = f"http://{host}:{port}"
    card_data = AgentCardData(
        id=f"urn:agent:{agent_obj.name.replace(' ','_').lower()}",
        name=agent_obj.name,
        version=getattr(agent_obj, "version", "0.0.1"),
        description=getattr(agent_obj, "description", ""),
        skills=_skill_registry,
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
    repo = AgentCardRepo()
    repo.upsert(AgentCard.from_data(card_data))

    # Build FastAPI
    app = FastAPI(title=agent_obj.name)

    @app.get("/agentCard")
    async def get_agent_card():
        return card_data

    @app.post("/tasks/send", status_code=status.HTTP_202_ACCEPTED)
    async def send_task(request: JSONRPCRequest):
        if request.method != "tasks/send":
            raise JSONRPCInvalidRequest("Method must be 'tasks/send'")
        
        skill_name = request.params.agentSkill
        args = request.params.input
        fn = next((f for f in _extract_functions(agent_obj) if getattr(f, "_a2a_skill", None)==skill_name), None)
        
        if fn is None:
            error = JSONRPCError(code=-32601, message=f"Skill '{skill_name}' not found")
            return JSONRPCResponse(id=request.id, error=error)
        
        task_id = str(uuid.uuid4())
        _active_tasks[task_id] = {
            "status": "accepted",
            "request_id": request.id,
            "function": fn,
            "args": args,
            "result": None,
            "error": None
        }
        
        # Start task execution in background
        asyncio.create_task(_execute_task(task_id))
        
        return TaskResponse(taskId=task_id)

    async def _execute_task(task_id: str):
        task = _active_tasks[task_id]
        fn = task["function"]
        args = task["args"]
        request_id = task["request_id"]
        
        try:
            task["status"] = "running"
            result = await fn(args) if inspect.iscoroutinefunction(fn) else fn(args)
            task["result"] = result
            task["status"] = "completed"
        except Exception as e:
            task["error"] = str(e)
            task["status"] = "failed"

    @app.get("/tasks/{task_id}/events")
    async def task_events(task_id: str):
        if task_id not in _active_tasks:
            raise HTTPException(status_code=404, detail="Task not found")
            
        async def event_generator() -> AsyncGenerator[Dict[str, Any], None]:
            task = _active_tasks[task_id]
            request_id = task["request_id"]
            
            # Send initial accepted event
            yield {
                "event": "accepted", 
                "data": json.dumps({
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"status": "accepted"}
                })
            }
            
            # Wait for task to start running
            while task["status"] == "accepted":
                await asyncio.sleep(0.1)
                
            # Send running event
            yield {
                "event": "running", 
                "data": json.dumps({
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"status": "running"}
                })
            }
            
            # Wait for task to complete or fail
            while task["status"] == "running":
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
                yield {
                    "event": "failed", 
                    "data": json.dumps({
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32000,
                            "message": "Task execution failed",
                            "data": {"error": task["error"]}
                        }
                    })
                }
                
        return EventSourceResponse(event_generator())

    @app.post("/search")
    async def skill_search(request: Dict[str, Any]):
        """JSON-RPC skills/search endpoint for A2A compatibility"""
        if request.get("method") != "skills/search":
            error = JSONRPCError(code=-32601, message="Method must be 'skills/search'")
            return JSONRPCResponse(id=request.get("id", ""), error=error)
            
        repo = AgentCardRepo()
        query = request.get("params", {}).get("query", "")
        results = repo.search(skill=query)
        
        return {
            "jsonrpc": "2.0",
            "id": request.get("id", ""),
            "result": {"agents": results}
        }

    import uvicorn, sys
    uvicorn.run(app, host=host, port=port, log_level="info")

def _extract_functions(agent_obj):
    # CrewAI agent.task objects keep python functions in .fn attr. For generic fallback inspect module
    funcs=[]
    if hasattr(agent_obj,"tasks"):
        for t in agent_obj.tasks:
            fn=getattr(t,"fn",None) or t
            funcs.append(fn)
    return funcs