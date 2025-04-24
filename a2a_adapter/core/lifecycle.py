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
_task_locks: Dict[str, asyncio.Lock] = {}  # Per-task locks

async def create_task(skill_fn: Callable, args: Any, request_id: Union[str, int]) -> str:
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
    
    # Create a lock for this task
    task_lock = asyncio.Lock()
    _task_locks[task_id] = task_lock
    
    # Create the task with initial state
    async with task_lock:
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
    if task_id not in _tasks or task_id not in _task_locks:
        return
        
    lock = _task_locks[task_id]
    
    try:
        # Get task data
        fn = None
        args = None
        async with lock:
            if task_id not in _tasks:
                return
            task = _tasks[task_id]
            fn = task["function"]
            args = task["args"]
            # Update task status to running
            task["status"] = "running"
            task["last_update"] = time.time()
        
        # Execute function outside the lock
        result = await fn(args) if inspect.iscoroutinefunction(fn) else fn(args)
        
        # Update task with result
        async with lock:
            if task_id in _tasks:
                _tasks[task_id]["result"] = result
                _tasks[task_id]["status"] = "completed"
                _tasks[task_id]["last_update"] = time.time()
    
    except Exception as e:
        # Handle exceptions and update task status
        async with lock:
            if task_id in _tasks:
                _tasks[task_id]["error"] = str(e)
                _tasks[task_id]["status"] = "failed"
                _tasks[task_id]["last_update"] = time.time()

async def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a task by ID
    
    Args:
        task_id: The task ID
        
    Returns:
        Task data or None if not found
    """
    if task_id not in _tasks or task_id not in _task_locks:
        return None
        
    lock = _task_locks[task_id]
    async with lock:
        return _tasks.get(task_id)

async def task_exists(task_id: str) -> bool:
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
    if task_id not in _tasks or task_id not in _task_locks:
        raise KeyError(f"Task {task_id} not found")
        
    lock = _task_locks[task_id]
    request_id = None
    task_status = None
    heartbeat_interval = 10  # seconds
    last_heartbeat = time.time()
    
    # Get initial task data with lock
    async with lock:
        task = _tasks[task_id]
        request_id = task["request_id"]
        task_status = task["status"]
    
    # Send initial accepted event
    yield format_sse_event("accepted", request_id, {})
    
    # Wait for task to start running with timeout
    timeout_start = time.time()
    while task_status == "accepted":
        # Send heartbeat if needed
        if time.time() - last_heartbeat > heartbeat_interval:
            yield format_sse_event("heartbeat", request_id, {"timestamp": time.time()})
            last_heartbeat = time.time()
            
        # Check timeout (30 seconds)
        if time.time() - timeout_start > 30:
            async with lock:
                if task_id in _tasks:
                    _tasks[task_id]["status"] = "failed"
                    _tasks[task_id]["error"] = "Task execution timed out waiting to start"
                    task_status = "failed"
            break
        
        # Check status with lock
        async with lock:
            if task_id in _tasks:
                task_status = _tasks[task_id]["status"]
            else:
                return  # Task was deleted
                
        await asyncio.sleep(0.1)
    
    # Send running event if task didn't fail during startup
    if task_status == "running":
        yield format_sse_event("running", request_id, {})
        
        # Wait for task to complete or fail, sending heartbeats
        while task_status == "running":
            # Send heartbeat if needed
            if time.time() - last_heartbeat > heartbeat_interval:
                yield format_sse_event("heartbeat", request_id, {"timestamp": time.time()})
                last_heartbeat = time.time()
                
            # Check status with lock
            async with lock:
                if task_id in _tasks:
                    task_status = _tasks[task_id]["status"]
                else:
                    return  # Task was deleted
                    
            await asyncio.sleep(0.1)
    
    # Send final event based on final status
    result = None
    error = None
    
    async with lock:
        if task_id in _tasks:
            result = _tasks[task_id].get("result")
            error = _tasks[task_id].get("error")
    
    if task_status == "completed":
        yield format_sse_event("completed", request_id, result)
    else:
        yield format_sse_event("failed", request_id, {"error": error})