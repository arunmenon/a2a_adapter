"""
Task lifecycle management for A2A Adapter

This module provides task storage and event generation for A2A tasks.
"""
from typing import Dict, Any, Optional, List, AsyncGenerator, Callable, Union
import asyncio
import time
import json
import uuid
import inspect
from .rpc import format_sse_event

# Global task store
# Maps task_id to task state
_tasks: Dict[str, Dict[str, Any]] = {}

def create_task(skill_fn: Callable, args: Any, request_id: Union[str, int]) -> str:
    """
    Create a new task
    
    Args:
        skill_fn: The skill function to execute
        args: Arguments to pass to the function
        request_id: The original JSON-RPC request ID
        
    Returns:
        Task ID
    """
    task_id = str(uuid.uuid4())
    _tasks[task_id] = {
        "status": "accepted",
        "request_id": request_id,
        "function": skill_fn,
        "args": args,
        "result": None,
        "error": None,
        "created_at": time.time(),
        "last_update": time.time()
    }
    
    # Start task execution in background
    asyncio.create_task(_execute_task(task_id))
    
    return task_id

async def _execute_task(task_id: str) -> None:
    """
    Execute a task
    
    This function is called in the background to execute a task
    and update its status
    
    Args:
        task_id: The task ID
    """
    if task_id not in _tasks:
        return
        
    task = _tasks[task_id]
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

def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a task by ID
    
    Args:
        task_id: The task ID
        
    Returns:
        Task data or None if not found
    """
    return _tasks.get(task_id)

def task_exists(task_id: str) -> bool:
    """
    Check if a task exists
    
    Args:
        task_id: The task ID
        
    Returns:
        True if task exists, False otherwise
    """
    return task_id in _tasks

async def generate_task_events(task_id: str) -> AsyncGenerator[Dict[str, str], None]:
    """
    Generate events for a task
    
    Args:
        task_id: The task ID
        
    Yields:
        Server-Sent Events for the task
    """
    if not task_exists(task_id):
        raise KeyError(f"Task {task_id} not found")
        
    task = _tasks[task_id]
    request_id = task["request_id"]
    heartbeat_interval = 10  # seconds
    last_heartbeat = time.time()
    
    # Send initial accepted event
    yield format_sse_event("accepted", request_id, {})
    
    # Wait for task to start running with timeout
    timeout_start = time.time()
    while task["status"] == "accepted":
        # Send heartbeat if needed
        if time.time() - last_heartbeat > heartbeat_interval:
            yield format_sse_event("heartbeat", request_id, {"timestamp": time.time()})
            last_heartbeat = time.time()
            
        # Check timeout (30 seconds)
        if time.time() - timeout_start > 30:
            task["status"] = "failed"
            task["error"] = "Task execution timed out waiting to start"
            break
            
        await asyncio.sleep(0.1)
    
    # Send running event if task didn't fail during startup
    if task["status"] == "running":
        yield format_sse_event("running", request_id, {})
        
        # Wait for task to complete or fail, sending heartbeats
        while task["status"] == "running":
            # Send heartbeat if needed
            if time.time() - last_heartbeat > heartbeat_interval:
                yield format_sse_event("heartbeat", request_id, {"timestamp": time.time()})
                last_heartbeat = time.time()
                
            await asyncio.sleep(0.1)
    
    # Send final event
    if task["status"] == "completed":
        yield format_sse_event("completed", request_id, task["result"])
    else:
        yield format_sse_event("failed", request_id, {"error": task["error"]})