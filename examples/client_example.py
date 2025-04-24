#!/usr/bin/env python
"""
A2A Client Example

This script demonstrates how to interact with an A2A-compatible agent service.
"""

import asyncio
import httpx
import json
import sys
import uuid
from pprint import pprint
from urllib.parse import urljoin
import time
from typing import Dict, Any, List, Optional, Union

class A2AClient:
    """Client for interacting with A2A-compatible agents"""
    
    def __init__(self, base_url: str = "http://localhost:8080"):
        """
        Initialize the client
        
        Args:
            base_url: Base URL of the A2A-compatible service
        """
        self.base_url = base_url
        self.httpx_client = httpx.AsyncClient()
    
    async def close(self):
        """Close the HTTP client"""
        await self.httpx_client.aclose()
    
    async def get_agent_card(self) -> Dict[str, Any]:
        """
        Get the agent card
        
        Returns:
            Agent card data
        """
        response = await self.httpx_client.get(urljoin(self.base_url, "/agentCard"))
        response.raise_for_status()
        return response.json()
    
    async def send_task(self, skill_name: str, input_data: Union[str, Dict[str, Any]]) -> str:
        """
        Send a task to the agent
        
        Args:
            skill_name: Name of the skill to execute
            input_data: Input data for the skill
            
        Returns:
            Task ID
        """
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
        
        response = await self.httpx_client.post(
            urljoin(self.base_url, "/tasks/send"),
            json=payload
        )
        
        response.raise_for_status()
        result = response.json()
        
        if "error" in result:
            raise RuntimeError(f"Error: {result['error']['message']}")
            
        return result["result"]["taskId"]
    
    async def get_task_events(self, task_id: str):
        """
        Get events for a task
        
        Args:
            task_id: Task ID
            
        Yields:
            Event data
        """
        events_url = urljoin(self.base_url, f"/tasks/{task_id}/events")
        
        # Stream response
        async with self.httpx_client.stream("GET", events_url) as response:
            response.raise_for_status()
            
            async for line in response.aiter_lines():
                if not line.strip() or not line.startswith("event:"):
                    continue
                
                # Parse SSE message
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
                
                if event_type and event_data:
                    yield {"type": event_type, "data": event_data}
                    
                    # If event is completed or failed, stop streaming
                    if event_type in ["completed", "failed"]:
                        break
    
    async def search_skills(self, query: str = "", domain: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search for skills
        
        Args:
            query: Search query
            domain: Domain to filter by
            
        Returns:
            List of matching agent cards
        """
        request_id = str(uuid.uuid4())
        
        params = {"query": query}
        if domain:
            params["domain"] = domain
            
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "skills/search",
            "params": params
        }
        
        response = await self.httpx_client.post(
            urljoin(self.base_url, "/search"),
            json=payload
        )
        
        response.raise_for_status()
        result = response.json()
        
        if "error" in result:
            raise RuntimeError(f"Error: {result['error']['message']}")
            
        return result["result"]["agents"]
        
    async def execute_skill(self, skill_name: str, input_data: Union[str, Dict[str, Any]]) -> Any:
        """
        Execute a skill and wait for the result
        
        Args:
            skill_name: Name of the skill to execute
            input_data: Input data for the skill
            
        Returns:
            Skill execution result
        """
        # Send task
        task_id = await self.send_task(skill_name, input_data)
        
        # Wait for result
        async for event in self.get_task_events(task_id):
            if event["type"] == "completed":
                if "result" in event["data"] and "data" in event["data"]["result"]:
                    return event["data"]["result"]["data"]
                return None
            elif event["type"] == "failed":
                error = event["data"].get("error", {})
                message = error.get("message", "Unknown error")
                raise RuntimeError(f"Skill execution failed: {message}")
                
        raise RuntimeError("No completion event received")

async def main():
    """Main function"""
    print("A2A Client Example")
    print("=================")
    
    # Create client
    base_url = "http://localhost:8080"
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
        
    client = A2AClient(base_url)
    
    try:
        # Get agent card
        print("\nGetting agent card...")
        card = await client.get_agent_card()
        print(f"Agent: {card['name']} {card['version']}")
        print(f"Description: {card['description']}")
        
        # List skills
        if "skills" in card and card["skills"]:
            print("\nAvailable skills:")
            for i, skill in enumerate(card["skills"]):
                print(f"{i+1}. {skill['name']}: {skill['description']}")
                print(f"   Input types: {skill['inputTypes']}")
                print(f"   Output types: {skill['outputTypes']}")
        else:
            print("No skills available")
            return
            
        # Let user select a skill
        if len(card["skills"]) > 1:
            skill_idx = int(input("\nSelect skill (number): ")) - 1
            if skill_idx < 0 or skill_idx >= len(card["skills"]):
                print("Invalid selection")
                return
        else:
            skill_idx = 0
            
        skill = card["skills"][skill_idx]
        print(f"\nSelected skill: {skill['name']}")
        
        # Get input
        user_input = input(f"Enter input for {skill['name']}: ")
        if not user_input:
            user_input = "test query"
            
        # Execute skill
        print(f"\nExecuting skill {skill['name']}...")
        print("Streaming events:")
        
        # Send task
        task_id = await client.send_task(skill["name"], user_input)
        print(f"Task ID: {task_id}")
        
        # Stream events
        async for event in client.get_task_events(task_id):
            event_type = event["type"]
            event_data = event["data"]
            
            print(f"Event: {event_type}")
            
            # Format result or error
            if event_type == "completed" and "result" in event_data and "data" in event_data["result"]:
                print("Result:")
                pprint(event_data["result"]["data"])
            elif event_type == "failed" and "error" in event_data:
                print("Error:")
                pprint(event_data["error"])
    finally:
        # Close client
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())