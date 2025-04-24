"""
CrewAI integration for A2A Adapter
"""
from ..core.skills import skill
from ..server import register_agent
from typing import List, Optional, Callable, Any

def adapt_crewai_agent(agent, host: str = "127.0.0.1", port: int = 8080):
    """
    Adapt a CrewAI agent to be A2A-compatible
    
    Args:
        agent: A CrewAI agent object
        host: Host to run the adapter on
        port: Port to run the adapter on
    """
    register_agent(agent, host=host, port=port)

def crewai_skill(name: str, inputTypes: List[str] = ["text"], outputTypes: List[str] = ["text"], description: Optional[str] = None):
    """
    Decorator to mark a function as a CrewAI agent skill
    
    Args:
        name: Name of the skill
        inputTypes: List of accepted input types
        outputTypes: List of output types produced by the skill
        description: Description of the skill (defaults to function docstring)
    """
    return skill(name=name, inputTypes=inputTypes, outputTypes=outputTypes)