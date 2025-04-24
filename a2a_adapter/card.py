from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Union, Literal
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

# JSON-RPC Pydantic models with proper schema constraints
class TaskInput(BaseModel):
    """Task input with flexible type support"""
    type: str = "text"
    content: Any

class JSONRPCParams(BaseModel):
    """Parameters for tasks/send method"""
    agentSkill: str
    input: Union[str, Dict[str, Any], TaskInput]

class JSONRPCRequest(BaseModel):
    """JSON-RPC 2.0 Request envelope"""
    jsonrpc: Literal["2.0"] = "2.0"
    id: Union[str, int]
    method: str
    params: JSONRPCParams

class JSONRPCErrorData(BaseModel):
    """Additional error information"""
    error: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

class JSONRPCError(BaseModel):
    """JSON-RPC 2.0 Error object"""
    code: int
    message: str
    data: Optional[JSONRPCErrorData] = None

class TaskResponseData(BaseModel):
    """Task response data with status"""
    status: str
    data: Optional[Any] = None

class JSONRPCResponse(BaseModel):
    """JSON-RPC 2.0 Response envelope"""
    jsonrpc: Literal["2.0"] = "2.0"
    id: Union[str, int]
    result: Optional[Union[Dict[str, Any], TaskResponseData]] = None
    error: Optional[JSONRPCError] = None

class TaskResponse(BaseModel):
    """Response from tasks/send endpoint"""
    jsonrpc: Literal["2.0"] = "2.0"
    id: Union[str, int]
    result: Dict[str, Any] = Field(default_factory=lambda: {"taskId": "", "status": "accepted"})

class SearchParams(BaseModel):
    """Parameters for skills/search method"""
    query: Optional[str] = None
    domain: Optional[str] = None
    limit: Optional[int] = None
    offset: Optional[int] = None

class SearchRequest(BaseModel):
    """JSON-RPC request for skills/search"""
    jsonrpc: Literal["2.0"] = "2.0"
    id: Union[str, int]
    method: Literal["skills/search"] = "skills/search"
    params: SearchParams