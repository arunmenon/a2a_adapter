# A2A Adapter

A lightweight library to expose Python-based agents via Google's Agent-to-Agent (A2A) protocol. This adapter makes it easy to expose existing agent implementations through a standard A2A-compatible API.

## Features

- **Full A2A Protocol Compatibility**: Implements the complete A2A protocol specification with JSON-RPC request/response format
- **Per-agent Skill Registry**: Each agent has its own set of skills to avoid conflicts
- **Streaming Responses**: Server-Sent Events (SSE) with proper event sequence (accepted → running → completed/failed)
- **Framework Integrations**: Support for CrewAI, LangGraph, and Symphony
- **Agent Discovery**: JSON-RPC compliant search endpoint
- **Type Safety**: Pydantic models for request/response validation
- **CLI Tool**: Command-line interface for running the adapter
- **Modular Design**: Clean separation of concerns for better maintainability

## Quick Start

```python
from types import SimpleNamespace
from a2a_adapter import skill, register_agent

@skill(name="mySkill", inputTypes=["text"], outputTypes=["json"])
def my_function(input_text):
    """Perform some operation on the input"""
    # Your implementation here
    return {"result": input_text}

# Create an agent object (can be any object with tasks)
agent = SimpleNamespace(
    name="My Agent",
    description="Agent that does things",
    tasks=[my_function]
)

# Register and start the server
register_agent(agent, host="0.0.0.0", port=8080)
```

## CLI Usage

You can also use the CLI to run an agent:

```bash
# Run from your code
python -m a2a_adapter.cli serve examples/crewai_catalog.py --host 0.0.0.0 --port 8080

# Enable auto-reload for development
python -m a2a_adapter.cli serve examples/crewai_catalog.py --reload

# Check version
python -m a2a_adapter.cli version
```

## A2A Protocol Support

This adapter implements the following A2A protocol components:

- **JSON-RPC 2.0 Envelope**: All requests and responses follow the JSON-RPC 2.0 specification
- **Task Lifecycle**: `/tasks/send` returns a task ID, client connects to `/tasks/{taskId}/events` for updates
- **Event Sequence**: Proper event sequence with `accepted` → `running` → `completed`/`failed` events
- **Agent Card**: Complete agent card with all required fields including capabilities and I/O types
- **Authentication**: Supports the authentication schemes field as required by the spec
- **Error Handling**: Standard JSON-RPC error codes and error object structure

## JSON-RPC Request Format

A2A-compatible requests should follow this format:

```json
{
  "jsonrpc": "2.0",
  "id": "request-123",
  "method": "tasks/send",
  "params": {
    "agentSkill": "skillName",
    "input": "your input data here"
  }
}
```

## Response Format

Responses follow the JSON-RPC 2.0 specification:

```json
{
  "jsonrpc": "2.0",
  "id": "request-123",
  "result": {
    "taskId": "task-456",
    "status": "accepted"
  }
}
```

## Event Stream Format

Events are streamed using Server-Sent Events (SSE) format:

```
event: accepted
data: {"jsonrpc":"2.0","id":"request-123","result":{"status":"accepted"}}

event: running
data: {"jsonrpc":"2.0","id":"request-123","result":{"status":"running"}}

event: completed
data: {"jsonrpc":"2.0","id":"request-123","result":{"status":"completed","data":{"result":"output data"}}}
```

## Architecture

The adapter is built with a clean, modular architecture:

> **Note**: The current implementation uses an in-memory task store which does not persist across restarts. For production use, consider implementing persistence with Redis or a database in a future version.

```
a2a_adapter/
├─ core/             # Core functionality 
│   ├─ skills.py     # Skill decorator and per-agent registry
│   ├─ rpc.py        # JSON-RPC utilities and envelope handling
│   └─ lifecycle.py  # Thread-safe task execution and event streaming
├─ api/              # API endpoints
│   ├─ card_routes.py # Agent card and search routes
│   └─ task_routes.py # JSON-RPC task execution endpoints
├─ db/               # Data storage
│   └─ registry.py   # Agent card repository with SQLAlchemy
├─ integrations/     # Framework integrations
│   ├─ crewai.py     # CrewAI integration
│   ├─ langgraph.py  # LangGraph integration
│   └─ symphony.py   # Symphony integration
├─ cli.py           # Command-line interface with Typer
└─ server.py        # FastAPI app builder (non-blocking)
```

### Component Interaction

```
┌──────────────┐         ┌───────────────┐
│ Agent Object │◄────────┤ @skill        │ Decorator attaches
└──────┬───────┘         └───────────────┘ metadata to functions
       │
       ▼
┌──────────────┐         ┌───────────────┐
│ register_    │◄────────┤ CLI           │ Client interfaces
│ agent()      │         │ /examples     │
└──────┬───────┘         └───────────────┘
       │
       ▼
┌──────────────┐
│ build_app()  │ Creates FastAPI app with routes
└──────┬───────┘
       │
       ▼
┌──────────────┐         ┌───────────────┐
│ API Endpoints│◄────────┤ JSON-RPC      │ Spec-compliant 
└──────┬───────┘         │ Request/      │ transport format
       │                 │ Response      │
       ▼                 └───────────────┘
┌──────────────┐
│ Task         │ Thread-safe execution
│ Lifecycle    │ with proper event sequence
└──────────────┘
```

## Examples

See the `examples` directory for complete examples:

- `crewai_catalog.py`: Simple catalog search agent
- `client_example.py`: Client that connects to an A2A agent
- `test_compliance.py`: Test script to verify A2A compliance

## Installation

```bash
pip install a2a-adapter
```

## Development

```bash
# Clone the repository
git clone https://github.com/arunmenon/a2a_adapter.git
cd a2a_adapter

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest
```

## License

MIT License