"""
Server module for A2A Adapter

This module provides functions for building and running the A2A adapter server.
"""
from typing import Any, Dict, List, Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from .card import AgentCardData, AgentCard, Skill
from .core.skills import extract_skills
from .db.registry import AgentCardRepo
from .api.card_routes import create_card_router
from .api.task_routes import create_task_router

def build_app(agent_obj: Any, *, 
              host: str = "127.0.0.1", 
              port: int = 8080,
              card_data: Optional[AgentCardData] = None) -> FastAPI:
    """
    Build a FastAPI application for an agent
    
    Args:
        agent_obj: The agent object with skills
        host: Host to bind the server to
        port: Port to bind the server to
        card_data: Optional pre-populated agent card data
        
    Returns:
        FastAPI application
    """
    # Create FastAPI app
    app = FastAPI(
        title=agent_obj.name,
        description=getattr(agent_obj, "description", ""),
        version=getattr(agent_obj, "version", "0.0.1")
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Generate or use agent card data
    if card_data is None:
        # Extract skills
        skills = extract_skills(agent_obj)
        
        # Generate base URL
        base_url = f"http://{host}:{port}"
        
        # Create agent card
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
        
        # Save card to repository
        repo = AgentCardRepo()
        repo.upsert(AgentCard.from_data(card_data))
    
    # Register routes
    app.include_router(create_card_router(card_data))
    app.include_router(create_task_router(agent_obj))
    
    return app

def register_agent(agent_obj: Any, *, 
                   host: str = "127.0.0.1", 
                   port: int = 8080, 
                   dry_run: bool = False) -> FastAPI:
    """
    Register an agent and start the API server
    
    Args:
        agent_obj: The agent object with skills
        host: Host to bind the server to
        port: Port to bind the server to
        dry_run: If True, don't start the server (for testing)
        
    Returns:
        FastAPI application
    """
    # Build app
    app = build_app(agent_obj, host=host, port=port)
    
    # If dry_run, just return the app
    if dry_run:
        return app
    
    # Start server
    uvicorn.run(app, host=host, port=port, log_level="info")
    
    # This line is never reached during normal operation
    return app