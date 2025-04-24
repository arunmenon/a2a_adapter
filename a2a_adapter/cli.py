#!/usr/bin/env python
"""
A2A Adapter CLI - Command line interface for running A2A adapter
"""

import typer
import uvicorn
import importlib.util
import sys
import os
from pathlib import Path
from typing import Optional

from . import __version__
from .adapter import build_app, _extract_skills, AgentCardData
from .registry import AgentCardRepo
from .card import AgentCard

app = typer.Typer(help="A2A Adapter CLI")

def load_agent_module(module_path: str, agent_name: Optional[str] = None):
    """
    Load an agent module from a Python file
    
    Args:
        module_path: Path to Python file
        agent_name: Name of agent variable in the module
        
    Returns:
        Loaded agent object
    """
    path = Path(module_path).resolve()
    
    if not path.exists():
        typer.echo(f"Error: File {path} does not exist")
        raise typer.Exit(code=1)
    
    # Load module
    spec = importlib.util.spec_from_file_location("agent_module", path)
    if spec is None or spec.loader is None:
        typer.echo(f"Error: Could not load module from {path}")
        raise typer.Exit(code=1)
        
    module = importlib.util.module_from_spec(spec)
    sys.modules["agent_module"] = module
    spec.loader.exec_module(module)
    
    # Find agent object
    if agent_name:
        if not hasattr(module, agent_name):
            typer.echo(f"Error: Agent '{agent_name}' not found in {path}")
            raise typer.Exit(code=1)
        return getattr(module, agent_name)
    
    # Try to find agent by common names
    for name in ["agent", "Agent", "AGENT"]:
        if hasattr(module, name):
            return getattr(module, name)
    
    # Look for any object with tasks attribute
    for name in dir(module):
        obj = getattr(module, name)
        if hasattr(obj, "tasks") and callable(getattr(obj.tasks, "__iter__", None)):
            return obj
    
    typer.echo(f"Error: Could not find agent in {path}. Please specify agent name with --agent")
    raise typer.Exit(code=1)

@app.command()
def serve(
    module_path: str = typer.Argument(..., help="Path to Python file with agent definition"),
    agent_name: Optional[str] = typer.Option(None, "--agent", "-a", help="Name of agent variable in module"),
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host to bind server to"),
    port: int = typer.Option(8080, "--port", "-p", help="Port to bind server to"),
    reload: bool = typer.Option(False, "--reload", "-r", help="Enable auto-reload on file changes"),
    log_level: str = typer.Option("info", "--log-level", "-l", help="Logging level"),
):
    """
    Start A2A adapter server
    
    This command loads an agent module and starts an A2A adapter server for it.
    """
    try:
        # Load agent
        agent = load_agent_module(module_path, agent_name)
        
        # Extract skills
        skills = _extract_skills(agent)
        if not skills:
            typer.echo("Warning: No skills found in agent. Make sure they are decorated with @skill")
        else:
            typer.echo(f"Found {len(skills)} skills: {', '.join(s.name for s in skills)}")
        
        # Create agent card
        base_url = f"http://{host}:{port}"
        card_data = AgentCardData(
            id=f"urn:agent:{agent.name.replace(' ','_').lower()}",
            name=agent.name,
            version=getattr(agent, "version", "0.0.1"),
            description=getattr(agent, "description", ""),
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
            extra={"framework": agent.__class__.__module__}
        )
        
        # Save card to registry
        repo = AgentCardRepo()
        repo.upsert(AgentCard.from_data(card_data))
        
        # Build application
        app = build_app(agent, card_data=card_data)
        
        # Start server
        typer.echo(f"Starting A2A adapter server on {host}:{port}")
        typer.echo(f"Agent: {agent.name} ({getattr(agent, 'version', '0.0.1')})")
        typer.echo(f"Skills: {', '.join(s.name for s in skills)}")
        typer.echo(f"OpenAPI docs: http://{host}:{port}/docs")
        
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level=log_level,
            reload=reload,
            reload_includes=[os.path.abspath(module_path)] if reload else None,
        )
    except Exception as e:
        typer.echo(f"Error: {e}")
        raise typer.Exit(code=1)

@app.command()
def version():
    """Show A2A adapter version"""
    typer.echo(f"A2A Adapter v{__version__}")

if __name__ == "__main__":
    app()