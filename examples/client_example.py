#!/usr/bin/env python
"""
A2A Client Example

This script demonstrates how to interact with an A2A-compatible agent service.
"""

import asyncio
import httpx
import json
import sys
from pprint import pprint
from urllib.parse import urljoin
import uuid
import sseclient

BASE_URL = "http://localhost:8080"

async def get_agent_card():
    """Get the agent card from the service"""
    print("Fetching agent card...")
    async with httpx.AsyncClient() as client:
        response = await client.get(urljoin(BASE_URL, "/agentCard"))
        if response.status_code == 200:
            card = response.json()
            print("Agent Card:")
            pprint(card)
            return card
        else:
            print(f"Error: {response.text}")
            return None

async def send_task(skill_name, input_data):
    """Send a task to the agent"""
    print(f"\nSending task with skill '{skill_name}'...")
    request_id = str(uuid.uuid4())
    
    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tasks/send",
        "params": {
            "agentSkill": skill_name,
            "input": input_data
        }
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            urljoin(BASE_URL, "/tasks/send"),
            json=payload
        )
        
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
            print(f"Error: {response.status_code} - {response.text}")
            return None

def process_events(task_id):
    """Process events from the task using SSE"""
    print(f"\nProcessing events for task {task_id}...")
    
    events_url = urljoin(BASE_URL, f"/tasks/{task_id}/events")
    print(f"Connecting to {events_url}")
    
    with httpx.Client() as client:
        response = client.get(events_url, stream=True)
        if response.status_code != 200:
            print(f"Error: {response.status_code} - {response.text}")
            return False
        
        client = sseclient.SSEClient(response)
        
        for event in client.events():
            print(f"Event: {event.event}")
            try:
                data = json.loads(event.data)
                print("Data:")
                pprint(data)
            except json.JSONDecodeError:
                print(f"Raw data: {event.data}")
            
            # If we receive a completed or failed event, we're done
            if event.event in ["completed", "failed"]:
                break
    
    return True

async def main():
    print("A2A Client Example")
    print("=================")
    
    # Get the agent card
    card = await get_agent_card()
    if not card:
        return
    
    # Get the first skill name for testing
    if "skills" in card and card["skills"]:
        skill = card["skills"][0]
        skill_name = skill["name"]
        print(f"\nFound skill: {skill_name}")
        print(f"Description: {skill.get('description', 'No description')}")
        print(f"Input types: {skill.get('inputTypes', [])}")
        print(f"Output types: {skill.get('outputTypes', [])}")
    else:
        print("No skills found in agent card")
        return
    
    # Get user input
    user_input = input("\nEnter input for the skill: ")
    if not user_input:
        user_input = "default query"
    
    # Send a task
    task_id = await send_task(skill_name, user_input)
    if not task_id:
        return
    
    # Process events
    process_events(task_id)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        BASE_URL = sys.argv[1]
    
    try:
        import sseclient
    except ImportError:
        print("Error: sseclient-py package is required.")
        print("Install it with: pip install sseclient-py")
        sys.exit(1)
        
    asyncio.run(main())