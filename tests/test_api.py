import pytest
from fastapi.testclient import TestClient
import json
from types import SimpleNamespace
from a2a_adapter import skill, register_agent, build_app

# Create a test agent with skills for testing
@skill(name="echo", inputTypes=["text"], outputTypes=["text"])
def echo(input_text):
    """Echo the input text"""
    return input_text

@skill(name="transform", inputTypes=["text"], outputTypes=["json"])
def transform(input_text):
    """Transform text to JSON"""
    return {"result": input_text}

# Create test agent
test_agent = SimpleNamespace(
    name="Test Agent",
    description="Agent for testing A2A API",
    version="0.1.0",
    tasks=[echo, transform]
)

@pytest.fixture
def client():
    """Create a test client"""
    app = build_app(test_agent, host="127.0.0.1", port=8080)
    return TestClient(app)

def test_agent_card_endpoint(client):
    """Test the /agentCard endpoint"""
    response = client.get("/agentCard")
    
    # Check response status
    assert response.status_code == 200
    
    # Check required fields
    data = response.json()
    assert "id" in data
    assert "name" in data
    assert data["name"] == "Test Agent"
    assert "capabilities" in data
    assert data["capabilities"]["streaming"] is True
    assert "authentication" in data
    assert "schemes" in data["authentication"]
    assert "defaultInputModes" in data
    assert "text" in data["defaultInputModes"]
    assert "defaultOutputModes" in data
    assert "text" in data["defaultOutputModes"]
    assert "skills" in data
    assert len(data["skills"]) == 2
    
    # Check skill structure
    skill = next(s for s in data["skills"] if s["name"] == "echo")
    assert "inputTypes" in skill
    assert "outputTypes" in skill
    assert "description" in skill

def test_tasks_send_jsonrpc(client):
    """Test the /tasks/send endpoint with JSON-RPC"""
    # Prepare JSON-RPC request
    request = {
        "jsonrpc": "2.0",
        "id": "test-123",
        "method": "tasks/send",
        "params": {
            "agentSkill": "echo",
            "input": "hello world"
        }
    }
    
    # Send request
    response = client.post("/tasks/send", json=request)
    
    # Check response status (accepted)
    assert response.status_code == 202
    
    # Check JSON-RPC envelope
    data = response.json()
    assert "jsonrpc" in data
    assert data["jsonrpc"] == "2.0"
    assert "id" in data
    assert data["id"] == "test-123"
    assert "result" in data
    assert "taskId" in data["result"]
    assert "status" in data["result"]
    assert data["result"]["status"] == "accepted"

def test_tasks_send_invalid_skill(client):
    """Test the /tasks/send endpoint with invalid skill"""
    # Prepare JSON-RPC request with non-existent skill
    request = {
        "jsonrpc": "2.0",
        "id": "test-error",
        "method": "tasks/send",
        "params": {
            "agentSkill": "nonexistent",
            "input": "hello world"
        }
    }
    
    # Send request
    response = client.post("/tasks/send", json=request)
    
    # Check error response
    data = response.json()
    assert "jsonrpc" in data
    assert data["jsonrpc"] == "2.0"
    assert "id" in data
    assert data["id"] == "test-error"
    assert "error" in data
    assert "code" in data["error"]
    assert "message" in data["error"]

def test_tasks_send_invalid_method(client):
    """Test the /tasks/send endpoint with invalid method"""
    # Prepare JSON-RPC request with wrong method
    request = {
        "jsonrpc": "2.0",
        "id": "test-error",
        "method": "invalid_method",
        "params": {
            "agentSkill": "echo",
            "input": "hello world"
        }
    }
    
    # Send request
    response = client.post("/tasks/send", json=request)
    
    # Check error response
    data = response.json()
    assert "jsonrpc" in data
    assert data["jsonrpc"] == "2.0"
    assert "id" in data
    assert data["id"] == "test-error"
    assert "error" in data
    assert "code" in data["error"]
    assert "message" in data["error"]

def test_search_endpoint(client):
    """Test the /search endpoint"""
    # Prepare JSON-RPC request
    request = {
        "jsonrpc": "2.0",
        "id": "search-1",
        "method": "skills/search",
        "params": {
            "query": "echo"
        }
    }
    
    # Send request
    response = client.post("/search", json=request)
    
    # Check response
    assert response.status_code == 200
    data = response.json()
    assert "jsonrpc" in data
    assert data["jsonrpc"] == "2.0"
    assert "id" in data
    assert data["id"] == "search-1"
    assert "result" in data
    assert "agents" in data["result"]