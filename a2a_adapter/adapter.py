from typing import Callable, Dict, Any, List
from functools import wraps
import inspect, uuid, asyncio, os
from fastapi import FastAPI, HTTPException
from sse_starlette.sse import EventSourceResponse
from .card import Skill, AgentCardData, AgentCard
from .registry import AgentCardRepo

_skill_registry: List[Skill] = []

def skill(name:str, inputs:List[str], outputs:List[str]):
    def decorator(fn:Callable):
        _skill_registry.append(Skill(name=name, inputs=inputs, outputs=outputs, description=fn.__doc__ or ""))
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            return await fn(*args, **kwargs) if inspect.iscoroutinefunction(fn) else fn(*args, **kwargs)
        wrapper._a2a_skill = name
        return wrapper
    return decorator

def register_agent(agent_obj, *, host:str="127.0.0.1", port:int=8080):
    card_data = AgentCardData(
        id=f"urn:agent:{agent_obj.name.replace(' ','_').lower()}",
        name=agent_obj.name,
        version=getattr(agent_obj, "version", "0.0.1"),
        description=getattr(agent_obj, "description", ""),
        skills=_skill_registry,
        endpoints={
            "tasks": f"http://{host}:{port}/tasks/send",
            "stream": f"http://{host}:{port}/tasks/subscribe"
        },
        extra={"framework": agent_obj.__class__.__module__}
    )
    repo = AgentCardRepo()
    repo.upsert(AgentCard.from_data(card_data))

    # Build FastAPI
    app = FastAPI(title=agent_obj.name)

    @app.post("/tasks/send")
    async def send_task(payload: Dict[str, Any]):
        skill_name = payload.get("agentSkill")
        args = payload.get("input")
        fn = next((f for f in _extract_functions(agent_obj) if getattr(f, "_a2a_skill", None)==skill_name), None)
        if fn is None:
            raise HTTPException(status_code=404, detail="Skill not found")
        tid = str(uuid.uuid4())
        async def event_generator():
            try:
                result = await fn(args) if inspect.iscoroutinefunction(fn) else fn(args)
                yield {"event":"completed","id":tid,"data":str(result)}
            except Exception as e:
                yield {"event":"failed","id":tid,"data":str(e)}
        return EventSourceResponse(event_generator())

    @app.get("/tasks/subscribe")
    async def noop():
        return {"message":"Use SSE via /tasks/send"}

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
