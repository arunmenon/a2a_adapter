import pytest
from types import SimpleNamespace
from a2a_adapter import skill, register_agent
from a2a_adapter.adapter import Skill, _extract_skills

def test_skill_decorator():
    """Test the skill decorator correctly annotates functions"""
    @skill(name="test", inputTypes=["text"], outputTypes=["json"])
    def test_function(x):
        """Test function"""
        return x
        
    # Verify function has skill attributes
    assert hasattr(test_function, "_a2a_skill")
    assert test_function._a2a_skill == "test"
    assert hasattr(test_function, "_a2a_skills")
    assert len(test_function._a2a_skills) == 1
    
    # Verify skill metadata
    skill_def = test_function._a2a_skills[0]
    assert skill_def.name == "test"
    assert skill_def.description == "Test function"
    assert skill_def.inputTypes == ["text"]
    assert skill_def.outputTypes == ["json"]
    
def test_extract_skills():
    """Test extracting skills from an agent object"""
    @skill(name="skill1", inputTypes=["text"], outputTypes=["json"])
    def function1(x):
        return x
        
    @skill(name="skill2", inputTypes=["json"], outputTypes=["text"])
    def function2(x):
        return x
        
    # Create a simple agent with two skills
    agent = SimpleNamespace(name="Test Agent", tasks=[function1, function2])
    
    # Extract skills
    skills = _extract_skills(agent)
    
    # Verify skills
    assert len(skills) == 2
    skill_names = [s.name for s in skills]
    assert "skill1" in skill_names
    assert "skill2" in skill_names
    
def test_register_agent_starts():
    """Test that register_agent creates a valid FastAPI app"""
    # Create a simple agent with a skill
    @skill(name="echo", inputTypes=["text"], outputTypes=["text"])
    def echo(x):
        return x
        
    agent = SimpleNamespace(name="Echo", description="Echo agent", tasks=[echo])
    
    # Register agent in dry_run mode
    app = register_agent(agent, host="0.0.0.0", port=0, dry_run=True)
    
    # Verify app was created
    assert app.title == "Echo"
    assert app.description == "Echo agent"
    
    # Verify endpoints
    routes = {route.path: route for route in app.routes}
    assert "/agentCard" in routes
    assert "/tasks/send" in routes
    assert "/tasks/{task_id}/events" in routes
    assert "/search" in routes