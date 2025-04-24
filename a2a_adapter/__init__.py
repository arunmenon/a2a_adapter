"""
A2A Adapter - Python library for exposing agents via Google's A2A protocol
"""

from .adapter import skill, register_agent, build_app
from .card import AgentCardData, Skill
from .registry import AgentCardRepo

__version__ = "0.1.0"