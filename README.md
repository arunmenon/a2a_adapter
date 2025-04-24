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

## Quick Start

```python
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
python -m a2a_adapter.cli serve examples/crewai_catalog.py --host 0.0.0.0 --port 8080
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

## Examples

See the `examples` directory for complete examples:

- `crewai_catalog.py`: Simple catalog search agent
- `client_example.py`: Client that connects to an A2A agent
- `test_compliance.py`: Test script to verify A2A compliance

## Installation

```bash
pip install a2a-adapter
```

## License

MIT License