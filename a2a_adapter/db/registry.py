"""
Agent card repository
"""
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from ..card import AgentCard, AgentCardData, Base
from typing import Optional, List, Dict, Any
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///dev.db")
engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)
Base.metadata.create_all(engine)

class AgentCardRepo:
    """Repository for agent cards"""
    
    def __init__(self):
        self.db = SessionLocal()

    def upsert(self, card: AgentCard) -> None:
        """
        Insert or update an agent card
        
        Args:
            card: The agent card to insert or update
        """
        existing = self.db.get(AgentCard, card.id)
        if existing:
            existing.card = card.card
            existing.version = card.version
            existing.skills_text = card.skills_text
        else:
            self.db.add(card)
        self.db.commit()

    def search(self, *, 
               skill: Optional[str] = None, 
               domain: Optional[str] = None,
               limit: Optional[int] = None,
               offset: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Search for agent cards by skill or domain with pagination
        
        Args:
            skill: Optional skill name to search for
            domain: Optional domain to search for
            limit: Maximum number of results to return (pagination)
            offset: Number of results to skip (pagination)
            
        Returns:
            List of matching agent cards
        """
        stmt = select(AgentCard)
        
        # Apply filters
        if skill:
            stmt = stmt.where(AgentCard.skills_text.ilike(f"%{skill}%"))
        # domain filter could inspect JSON_b but SQLite lacks -> simple string contains
        if domain:
            stmt = stmt.where(AgentCard.card["extra"].as_string().ilike(f"%{domain}%"))
            
        # Order by most recent updates
        stmt = stmt.order_by(AgentCard.updated_at.desc())
        
        # Apply pagination
        if offset is not None:
            stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)
            
        return [row.to_dict() for row in self.db.execute(stmt).scalars()]