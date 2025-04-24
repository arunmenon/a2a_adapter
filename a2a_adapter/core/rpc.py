"""
JSON-RPC module for A2A Adapter

This module provides JSON-RPC 2.0 utilities and models for handling
requests and responses according to the A2A protocol specification.
"""
from typing import Dict, List, Any, Optional, Union, Literal
from pydantic import BaseModel, Field
from fastapi.responses import JSONResponse
import json

# Re-export models from card.py for backward compatibility
# Eventually, these should be moved here completely
from ..card import (
    JSONRPCRequest, JSONRPCResponse, JSONRPCError, 
    JSONRPCErrorData, TaskResponse, SearchParams
)

# JSON-RPC Error codes
class ErrorCodes:
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    SERVER_ERROR_START = -32000
    SERVER_ERROR_END = -32099
    TASK_NOT_FOUND = -32001
    SKILL_NOT_FOUND = -32002

class JSONRPCException(Exception):
    """Base exception for JSON-RPC errors with proper error handling"""
    def __init__(self, code: int, message: str, data: Optional[Dict[str, Any]] = None):
        self.code = code
        self.message = message
        self.data = JSONRPCErrorData(error=message, details=data)
        super().__init__(message)
    
    def to_response(self, request_id: Union[str, int]) -> JSONResponse:
        """Convert exception to proper JSON-RPC response"""
        error = JSONRPCError(code=self.code, message=self.message, data=self.data)
        response = JSONRPCResponse(jsonrpc="2.0", id=request_id, error=error)
        return JSONResponse(content=response.dict(exclude_none=True))

class JSONRPCInvalidRequest(JSONRPCException):
    """Exception for invalid JSON-RPC requests"""
    def __init__(self, message: str = "Invalid Request"):
        super().__init__(code=ErrorCodes.INVALID_REQUEST, message=message)

class JSONRPCMethodNotFound(JSONRPCException):
    """Exception for method not found in JSON-RPC requests"""
    def __init__(self, message: str = "Method not found"):
        super().__init__(code=ErrorCodes.METHOD_NOT_FOUND, message=message)

class JSONRPCSkillNotFound(JSONRPCException):
    """Exception for skill not found in A2A requests"""
    def __init__(self, skill_name: str):
        super().__init__(
            code=ErrorCodes.SKILL_NOT_FOUND, 
            message=f"Skill '{skill_name}' not found"
        )

class JSONRPCTaskNotFound(JSONRPCException):
    """Exception for task not found in A2A requests"""
    def __init__(self, task_id: str):
        super().__init__(
            code=ErrorCodes.TASK_NOT_FOUND,
            message=f"Task '{task_id}' not found"
        )

def create_success_response(request_id: Union[str, int], result: Any) -> JSONResponse:
    """
    Create a JSON-RPC 2.0 success response
    
    Args:
        request_id: The ID from the request
        result: The result data
        
    Returns:
        FastAPI JSONResponse
    """
    response = JSONRPCResponse(jsonrpc="2.0", id=request_id, result=result)
    return JSONResponse(content=response.dict(exclude_none=True))

def create_error_response(request_id: Union[str, int], code: int, message: str, data: Optional[Any] = None) -> JSONResponse:
    """
    Create a JSON-RPC 2.0 error response
    
    Args:
        request_id: The ID from the request
        code: The error code
        message: The error message
        data: Additional error data
        
    Returns:
        FastAPI JSONResponse
    """
    error_data = JSONRPCErrorData(error=message, details=data) if data else None
    error = JSONRPCError(code=code, message=message, data=error_data)
    response = JSONRPCResponse(jsonrpc="2.0", id=request_id, error=error)
    return JSONResponse(content=response.dict(exclude_none=True))

def create_task_accepted_response(request_id: Union[str, int], task_id: str) -> JSONResponse:
    """
    Create a task accepted response for A2A
    
    Args:
        request_id: The ID from the request
        task_id: The generated task ID
        
    Returns:
        FastAPI JSONResponse with 202 Accepted status
    """
    response = TaskResponse(
        jsonrpc="2.0",
        id=request_id,
        result={"taskId": task_id, "status": "accepted"}
    )
    return JSONResponse(
        content=response.dict(exclude_none=True),
        status_code=202
    )

def format_sse_event(event_type: str, request_id: Union[str, int], data: Any) -> Dict[str, str]:
    """
    Format a server-sent event with JSON-RPC envelope
    
    Args:
        event_type: Type of event (accepted, running, completed, failed)
        request_id: Original request ID
        data: Event data
        
    Returns:
        Dict formatted for SSE
    """
    if event_type == "failed":
        error_data = JSONRPCErrorData(error=data.get("error", "Unknown error"))
        json_data = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": ErrorCodes.SERVER_ERROR_START,
                "message": "Task execution failed",
                "data": error_data.dict(exclude_none=True)
            }
        }
    else:
        result = {"status": event_type}
        if event_type == "completed" and data:
            result["data"] = data
        json_data = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result
        }
    
    return {
        "event": event_type,
        "data": json.dumps(json_data)
    }