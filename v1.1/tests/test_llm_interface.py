# tests/test_llm_interface.py

import pytest
import os
from unittest.mock import patch, MagicMock

# Assume LLMInterface is importable
from llm_interface import LLMInterface

# --- Fixtures ---

@pytest.fixture
def openai_config():
    return {
        'llm': {
            'provider': 'openai',
            'default_model': 'gpt-test-dummy',
            'openai_models': {'default': 'gpt-test-dummy'}
        }
    }

@pytest.fixture
def anthropic_config():
     return {
        'llm': {
            'provider': 'anthropic',
            'default_model': 'claude-test-dummy',
            'anthropic_models': {'default': 'claude-test-dummy'}
        }
    }

# Set dummy API keys for testing initialization
@pytest.fixture(autouse=True)
def set_dummy_env_vars(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-openai-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy-anthropic-key")

# --- Mocks --- 

# Mock the OpenAI client
@pytest.fixture
def mock_openai_client():
    with patch('llm_interface.OpenAI') as mock_openai:
        mock_instance = MagicMock()
        mock_completion = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_usage = MagicMock()

        mock_message.content = " Mocked OpenAI Response "
        mock_choice.message = mock_message
        mock_completion.choices = [mock_choice]
        mock_usage.total_tokens = 42
        mock_completion.usage = mock_usage
        
        mock_instance.chat.completions.create.return_value = mock_completion
        mock_openai.return_value = mock_instance
        yield mock_openai # Yield the mock class itself

# Mock the Anthropic client
@pytest.fixture
def mock_anthropic_client():
     # Requires Anthropic library installed, even for mocking the import
     try:
          with patch('llm_interface.Anthropic') as mock_anthropic:
              mock_instance = MagicMock()
              mock_message_response = MagicMock()
              mock_content = MagicMock()

              mock_content.text = " Mocked Anthropic Response "
              mock_message_response.content = [mock_content]
              # Mock usage if needed
              # mock_usage = MagicMock()
              # mock_usage.input_tokens = 10
              # mock_usage.output_tokens = 30
              # mock_message_response.usage = mock_usage

              mock_instance.messages.create.return_value = mock_message_response
              mock_anthropic.return_value = mock_instance
              yield mock_anthropic
     except ImportError:
          pytest.skip("Anthropic library not installed, skipping Anthropic client mock setup")
     except AttributeError:
          # If patch target doesn't exist (e.g., library not installed and ANTHROPIC_AVAILABLE=False)
          pytest.skip("Anthropic library likely not installed, cannot patch client") 

# --- Tests ---

def test_llm_openai_init(openai_config, mock_openai_client):
    "Tests successful OpenAI initialization." 
    interface = LLMInterface(openai_config)
    assert interface.provider == 'openai'
    assert interface.client is not None
    mock_openai_client.assert_called_once()

def test_llm_anthropic_init(anthropic_config, mock_anthropic_client):
     "Tests successful Anthropic initialization." 
     # This test will be skipped if anthropic isn't installed
     interface = LLMInterface(anthropic_config)
     assert interface.provider == 'anthropic'
     assert interface.client is not None
     mock_anthropic_client.assert_called_once()

def test_llm_openai_generate(openai_config, mock_openai_client):
    "Tests OpenAI generation call uses the mock." 
    interface = LLMInterface(openai_config)
    prompt = "Test prompt"
    response = interface.generate(prompt)
    
    assert interface.client.chat.completions.create.call_count == 1
    # Check some args passed to the mocked method
    call_args = interface.client.chat.completions.create.call_args
    assert call_args.kwargs['model'] == 'gpt-test-dummy'
    assert call_args.kwargs['messages'][1]['content'] == prompt
    
    assert response == "Mocked OpenAI Response"

def test_llm_anthropic_generate(anthropic_config, mock_anthropic_client):
     "Tests Anthropic generation call uses the mock." 
     interface = LLMInterface(anthropic_config)
     prompt = "Test prompt for Claude"
     response = interface.generate(prompt)
     
     assert interface.client.messages.create.call_count == 1
     call_args = interface.client.messages.create.call_args
     assert call_args.kwargs['model'] == 'claude-test-dummy'
     assert call_args.kwargs['messages'][0]['content'] == prompt
     
     assert response == "Mocked Anthropic Response"

def test_llm_no_client_generate(openai_config):
     "Tests error handling when client isn't initialized." 
     # Simulate failed init by removing API key *after* fixture setup
     with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
          interface = LLMInterface(openai_config)
          assert interface.client is None
          response = interface.generate("prompt")
          assert "Error: LLM client not ready" in response 