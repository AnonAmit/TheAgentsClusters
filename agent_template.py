# agent_template.py

import asyncio
import logging # Import logging
from llm_interface import LLMInterface
from memory import MemorySystem

logger = logging.getLogger(__name__) # Module-level logger

class Agent:
    def __init__(self, agent_id: str, master_controller, llm_interface: LLMInterface, memory_system: MemorySystem, config: dict):
        self.agent_id = agent_id
        self.master = master_controller # Reference to the master controller
        self.llm = llm_interface
        self.memory = memory_system
        self.config = config.get('agents', {}) # Agent specific config section
        self.state = "idle" # Example state: idle, running, finished, error
        self.current_task = None
        # Use logger instead of print
        logger.info(f"Agent {self.agent_id} initialized.")

    async def receive_task(self, task_details):
        logger.info(f"Agent {self.agent_id} received task: {str(task_details)[:100]}...")
        self.current_task = task_details
        self.state = "running"
        result = None
        error = None
        try:
            # Process task - potentially asynchronously
            result = await self.process_task(task_details)
            self.state = "finished"
            logger.info(f"Agent {self.agent_id} finished task successfully.")
        except asyncio.CancelledError:
            logger.warning(f"Agent {self.agent_id} task cancelled.")
            self.state = "cancelled"
            # Re-raise the error so the master controller's task wrapper knows
            raise 
        except Exception as e:
            logger.exception(f"Agent {self.agent_id} encountered error processing task: {e}")
            self.state = "error"
            error = str(e)
            # Store the error maybe? self.memory.store(f"{self.agent_id}_error", error)
        finally:
            # Report final state and result/error back to master controller
            await self.report_back(result if self.state == "finished" else error)
            # Ensure master is notified about the final state
            # Let master know the final state (handles retries etc)
            # The master's _run_agent_task wrapper already calls receive_agent_update, 
            # calling it here too might be redundant unless specific intermediate updates needed.
            # Let's comment this out for now to avoid double reporting on final state.
            # await self.master.receive_agent_update(self.agent_id, self.state, result if self.state == "finished" else error)
            self.current_task = None # Clear task after completion/error

    async def process_task(self, task_details):
        """Placeholder for the agent's core logic to process a task."""
        logger.debug(f"Agent {self.agent_id} starting processing task: {task_details}")

        # --- Example Memory Communication --- 
        # Attempt to retrieve data potentially stored by another agent
        # This requires coordination on keys (e.g., based on task ID or dependencies)
        required_input_key = task_details.get('depends_on_key') # Hypothetical dependency
        if required_input_key:
             logger.debug(f"Agent {self.agent_id} attempting to retrieve prerequisite data from key: {required_input_key}")
             prerequisite_data = self.memory.retrieve(required_input_key, check_long_term_if_missing=True)
             if prerequisite_data:
                  logger.debug(f"Agent {self.agent_id} retrieved prerequisite data: {str(prerequisite_data)[:100]}...")
                  # Use the prerequisite_data in the current task processing
             else:
                  logger.warning(f"Agent {self.agent_id} could not find prerequisite data for key: {required_input_key}.")
        # --- End Example --- 

        # Example: Use LLM for planning or execution
        if self.llm and self.llm.client:
            plan_prompt = f"Based on the task '{task_details}', create a simple step-by-step plan."
            plan = await asyncio.to_thread(self.llm.generate, plan_prompt, max_tokens=100)
            logger.debug(f"Agent {self.agent_id} generated plan: {plan}")
            # Store plan in memory
            self.memory.store(f"{self.agent_id}_plan", plan, is_short_term=True)

        # Example: Spawn sub-agents if needed (logic depends on task)
        await self.spawn_sub_agents_if_needed(task_details)

        # Simulate work
        await asyncio.sleep(1)

        result = f"Processed result for task: {str(task_details)[:50]}..."
        logger.debug(f"Agent {self.agent_id} finished processing.")
        return result

    async def spawn_sub_agents_if_needed(self, task_details):
        # Logic to determine if sub-agents are needed and spawn them
        # This might involve calling the master controller or handling directly
        logger.debug(f"Agent {self.agent_id} checking if sub-agents are needed...")
        # Example: If task involves multiple parts, spawn sub-agents
        if self.config.get('allow_dynamic_sub_agents', False):
            # Sub-agent spawning logic goes here
            # For now, just print
            logger.info(f"Agent {self.agent_id}: Sub-agent spawning enabled, but no specific logic implemented yet.")
        pass

    async def report_back(self, result):
        logger.info(f"Agent {self.agent_id} reporting back: {str(result)[:100]}...")
        # Send result to master or store in shared memory
        # Example: Store result in memory
        if result is not None:
             self.memory.store(f"{self.agent_id}_last_result", result, is_short_term=False) # Store in long-term
        # Optionally notify master
        # await self.master.receive_agent_update(self.agent_id, self.state, result)
        pass

    async def run(self):
        # Main execution loop for the agent, if needed for continuous operation
        # For now, agents are task-driven via receive_task
        logger.info(f"Agent {self.agent_id} run loop started (currently idle). State: {self.state}")
        while self.state != "stopped": # Example loop condition
            # Agents might poll for tasks, perform background checks, etc.
            await asyncio.sleep(5) # Prevent busy-waiting
            if self.state == "idle":
                 # Maybe request work from master?
                 logger.debug(f"Agent {self.agent_id} is idle.")
        logger.info(f"Agent {self.agent_id} run loop stopped.")

    def stop(self):
        logger.info(f"Stopping agent {self.agent_id}...")
        self.state = "stopped" 