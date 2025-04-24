from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Callable
from .registry import AgentCardRepo
repo = AgentCardRepo()
router = APIRouter()

@router.get("/search")
async def search(skill:str|None=None, domain:str|None=None):
    return repo.search(skill=skill, domain=domain)
