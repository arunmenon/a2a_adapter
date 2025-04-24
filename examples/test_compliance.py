#!/usr/bin/env python
"""
A2A Protocol Compliance Test Script

This script tests an A2A adapter implementation for compliance with the A2A protocol.
It performs the following tests:
1. Get the agent card
2. Send a task
3. Receive task events
4. Test error handling
"""

import httpx
import asyncio
import json
import sys
from pprint import pprint
from urllib.parse import urljoin

BASE_URL = "http://localhost:8080"

async def test_agent_card():
    """Test retrieving the agent card"""
    print("\n=== Testing Agent Card ===")
    async with httpx.AsyncClient() as client:
        response = await client.get(urljoin(BASE_URL, "/agentCard"))
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            card = response.json()
            print("Agent Card Fields:")
            
            # Check required fields
            required_fields = [
                "id", "name", "version", "description", "skills", 
                "url", "endpoints", "capabilities", "authentication",
                "defaultInputModes", "defaultOutputModes"
            ]
            
            for field in required_fields:
                if field in card:
                    print(f"✓ {field}")
                else:
                    print(f"✗ {field} - MISSING")
            
            # Check skills structure
            if "skills" in card and card["skills"]:
                skill = card["skills"][0]
                print("\nSkill Fields:")
                skill_fields = ["name", "description", "inputTypes", "outputTypes"]
                for field in skill_fields:
                    if field in skill:
                        print(f"✓ {field}")
                    else:
                        print(f"✗ {field} - MISSING")
            
            return card
        else:
            print(f"Error: {response.text}")
            return None

async def test_task_send(skill_name):
    """Test sending a task"""
    print("\n=== Testing Task Send ===")
    request_id = "test-request-123"
    
    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tasks/send",
        "params": {
            "agentSkill": skill_name,
            "input": "test query"
        }
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            urljoin(BASE_URL, "/tasks/send"),
            json=payload
        )
        
        print(f"Status: {response.status_code}")
        if response.status_code == 202:
            result = response.json()
            print("Response:")
            pprint(result)
            
            if "taskId" in result:
                return result["taskId"]
            else:
                print("Error: No taskId in response")
                return None
        else:
            print(f"Error: {response.text}")
            return None

async def test_task_events(task_id):
    """Test receiving task events"""
    print(f"\n=== Testing Task Events for {task_id} ===")
    
    events_url = urljoin(BASE_URL, f"/tasks/{task_id}/events")
    print(f"Connecting to {events_url}")
    
    async with httpx.AsyncClient(timeout=20.0) as client:
        async with client.stream("GET", events_url) as response:
            if response.status_code != 200:
                print(f"Error: {response.status_code} - {response.text}")
                return False
            
            required_events = {"accepted": False, "running": False, "completed": False}
            
            async for line in response.aiter_lines():
                line = line.strip()
                
                if not line or line == ":" or not line.startswith("data:"):
                    continue
                
                data = json.loads(line[5:])  # Extract JSON after "data:" prefix
                print(f"Event: {data.get('event')}")
                print(f"Data: {data.get('data')}")
                
                # Mark event as received
                event_type = data.get("event")
                if event_type in required_events:
                    required_events[event_type] = True
                
                # If we received the completed/failed event, we're done
                if event_type in ["completed", "failed"]:
                    break
    
    print("\nEvent Sequence:")
    for event, received in required_events.items():
        print(f"✓ {event}" if received else f"✗ {event} - MISSING")
    
    return all(required_events.values())

async def test_error_handling():
    """Test error handling"""
    print("\n=== Testing Error Handling ===")
    request_id = "test-error-123"
    
    # Test with non-existent skill
    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tasks/send",
        "params": {
            "agentSkill": "nonExistentSkill",
            "input": "test query"
        }
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            urljoin(BASE_URL, "/tasks/send"),
            json=payload
        )
        
        print(f"Status: {response.status_code}")
        print("Response:")
        pprint(response.json())
        
        # Check for proper error structure
        data = response.json()
        if "error" in data and "code" in data["error"] and "message" in data["error"]:
            print("✓ Proper error structure (code, message)")
            return True
        else:
            print("✗ Incorrect error structure")
            return False

async def main():
    print("A2A Protocol Compliance Test")
    print("===========================")
    
    # Test 1: Get Agent Card
    card = await test_agent_card()
    if not card:
        print("❌ Agent Card test failed")
        return
    
    # Get the first skill name for testing
    if "skills" in card and card["skills"]:
        skill_name = card["skills"][0]["name"]
    else:
        print("❌ No skills found in agent card")
        return
    
    # Test 2: Send a task
    task_id = await test_task_send(skill_name)
    if not task_id:
        print("❌ Task Send test failed")
        return
    
    # Test 3: Receive task events
    events_success = await test_task_events(task_id)
    if not events_success:
        print("❌ Task Events test failed")
        return
    
    # Test 4: Error handling
    error_success = await test_error_handling()
    if not error_success:
        print("❌ Error Handling test failed")
        return
    
    print("\n=== SUMMARY ===")
    print("✅ All tests passed! Your implementation is A2A-compatible.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        BASE_URL = sys.argv[1]
    
    asyncio.run(main())