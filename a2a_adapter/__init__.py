"""
A2A Adapter - Python library for exposing agents via Google's A2A protocol
"""

# Core imports
from .core.skills import skill
from .server import register_agent, build_app
from .card import AgentCardData, Skill
from .db.registry import AgentCardRepo

__version__ = "0.1.0"