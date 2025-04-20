# THE AGENTS CLUSTER [TAC]

A fully autonomous, hyper-personalized AI agents framework built with Python and asyncio.

This project implements an agent-based orchestration system capable of autonomously executing tasks using a network of specialized AI agents and dynamically created sub-agents. It features concurrent agent execution, shared memory, LLM integration, dynamic tool creation & execution, and a basic CLI and web dashboard for monitoring.

## Architecture Overview

TAC follows a hierarchical structure:

1.  **Master Controller (`master_controller.py`)**: The central orchestrator. It manages the task queue, assigns tasks to appropriate agents, spins up new agents based on demand (respecting concurrency limits), monitors agent status, and holds references to shared components like the LLM interface and Memory System.
2.  **Agents (`agent_template.py`, `browser_agent.py`, etc.)**: Autonomous units responsible for executing high-level tasks. They inherit from a base `Agent` class, giving them access to shared memory and LLM capabilities. Agents can be specialized (e.g., `BrowserAgent` for web tasks, `ToolCreatorAgent` for generating code). They process tasks asynchronously.
3.  **Sub-Agents (`sub_agent_template.py`)**: Lightweight, typically function-based workers designed for atomic sub-tasks spawned by main Agents (implementation details depend on agent logic).
4.  **LLM Interface (`llm_interface.py`)**: Provides a unified way to interact with different Large Language Models (currently OpenAI and Anthropic Claude). It handles API key management (via environment variables) and generation calls.
5.  **Memory System (`memory.py`)**: Manages shared memory access. Supports short-term (in-memory dictionary) and long-term persistence (Redis, JSON file, ChromaDB - basic key/value via metadata). Agents use this to store results, intermediate data, or communicate.
6.  **Tooling (`tool_creator_agent.py`, `tool_executor_agent.py`)**: Agents specifically designed to create new Python tools (scripts) based on descriptions (using LLMs) and execute provided code safely in a separate process.
7.  **Interfaces (`cli.py`, `dashboard.py`)**: Provide ways to interact with and monitor the system. The CLI allows starting the controller and queuing initial tasks. The Streamlit dashboard reads status information from the Memory System.

## Project Structure

```
/
├── master_controller.py       # Central orchestrator
├── agent_template.py          # Base class for Agents
├── sub_agent_template.py      # Template for sub-agent functions
├── memory.py                # Shared memory system (Redis, JSON, ChromaDB)
├── llm_interface.py           # Interface for LLMs (OpenAI, Anthropic)
├── logging_config.py        # Central logging setup
├── browser_agent.py         # Agent for web browsing/scraping (Playwright)
├── tool_creator_agent.py      # Agent that generates Python tools
├── tool_executor_agent.py     # Agent that executes Python code safely
├── info_hunter_agent.py       # Agent specialized in information gathering
├── cli.py                   # Command-Line Interface to run the controller
├── dashboard.py             # Streamlit dashboard for monitoring
├── config.yaml              # Main configuration file
├── requirements.txt         # Python dependencies
├── README.md                # This file
├── Project-TO-DO-List.txt   # Development task tracking
└── tests/                   # Unit/integration tests
    ├── test_memory.py
    ├── test_llm_interface.py
    └── test_agent_template.py
```

## Setup

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd tac-project # Or your chosen directory name
    ```

2.  **Create and activate a virtual environment (recommended):**
    ```bash
    python -m venv venv
    # On Linux/macOS
    source venv/bin/activate 
    # On Windows (Command Prompt)
    # venv\Scripts\activate.bat
    # On Windows (PowerShell)
    # .\venv\Scripts\Activate.ps1 
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Install Playwright browsers (if using `BrowserAgent`):**
    ```bash
    playwright install
    # You might only need one browser, e.g.: playwright install chromium
    ```

5.  **Configure API Keys:**
    TAC requires API keys for the configured LLM provider(s) to be set as environment variables.
    -   **OpenAI:** Set `OPENAI_API_KEY`
    -   **Anthropic:** Set `ANTHROPIC_API_KEY`
    
    *Example (Linux/macOS):*
    ```bash
    export OPENAI_API_KEY='your_openai_key'
    export ANTHROPIC_API_KEY='your_anthropic_key'
    ```
    *Example (Windows PowerShell):*
    ```powershell
    $env:OPENAI_API_KEY='your_openai_key'
    $env:ANTHROPIC_API_KEY='your_anthropic_key'
    ```

6.  **Configure `config.yaml`:**
    Review and adjust settings in `config.yaml`: 
    -   `master_controller`: `max_concurrent_agents`, `max_task_retries`.
    -   `llm`: Select `provider` (openai, anthropic), set default models.
    -   `memory`: Choose `backend` (redis, json_file, vector_db), configure backend specifics (host/port for Redis, path/collection for ChromaDB).
    -   `browser`: Configure `provider` (playwright), `headless` mode, `browser_type`.
    -   `logging`: Set `level`, `format`, `log_file`.

7.  **Setup External Services (if applicable):**
    -   **Redis:** If using the Redis memory backend, ensure a Redis server is running and accessible at the host/port specified in `config.yaml`.
    -   **ChromaDB:** If using ChromaDB with a persistent path, ensure the directory exists or is writable.

## Running

### Running the Master Controller (via CLI)

The primary way to run the system is using `cli.py`.

```bash
# Start the controller (will run indefinitely until Ctrl+C)
python cli.py

# Start and assign a simple initial task by description
python cli.py --task "Summarize the main points from https://example.com"

# Start and assign a complex task using JSON details
python cli.py --details '{"description": "Scrape headlines from news site", "url": "https://news.google.com", "action": "scrape_text", "selector": "h3", "agent_type": "browser"}'

# Use a different config file
python cli.py --config my_config.yaml --task "Generate a tool to calculate Fibonacci numbers"
```

### Running the Dashboard

While the Master Controller is running (using `cli.py` in a separate terminal), you can launch the Streamlit dashboard:

```bash
streamlit run dashboard.py
```

This will open a web page in your browser showing the current status read from the memory system (task queue, active agents, history).

### Running Tests

Make sure you have installed the test dependencies (`pytest`, `pytest-asyncio`).

```bash
# Run all tests from the root directory
pytest

# Run tests in a specific file
pytest tests/test_memory.py

# Run with verbose output
pytest -v
```

## Extending TAC

-   **Adding New Agents:** Create a new Python file (e.g., `my_special_agent.py`), define a class inheriting from `Agent`, implement the `process_task` method with the agent's specific logic, and update the agent routing logic in `MasterController._create_agent` to recognize and instantiate your new agent based on `agent_type` hints or task details.
-   **Adding LLM Providers:** Modify `llm_interface.py` to add a new client initialization block and generation logic for the desired provider. Add necessary configuration to `config.yaml` and update `requirements.txt`.
-   **Adding Memory Backends:** Modify `memory.py` to handle a new backend type, implementing initialization, store, retrieve, and delete methods. Add necessary configuration to `config.yaml` and update `requirements.txt`.

## Contributing

(Contribution guidelines can be added here - e.g., code style, pull request process.) 