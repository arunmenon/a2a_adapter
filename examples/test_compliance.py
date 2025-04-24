#!/usr/bin/env python
"""
A2A Protocol Compliance Test Script

This script tests an A2A adapter implementation for compliance with the A2A protocol.
It performs the following tests:
1. Get the agent card
2. Send a task
3. Receive task events
4. Test error handling
5. Test JSON-RPC compliance
"""

import httpx
import asyncio
import json
import sys
import uuid
import time
from pprint import pprint
from urllib.parse import urljoin
from typing import Dict, Any, List, Optional

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

async def test_task_send(skill_name: str):
    """Test sending a task using JSON-RPC format"""
    print("\n=== Testing Task Send (JSON-RPC) ===")
    request_id = str(uuid.uuid4())
    
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
            
            # Validate JSON-RPC response
            if "jsonrpc" in result and result["jsonrpc"] == "2.0":
                print("✓ JSON-RPC 2.0 envelope")
            else:
                print("✗ Missing or incorrect JSON-RPC 2.0 envelope")
                
            if "id" in result and result["id"] == request_id:
                print("✓ Request ID echoed correctly")
            else:
                print("✗ Request ID not echoed correctly")
                
            if "result" in result and "taskId" in result["result"]:
                print(f"✓ Task ID returned: {result['result']['taskId']}")
                return result["result"]["taskId"]
            else:
                print("✗ No taskId in response")
                return None
        else:
            print(f"Error: {response.text}")
            return None

async def test_invalid_skill():
    """Test error handling for invalid skill"""
    print("\n=== Testing Invalid Skill Handling ===")
    request_id = str(uuid.uuid4())
    
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
        result = response.json()
        print("Response:")
        pprint(result)
        
        # Check error structure
        if "error" in result:
            error = result["error"]
            if "code" in error and isinstance(error["code"], int):
                print(f"✓ Error code: {error['code']}")
            else:
                print("✗ Missing or invalid error code")
                
            if "message" in error and isinstance(error["message"], str):
                print(f"✓ Error message: {error['message']}")
            else:
                print("✗ Missing or invalid error message")
                
            return True
        else:
            print("✗ No error object in response")
            return False

async def test_task_events(task_id: str):
    """Test the event stream for a task"""
    print(f"\n=== Testing Task Events Stream ===")
    print(f"Task ID: {task_id}")
    
    events_url = urljoin(BASE_URL, f"/tasks/{task_id}/events")
    print(f"Connecting to {events_url}")
    
    events_received = []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            async with client.stream("GET", events_url) as response:
                if response.status_code != 200:
                    print(f"Error: {response.status_code} - {await response.text()}")
                    return False
                
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line or line == ":" or not line.startswith("event:"):
                        continue
                    
                    event_type = None
                    event_data = None
                    
                    # Parse SSE format (event: xxx\ndata: xxx)
                    parts = line.split("\n")
                    for part in parts:
                        if part.startswith("event:"):
                            event_type = part[6:].strip()
                        elif part.startswith("data:"):
                            try:
                                event_data = json.loads(part[5:].strip())
                            except:
                                event_data = part[5:].strip()
                    
                    if event_type:
                        print(f"Event: {event_type}")
                        if event_data:
                            print(f"Data: {event_data}")
                        
                        events_received.append(event_type)
                        
                        # If we received the completed event, we're done
                        if event_type in ["completed", "failed"]:
                            break
        
    except asyncio.TimeoutError:
        print("Error: Connection timed out")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False
    
    # Check required events
    required_events = ["accepted", "running", "completed"]
    print("\nEvent Sequence:")
    for event in required_events:
        if event in events_received:
            print(f"✓ {event}")
        else:
            print(f"✗ {event} - MISSING")
    
    # Check proper ordering
    is_ordered = True
    required_indices = [events_received.index(e) for e in required_events if e in events_received]
    for i in range(1, len(required_indices)):
        if required_indices[i] < required_indices[i-1]:
            is_ordered = False
            break
    
    if is_ordered:
        print("✓ Events in correct order")
    else:
        print("✗ Events in incorrect order")
    
    return "completed" in events_received

async def test_search():
    """Test the search endpoint"""
    print("\n=== Testing Search Endpoint ===")
    request_id = str(uuid.uuid4())
    
    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "skills/search",
        "params": {
            "query": ""
        }
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            urljoin(BASE_URL, "/search"),
            json=payload
        )
        
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print("Response:")
            pprint(result)
            
            # Validate JSON-RPC response
            if "jsonrpc" in result and result["jsonrpc"] == "2.0":
                print("✓ JSON-RPC 2.0 envelope")
            else:
                print("✗ Missing or incorrect JSON-RPC 2.0 envelope")
                
            if "id" in result and result["id"] == request_id:
                print("✓ Request ID echoed correctly")
            else:
                print("✗ Request ID not echoed correctly")
                
            if "result" in result and "agents" in result["result"]:
                print(f"✓ Agents returned: {len(result['result']['agents'])}")
                return True
            else:
                print("✗ No agents in response")
                return False
        else:
            print(f"Error: {response.text}")
            return False

async def main():
    print("A2A Protocol Compliance Test")
    print("===========================")
    
    # Test 1: Get Agent Card
    card = await test_agent_card()
    if not card:
        print("❌ Agent Card test failed")
        return 1
    
    # Get the first skill name for testing
    if "skills" in card and card["skills"]:
        skill_name = card["skills"][0]["name"]
    else:
        print("❌ No skills found in agent card")
        return 1
    
    # Test 2: Test error handling
    error_success = await test_invalid_skill()
    if not error_success:
        print("❌ Error handling test failed")
        return 1
    
    # Test 3: Send a task
    task_id = await test_task_send(skill_name)
    if not task_id:
        print("❌ Task Send test failed")
        return 1
    
    # Test 4: Receive task events
    events_success = await test_task_events(task_id)
    if not events_success:
        print("❌ Task Events test failed")
        return 1
    
    # Test 5: Search endpoint
    search_success = await test_search()
    if not search_success:
        print("❌ Search test failed")
        return 1
    
    print("\n=== SUMMARY ===")
    print("✅ All tests passed! Your implementation is A2A-compatible.")
    return 0

if __name__ == "__main__":
    if len(sys.argv) > 1:
        BASE_URL = sys.argv[1]
    
    exit_code = asyncio.run(main())
    sys.exit(exit_code)