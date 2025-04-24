from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, declarative_base
from pydantic import BaseModel, Field
import json
from datetime import datetime

Base = declarative_base()

@dataclass
class Skill:
    name: str
    description: str = ""
    inputTypes: List[str] = field(default_factory=list)
    outputTypes: List[str] = field(default_factory=list)

@dataclass
class AgentCardData:
    id: str
    name: str
    version: str
    description: str
    skills: List[Skill]
    url: str
    endpoints: dict
    capabilities: dict = field(default_factory=lambda: {"streaming": True})
    authentication: dict = field(default_factory=lambda: {"schemes": ["none"]})
    defaultInputModes: List[str] = field(default_factory=lambda: ["text"])
    defaultOutputModes: List[str] = field(default_factory=lambda: ["text"])
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

# JSON-RPC Pydantic models
class JSONRPCParams(BaseModel):
    agentSkill: str
    input: Any

class JSONRPCRequest(BaseModel):
    jsonrpc: str = Field("2.0", const=True)
    id: str
    method: str
    params: JSONRPCParams

class JSONRPCError(BaseModel):
    code: int
    message: str
    data: Optional[Dict[str, Any]] = None

class JSONRPCResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: str
    result: Optional[Any] = None
    error: Optional[JSONRPCError] = None

class TaskResponse(BaseModel):
    taskId: str
    status: str = "accepted"