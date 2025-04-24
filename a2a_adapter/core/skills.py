"""
Skills module for A2A Adapter

This module provides the skill decorator and functions to manage
agent skills in a per-agent registry.
"""
from typing import Dict, List, Any, Callable, TypeVar, Optional, cast
from functools import wraps
import inspect
import weakref
from dataclasses import dataclass, field

from ..card import Skill

# Type variable for generic function
F = TypeVar('F', bound=Callable[..., Any])

# Per-agent skill registry using weak references to avoid memory leaks
_skill_registries = weakref.WeakKeyDictionary()

def skill(name: str, inputTypes: List[str], outputTypes: List[str]) -> Callable[[F], F]:
    """
    Decorator to mark a function as an A2A skill
    
    Args:
        name: Name of the skill
        inputTypes: List of accepted input types
        outputTypes: List of output types produced by the skill
    
    Returns:
        Decorated function with skill metadata
    """
    def decorator(fn: F) -> F:
        # Get the module where the function is defined
        # This will be our reference point for associating skills with agents
        module = inspect.getmodule(fn)
        
        skill_def = Skill(
            name=name,
            description=fn.__doc__ or "",
            inputTypes=inputTypes,
            outputTypes=outputTypes
        )
        
        # Store the skill in the function's attributes
        if not hasattr(fn, "_a2a_skills"):
            fn._a2a_skills = []
        fn._a2a_skills.append(skill_def)
        
        # Mark the function with skill name for discovery
        fn._a2a_skill = name
        
        @wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            """Wraps the function to handle both sync and async functions"""
            if inspect.iscoroutinefunction(fn):
                return await fn(*args, **kwargs)
            else:
                return fn(*args, **kwargs)
        
        # Copy skill attributes to wrapper
        wrapper._a2a_skill = name
        wrapper._a2a_skills = fn._a2a_skills
        
        return cast(F, wrapper)
    return decorator

def register_skill_for_agent(agent: Any, skill_fn: Callable) -> None:
    """
    Register a skill function for a specific agent
    
    Args:
        agent: The agent object
        skill_fn: The skill function to register
    """
    if not hasattr(skill_fn, "_a2a_skills"):
        return
        
    # Initialize agent's skill registry if needed
    if agent not in _skill_registries:
        _skill_registries[agent] = []
        
    # Add skills to the agent's registry
    for skill_def in skill_fn._a2a_skills:
        _skill_registries[agent].append(skill_def)

def skills_for_agent(agent: Any) -> List[Skill]:
    """
    Get all skills registered for an agent
    
    Args:
        agent: The agent object
        
    Returns:
        List of Skill objects
    """
    return _skill_registries.get(agent, [])

def extract_skills(agent_obj: Any) -> List[Skill]:
    """
    Extract skills from an agent object
    
    This function first checks if the agent has registered skills.
    If not, it tries to extract skills from the agent's functions
    and registers them automatically.
    
    Args:
        agent_obj: The agent object
        
    Returns:
        List of Skill objects
    """
    # First check the registry
    skills = skills_for_agent(agent_obj)
    if skills:
        return skills
        
    # If no skills are registered, try to extract them from functions
    functions = extract_functions(agent_obj)
    
    # Register skills if found
    for fn in functions:
        if hasattr(fn, "_a2a_skills"):
            for skill_def in fn._a2a_skills:
                register_skill_for_agent(agent_obj, fn)
                
    # Return skills from registry after registration
    return skills_for_agent(agent_obj)

def extract_functions(agent_obj: Any) -> List[Callable]:
    """
    Extract functions from an agent object
    
    This function tries to extract functions from common agent frameworks
    
    Args:
        agent_obj: The agent object
        
    Returns:
        List of functions
    """
    funcs = []
    
    # Extract functions from CrewAI agent
    if hasattr(agent_obj, "tasks"):
        for t in agent_obj.tasks:
            fn = getattr(t, "fn", None) or t
            funcs.append(fn)
    
    # Extract functions from LangGraph agent (might have tools attribute)
    elif hasattr(agent_obj, "tools"):
        for t in agent_obj.tools:
            if callable(t):
                funcs.append(t)
            elif hasattr(t, "fn"):
                funcs.append(t.fn)
    
    return funcs