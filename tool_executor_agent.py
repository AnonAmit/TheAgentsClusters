# tool_executor_agent.py

import asyncio
import sys
import tempfile
import os
import subprocess
from agent_template import Agent
from llm_interface import LLMInterface
from memory import MemorySystem

class ToolExecutorAgent(Agent):
    """An agent designed to execute Python code provided as a string or memory key."""
    def __init__(self, agent_id: str, master_controller, llm_interface: LLMInterface, memory_system: MemorySystem, config: dict):
        super().__init__(agent_id, master_controller, llm_interface, memory_system, config)
        print(f"ToolExecutorAgent {self.agent_id} initialized.")
        self.execution_timeout = config.get('tool_executor', {}).get('timeout', 30) # Default 30s timeout

    async def process_task(self, task_details):
        """Overrides the base Agent method to handle code execution tasks."""
        print(f"ToolExecutorAgent {self.agent_id} received task: {task_details}")
        code_to_execute = task_details.get('code')
        code_key = task_details.get('code_key')

        if not code_to_execute and code_key:
            print(f"Agent {self.agent_id}: Retrieving code from memory key '{code_key}'")
            code_to_execute = self.memory.retrieve(code_key, check_long_term_if_missing=True)

        if not code_to_execute:
            return "Error: No code provided or found in memory for ToolExecutorAgent task."
        
        if not isinstance(code_to_execute, str):
             return f"Error: Code to execute must be a string, but got type {type(code_to_execute)}."

        print(f"Agent {self.agent_id}: Preparing to execute code snippet (first 100 chars): {code_to_execute[:100]}...")

        # Execute the code in a separate process for safety
        return await self.execute_code_safely(code_to_execute)

    async def execute_code_safely(self, code_str: str) -> str:
        """Executes the provided Python code string in a separate process.

        Args:
            code_str: The Python code to execute.

        Returns:
            A string containing the stdout and stderr of the execution, or an error message.
        """
        # Create a temporary file to store the code
        # Suffix is important for windows, delete=False needed to run it before closing
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as tmp_file:
                tmp_file_path = tmp_file.name
                tmp_file.write(code_str)
            print(f"Agent {self.agent_id}: Code written to temporary file: {tmp_file_path}")
        except Exception as e:
             return f"Error creating temporary file for code execution: {e}"
        
        process = None
        try:
            # Use asyncio's subprocess handling
            print(f"Agent {self.agent_id}: Executing [{sys.executable} {tmp_file_path}] with timeout {self.execution_timeout}s")
            process = await asyncio.create_subprocess_exec(
                sys.executable,  # Path to the current Python interpreter
                tmp_file_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Wait for the process to complete or timeout
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), 
                timeout=self.execution_timeout
            )
            
            return_code = process.returncode
            stdout = stdout_bytes.decode(errors='ignore') if stdout_bytes else ""
            stderr = stderr_bytes.decode(errors='ignore') if stderr_bytes else ""

            print(f"Agent {self.agent_id}: Execution finished. Return code: {return_code}")
            
            result = f"--- Execution Result (Return Code: {return_code}) ---\
"
            if stdout:
                result += f"--- STDOUT ---\n{stdout.strip()}\
"
            if stderr:
                 result += f"--- STDERR ---\n{stderr.strip()}\
"
            if not stdout and not stderr:
                 result += "(No output captured)"

            return result.strip()

        except asyncio.TimeoutError:
            print(f"Agent {self.agent_id}: Code execution timed out after {self.execution_timeout} seconds.")
            if process:
                process.kill() # Terminate the process if it timed out
                await process.wait() # Wait for kill to complete
            return f"Error: Code execution timed out after {self.execution_timeout} seconds."
        except FileNotFoundError:
            return f"Error: Python interpreter '{sys.executable}' not found."
        except Exception as e:
            print(f"Agent {self.agent_id}: Unexpected error during code execution: {e}")
            if process and process.returncode is None:
                 try: process.kill(); await process.wait() # Ensure process is cleaned up
                 except ProcessLookupError: pass # Process might already be gone
            return f"Error during code execution: {e}"
        finally:
            # Clean up the temporary file
            if os.path.exists(tmp_file_path):
                try:
                    os.remove(tmp_file_path)
                    print(f"Agent {self.agent_id}: Cleaned up temporary file: {tmp_file_path}")
                except Exception as e:
                    print(f"Warning: Failed to delete temporary file {tmp_file_path}: {e}") 