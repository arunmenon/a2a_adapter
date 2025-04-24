import pytest
import asyncio
from a2a_adapter.core.lifecycle import create_task, get_task, task_exists, generate_task_events

@pytest.mark.asyncio
async def test_task_lifecycle():
    """Test the full task lifecycle with concurrency"""
    # Create a test task function
    async def test_fn(args):
        await asyncio.sleep(0.1)  # Simulate work
        return f"Result: {args}"
    
    # Create a task
    task_id = await create_task(test_fn, "test input", "request-123")
    
    # Check task exists
    assert await task_exists(task_id)
    
    # Get initial task status
    task = await get_task(task_id)
    assert task is not None
    assert task["status"] in ["accepted", "running"]
    
    # Wait for completion
    for _ in range(20):  # Allow time for task to complete
        await asyncio.sleep(0.1)
        task = await get_task(task_id)
        if task["status"] == "completed":
            break
    
    # Check final state
    assert task["status"] == "completed"
    assert task["result"] == "Result: test input"
    
@pytest.mark.asyncio
async def test_task_events():
    """Test task events generation"""
    # Create a test task function
    async def test_fn(args):
        await asyncio.sleep(0.1)  # Simulate work
        return f"Result: {args}"
    
    # Create a task
    task_id = await create_task(test_fn, "test input", "request-123")
    
    # Collect events
    events = []
    async for event in generate_task_events(task_id):
        events.append(event["event"])
        if event["event"] == "completed":
            break
    
    # Verify event sequence
    assert "accepted" in events
    assert "running" in events
    assert "completed" in events
    
    # Verify order
    assert events.index("accepted") < events.index("running") < events.index("completed")
    
@pytest.mark.asyncio
async def test_concurrent_tasks():
    """Test multiple concurrent tasks"""
    # Create a test task function
    async def test_fn(args):
        await asyncio.sleep(0.1)
        return f"Result: {args}"
    
    # Create multiple tasks
    task_ids = []
    for i in range(5):
        task_id = await create_task(test_fn, f"input-{i}", f"request-{i}")
        task_ids.append(task_id)
    
    # Wait for all tasks to complete
    for _ in range(20):
        all_completed = True
        for task_id in task_ids:
            task = await get_task(task_id)
            if task["status"] != "completed":
                all_completed = False
                break
        if all_completed:
            break
        await asyncio.sleep(0.1)
    
    # Verify all tasks completed successfully
    for i, task_id in enumerate(task_ids):
        task = await get_task(task_id)
        assert task["status"] == "completed"
        assert task["result"] == f"Result: input-{i}"