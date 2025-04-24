# A2A Adapter

A lightweight library to expose Python-based agents via Google's Agent-to-Agent (A2A) protocol. This adapter makes it easy to expose existing agent implementations through a standard A2A-compatible API.

## Features

- **A2A Protocol Compatibility**: Fully implements the A2A protocol specification with JSON-RPC request/response format
- **Agent Registration**: Simple decorator-based approach to register agent skills
- **Streaming Responses**: Server-Sent Events (SSE) for streaming task results
- **Framework Integrations**: Built-in support for CrewAI, LangGraph, and Symphony
- **Agent Discovery**: Search-based discovery of agent capabilities

## Quick Start

```python
from a2a_adapter import skill, register_agent

@skill(name="mySkill", inputTypes=["text"], outputTypes=["json"])
def my_function(input_text):
    """Perform some operation on the input"""
    # Your implementation here
    return {"result": input_text}

# Register the agent (can be any Python object with tasks)
register_agent(my_agent, host="0.0.0.0", port=8080)
```

## A2A Protocol Support

This library implements the following A2A protocol components:

- `/tasks/send` endpoint with JSON-RPC 2.0 format
- `/tasks/{taskId}/events` endpoint for streaming task events
- Agent Card specification with capabilities, authentication, and I/O types
- Agent discovery via `/search` endpoint
- Proper event sequence: `accepted` → `running` → `completed`/`failed`

## Example

See `examples/crewai_catalog.py` for a simple example of exposing a mock catalog search agent.

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

## Installation

```bash
pip install a2a-adapter
```

## License

MIT License