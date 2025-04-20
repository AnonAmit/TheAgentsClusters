# tests/test_agent_template.py

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock # Use AsyncMock for async methods

# Assume Agent is importable
from agent_template import Agent

# --- Fixtures ---

@pytest.fixture
def mock_master_controller():
    mock = MagicMock()
    mock.receive_agent_update = AsyncMock() # Mock the async method
    return mock

@pytest.fixture
def mock_llm_interface():
    mock = MagicMock()
    mock.client = True # Simulate initialized client
    mock.generate = MagicMock(return_value="Mock LLM Plan") # Mock sync generate used via to_thread
    # If generate were async: mock.generate = AsyncMock(return_value="Mock LLM Plan")
    return mock

@pytest.fixture
def mock_memory_system():
    mock = MagicMock()
    mock.store = MagicMock()
    mock.retrieve = MagicMock(return_value=None) # Default retrieve returns None
    return mock

@pytest.fixture
def agent_config():
     # Basic config for the agent
     return {'agents': {'allow_dynamic_sub_agents': False}}

@pytest.fixture
def test_agent(mock_master_controller, mock_llm_interface, mock_memory_system, agent_config):
    "Creates a test Agent instance with mocked dependencies." 
    return Agent(
        agent_id="test-agent-001", 
        master_controller=mock_master_controller, 
        llm_interface=mock_llm_interface, 
        memory_system=mock_memory_system,
        config=agent_config
    )

# --- Tests --- 

@pytest.mark.asyncio # Mark test as async
async def test_agent_initialization(test_agent):
    assert test_agent.agent_id == "test-agent-001"
    assert test_agent.state == "idle"
    assert test_agent.llm is not None
    assert test_agent.memory is not None

@pytest.mark.asyncio
async def test_agent_receive_task_success(test_agent, mock_master_controller, mock_llm_interface, mock_memory_system):
    task_details = {'description': 'Do something important'}
    
    # Mock process_task to avoid its internal logic for this test
    test_agent.process_task = AsyncMock(return_value="Successful Result")
    
    await test_agent.receive_task(task_details)
    
    assert test_agent.state == "finished"
    assert test_agent.current_task is None
    test_agent.process_task.assert_awaited_once_with(task_details)
    # Check if report_back called store (indirectly testing report_back)
    mock_memory_system.store.assert_called_with("test-agent-001_last_result", "Successful Result", is_short_term=False)
    # Check if master was notified (commented out in agent, so shouldn't be called)
    # mock_master_controller.receive_agent_update.assert_awaited_once()
    mock_master_controller.receive_agent_update.assert_not_awaited()

@pytest.mark.asyncio
async def test_agent_receive_task_error(test_agent, mock_master_controller, mock_memory_system):
    task_details = {'description': 'Task that will fail'}
    error_message = "Something went wrong"
    
    # Mock process_task to raise an exception
    test_agent.process_task = AsyncMock(side_effect=Exception(error_message))
    
    await test_agent.receive_task(task_details)
    
    assert test_agent.state == "error"
    assert test_agent.current_task is None
    test_agent.process_task.assert_awaited_once_with(task_details)
    # Check if report_back called store with the error message
    mock_memory_system.store.assert_called_with("test-agent-001_last_result", error_message, is_short_term=False)
    # Check master notified (commented out in agent) 
    # mock_master_controller.receive_agent_update.assert_awaited_once_with(test_agent.agent_id, "error", error_message)
    mock_master_controller.receive_agent_update.assert_not_awaited()

@pytest.mark.asyncio
async def test_agent_process_task_uses_llm_and_memory(test_agent, mock_llm_interface, mock_memory_system):
     task_details = {'description': 'Plan and execute'}
     # Call the actual process_task
     await test_agent.process_task(task_details)

     # Check if LLM generate was called (indirectly via asyncio.to_thread)
     # We can't directly assert_awaited_once_with on the original generate 
     # because it's wrapped in to_thread. We check if the underlying sync mock was called.
     mock_llm_interface.generate.assert_called_once()
     # Check if the result was stored
     mock_memory_system.store.assert_called_with("test-agent-001_plan", "Mock LLM Plan", is_short_term=True)

@pytest.mark.asyncio
async def test_agent_process_task_retrieves_dependency(test_agent, mock_memory_system):
     dependency_key = "previous_result"
     dependency_value = {"data": "needed data"}
     task_details = {'description': 'Process dependency', 'depends_on_key': dependency_key}

     # Configure the mock memory to return the dependency
     mock_memory_system.retrieve.return_value = dependency_value

     await test_agent.process_task(task_details)

     # Check if memory retrieve was called correctly
     mock_memory_system.retrieve.assert_called_once_with(dependency_key, check_long_term_if_missing=True) 