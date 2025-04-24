from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, declarative_base
import json
from datetime import datetime

Base = declarative_base()

@dataclass
class Skill:
    name: str
    inputs: List[str]
    outputs: List[str]
    description: str = ""

@dataclass
class AgentCardData:
    id: str
    name: str
    version: str
    description: str
    skills: List[Skill]
    endpoints: dict
    auth: dict = field(default_factory=lambda: {"type": "none"})
    extra: dict = field(default_factory=dict)

class AgentCard(Base):
    __tablename__ = "agent_cards"
    id: Mapped[str] = mapped_column(sa.String, primary_key=True)
    version: Mapped[str] = mapped_column(sa.String)
    card: Mapped[str] = mapped_column(sa.JSON)
    skills_text: Mapped[str] = mapped_column(sa.String)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime, default=datetime.utcnow)

    @classmethod
    def from_data(cls, data: AgentCardData):
        return cls(
            id=data.id,
            version=data.version,
            card=asdict(data),
            skills_text=" ".join([s.name for s in data.skills]),
        )

    def to_dict(self) -> dict:
        return self.card
