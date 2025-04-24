from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from .card import AgentCard, AgentCardData, Base
from typing import Optional, List
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///dev.db")
engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)
Base.metadata.create_all(engine)

class AgentCardRepo:
    def __init__(self):
        self.db = SessionLocal()

    def upsert(self, card: AgentCard):
        existing = self.db.get(AgentCard, card.id)
        if existing:
            existing.card = card.card
            existing.version = card.version
            existing.skills_text = card.skills_text
        else:
            self.db.add(card)
        self.db.commit()

    def search(self, *, skill: Optional[str] = None, domain: Optional[str] = None):
        stmt = select(AgentCard)
        if skill:
            stmt = stmt.where(AgentCard.skills_text.ilike(f"%{skill}%"))
        # domain filter could inspect JSON_b but SQLite lacks -> simple string contains
        if domain:
            stmt = stmt.where(AgentCard.card["extra"].as_string().ilike(f"%{domain}%"))
        return [row.to_dict() for row in self.db.execute(stmt).scalars()]
