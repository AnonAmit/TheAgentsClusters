# master_controller.py

import asyncio
import yaml
import uuid
from collections import deque
import json
import time
import logging # Import logging

from llm_interface import LLMInterface
from memory import MemorySystem
from agent_template import Agent
# Import specific agent types as they are developed
from browser_agent import BrowserAgent
from tool_creator_agent import ToolCreatorAgent
from tool_executor_agent import ToolExecutorAgent
from info_hunter_agent import InfoHunterAgent # Import the new agent
# Placeholder for other agent types
# from synthesizer_agent import SynthesizerAgent

logger = logging.getLogger(__name__) # Module-level logger

class MasterController:
    def __init__(self, config_path='config.yaml'):
        self.config = self._load_config(config_path)
        self.llm_interface = LLMInterface(self.config) # Pass the whole config
        self.memory_system = MemorySystem(self.config) # Pass the whole config
        self.task_queue = deque()
        self.agents = {} # Dictionary to store active agents {agent_id: agent_instance}
        self.active_tasks = {} # Dictionary to store active asyncio tasks {agent_id: asyncio.Task}
        self.completed_tasks_history = deque(maxlen=50) # Store recent task outcomes {task_id: status_dict}
        self.status_update_interval = 5 # seconds
        self.status_memory_key = "tac_controller_status"
        self.agent_creation_lock = asyncio.Lock()
        self.max_concurrent_agents = self.config.get('master_controller', {}).get('max_concurrent_agents', 5)
        self.max_task_retries = self.config.get('master_controller', {}).get('max_task_retries', 1) # Add max retries
        
        logger.info("Master Controller Initialized.")
        logger.info(f"LLM Provider: {self.config.get('llm', {}).get('provider')}")
        logger.info(f"Memory Backend: {self.config.get('memory', {}).get('backend')}")
        logger.info(f"Max Concurrent Agents: {self.max_concurrent_agents}")
        logger.info(f"Max Task Retries: {self.max_task_retries}")

    def _load_config(self, config_path):
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.error(f"Configuration file '{config_path}' not found. Exiting.")
            exit(1)
        except yaml.YAMLError as e:
            logger.error(f"Error parsing configuration file '{config_path}': {e}. Exiting.")
            exit(1)
        except Exception as e:
            logger.exception(f"An unexpected error occurred loading configuration: {e}. Exiting.")
            exit(1)

    def assign_task(self, task_details, retry_count=0):
        """Adds a task to the central queue with retry count."""
        task_id = str(uuid.uuid4())
        task = {
            'task_id': task_id, 
            'details': task_details, 
            'status': 'pending', 
            'retry_count': retry_count
        }
        if retry_count > 0:
            self.task_queue.appendleft(task) # Prioritize retries slightly
            logger.info(f"Task {task_id} re-queued (Retry {retry_count}/{self.max_task_retries}): {str(task_details)[:100]}...")
        else:
             self.task_queue.append(task)
             logger.info(f"Task {task_id} assigned: {str(task_details)[:100]}...")
        return task_id

    async def _create_agent(self, agent_type="default", task_details=None):
        """Creates a new agent instance based on type hint or task details."""
        async with self.agent_creation_lock:
            if len(self.agents) >= self.max_concurrent_agents:
                logger.warning("Max concurrent agent limit reached. Cannot create new agent yet.")
                return None

            agent_id = f"{agent_type}-{str(uuid.uuid4())[:8]}"
            agent_instance = None
            task_info = task_details or {} # Use empty dict if no details passed

            common_args = {
                'agent_id': agent_id,
                'master_controller': self,
                'llm_interface': self.llm_interface,
                'memory_system': self.memory_system,
                'config': self.config # Pass the full config down
            }

            # Agent routing logic
            effective_agent_type = agent_type
            if agent_type == 'default': # If default, try to infer from task details
                 if 'url' in task_info:
                      effective_agent_type = 'browser'
                 elif 'description' in task_info and 'create' in task_info['description'].lower():
                      effective_agent_type = 'tool_creator'
                 elif 'code' in task_info or 'code_key' in task_info:
                      effective_agent_type = 'tool_executor'
                 elif 'description' in task_info and ('find' in task_info['description'].lower() or 'research' in task_info['description'].lower() or 'gather' in task_info['description'].lower()):
                      effective_agent_type = 'info_hunter'
                 # Add more inference rules here

            logger.debug(f"Attempting to create agent of effective type: {effective_agent_type}")

            if effective_agent_type == "browser":
                agent_instance = BrowserAgent(**common_args)
            elif effective_agent_type == "tool_creator":
                 agent_instance = ToolCreatorAgent(**common_args)
            elif effective_agent_type == "tool_executor":
                 agent_instance = ToolExecutorAgent(**common_args)
            elif effective_agent_type == "info_hunter":
                 agent_instance = InfoHunterAgent(**common_args)
            # Add other agent types here
            # elif effective_agent_type == "synthesizer":
            #     agent_instance = SynthesizerAgent(**common_args)
            else:
                # Default generic agent
                logger.warning(f"Creating default Agent (type hint was '{agent_type}'). Task details might not match.")
                agent_instance = Agent(**common_args)

            if agent_instance:
                self.agents[agent_id] = agent_instance
                logger.info(f"Agent {agent_id} of type {type(agent_instance).__name__} created.")
                return agent_instance
            else:
                logger.error(f"Failed to create agent of type '{effective_agent_type}' (Hint: '{agent_type}').")
                return None

    async def run(self):
        logger.info("Master Controller run loop started.")
        self.running = True
        last_status_update_time = time.time() # Requires `import time` at the top

        try:
            while self.running or self.active_tasks:
                # Launch new tasks if queue has items and concurrency limit allows
                while self.task_queue and len(self.active_tasks) < self.max_concurrent_agents:
                    task_details_with_meta = self.task_queue.popleft()
                    logger.debug(f"Attempting to start task {task_details_with_meta['task_id']} (Retry: {task_details_with_meta.get('retry_count', 0)}): {task_details_with_meta['details']}")
                    
                    # --- Agent Selection/Creation --- 
                    agent_type_hint = task_details_with_meta['details'].get('agent_type', 'default')
                    # Pass task details to potentially help with agent type inference
                    agent = await self._create_agent(
                        agent_type=agent_type_hint, 
                        task_details=task_details_with_meta['details']
                    )
                    
                    if agent:
                        logger.info(f"Delegating task {task_details_with_meta['task_id']} to agent {agent.agent_id} concurrently.")
                        # Create an asyncio task for the agent to receive and process the task
                        agent_task = asyncio.create_task(
                            self._run_agent_task(agent, task_details_with_meta),
                            name=f"AgentTask-{agent.agent_id}-{task_details_with_meta['task_id']}"
                        )
                        self.active_tasks[agent.agent_id] = agent_task
                        task_details_with_meta['status'] = 'running' 
                        # Add callback to handle task completion/errors
                        agent_task.add_done_callback(self._handle_task_completion)
                    else:
                        logger.warning(f"Failed to create agent for task {task_details_with_meta['task_id']}. Re-queueing.")
                        # Re-queue preserving retry count
                        current_retry_count = task_details_with_meta.get('retry_count', 0)
                        self.assign_task(task_details_with_meta['details'], retry_count=current_retry_count) 
                        # Need to handle the original task metadata removal if re-queued via assign_task
                        # Simplified: just put back for now, retry logic is in _handle_task_completion
                        # self.task_queue.appendleft(task_details_with_meta)
                        # await asyncio.sleep(1) 
                        pass # Let assign_task handle logging and queueing

                # If queue is empty or max concurrency reached, wait a bit
                if not self.task_queue and not self.active_tasks and not self.running:
                     break # Exit loop if shutdown initiated and no tasks left

                # Periodically update status in memory
                current_time = time.time()
                if current_time - last_status_update_time > self.status_update_interval:
                    await self._update_status_in_memory()
                    last_status_update_time = current_time

                # Check for completed tasks (handled by callback, but sleep yields control)
                await asyncio.sleep(0.5) # Yield control, allow tasks to run

            # Final status update on clean exit
            await self._update_status_in_memory(clear_on_shutdown=True)
            logger.info("Master Controller run loop finished.")

        except KeyboardInterrupt:
            logger.warning("Master Controller received shutdown signal (KeyboardInterrupt). Initiating shutdown...")
            await self.shutdown()
        except asyncio.CancelledError:
            logger.warning("Master Controller run loop cancelled. Initiating shutdown...")
            await self.shutdown()
        except Exception as e:
            logger.exception(f"An unexpected error occurred in the Master Controller run loop: {e}")
            await self.shutdown()
        finally:
             if self.memory_system:
                  await self._update_status_in_memory(clear_on_shutdown=True)

    async def _run_agent_task(self, agent: Agent, task_with_meta: dict):
        task_id = task_with_meta['task_id']
        task_details = task_with_meta['details']
        # Store meta on agent for callback access (temporary)
        agent._task_meta_for_callback = task_with_meta 
        logger.debug(f"Executing task {task_id} in agent {agent.agent_id} (Retry: {task_with_meta.get('retry_count', 0)})...")
        try:
            await agent.receive_task(task_details)
            task_with_meta['status'] = 'completed'
            logger.info(f"Async task for Agent {agent.agent_id} (Task ID: {task_id}) completed successfully.")
        except asyncio.CancelledError:
            task_with_meta['status'] = 'cancelled'
            logger.warning(f"Async task for Agent {agent.agent_id} (Task ID: {task_id}) was cancelled.")
            raise # Re-raise CancelledError
        except Exception as e:
            task_with_meta['status'] = 'error'
            logger.exception(f"Error in async task for Agent {agent.agent_id} (Task ID: {task_id}): {e}")
            task_with_meta['error'] = str(e)
            # Do not re-raise general exceptions, let completion handler manage retry
        finally:
            await self.receive_agent_update(agent.agent_id, agent.state, task_with_meta.get('error'))
            self.completed_tasks_history.append({task_id: task_with_meta})
            logger.debug(f"Added task {task_id} to completed history with status {task_with_meta.get('status')}.")
            # Don't clean up agent._task_meta_for_callback here, callback needs it

    def _handle_task_completion(self, task: asyncio.Task):
        agent_id = None
        original_task_meta = None # Store the original task meta if found
        # Find agent_id associated with this task
        # We need to associate the asyncio task back to the original task metadata
        # Modifying _run_agent_task or the structure might be needed.
        # Let's assume for now we can retrieve it based on agent_id mapping.
        for aid, t in self.active_tasks.items():
            if t == task:
                agent_id = aid
                # How to get original_task_meta here? 
                # Option 1: Store it with the agent? 
                # Option 2: Store {task_id: meta} mapping?
                # Option 3: Pass meta to the callback? (Not directly possible)
                # Let's try adding it to the agent temporarily.
                if agent_id in self.agents:
                     original_task_meta = getattr(self.agents[agent_id], '_task_meta_for_callback', None)
                break
        
        if agent_id:
            logger.debug(f"Handling completion callback for Agent {agent_id}'s task.")
            if agent_id in self.active_tasks: del self.active_tasks[agent_id]
            
            agent_instance = self.agents.get(agent_id)
            if agent_instance and agent_instance.state == "error" and original_task_meta:
                # --- Retry Logic --- 
                current_retry = original_task_meta.get('retry_count', 0)
                if current_retry < self.max_task_retries:
                    logger.warning(f"Task {original_task_meta['task_id']} failed (Agent: {agent_id}). Retrying (Attempt {current_retry + 1}/{self.max_task_retries})...")
                    self.assign_task(original_task_meta['details'], retry_count=current_retry + 1)
                else:
                    logger.error(f"Task {original_task_meta['task_id']} failed after {self.max_task_retries} retries (Agent: {agent_id}). Giving up.")
            elif agent_instance:
                 logger.debug(f"Task for agent {agent_id} finished with state: {agent_instance.state}")
                 # Consider cleanup/reuse
            
            # Clean up temporary attribute on agent
            if agent_instance and hasattr(agent_instance, '_task_meta_for_callback'):
                 delattr(agent_instance, '_task_meta_for_callback')
                 
        else:
            logger.warning(f"Completed task {task.get_name()} could not be mapped back to an active agent.")

        exception = task.exception()
        if exception and not isinstance(exception, asyncio.CancelledError):
            # Log exception details if it wasn't handled/logged adequately elsewhere
            logger.error(f"Task {task.get_name()} completed with unhandled exception: {exception}", exc_info=False) # Set exc_info=True for traceback

    async def shutdown(self):
        logger.info("Initiating Master Controller shutdown...")
        self.running = False # Signal run loop to stop accepting new tasks

        # Cancel all active agent tasks
        if self.active_tasks:
            logger.info(f"Cancelling {len(self.active_tasks)} active agent tasks...")
            for agent_id, task in list(self.active_tasks.items()):
                if not task.done():
                    task.cancel()
                    logger.info(f"Cancelled task for agent {agent_id}.")
            # Wait for tasks to finish cancellation
            await asyncio.gather(*self.active_tasks.values(), return_exceptions=True)
            logger.info("Active tasks cancellation complete.")
            self.active_tasks.clear()

        # Shutdown individual agents (e.g., close browsers)
        logger.info(f"Shutting down {len(self.agents)} agents...")
        shutdown_tasks = []
        for agent_id, agent in list(self.agents.items()):
            agent.stop() # Set state to stopped
            if hasattr(agent, 'shutdown_browser'): # Specific cleanup for browser agents
                 logger.info(f"Scheduling browser shutdown for agent {agent_id}")
                 shutdown_tasks.append(asyncio.create_task(agent.shutdown_browser()))
            # Add other specific shutdown methods here
        
        if shutdown_tasks:
             await asyncio.gather(*shutdown_tasks, return_exceptions=True)
             logger.info("Agent-specific shutdown procedures complete.")

        self.agents.clear()
        self.task_queue.clear()
        logger.info("Master Controller shutdown complete.")

    async def receive_agent_update(self, agent_id, state, result=None):
         logger.debug(f"Received update from Agent {agent_id}: State={state}, Result={str(result)[:100]}...")
         if agent_id in self.agents:
             self.agents[agent_id].state = state
             # Further logic based on state (e.g., if finished, remove/reassign)
             if state in ["finished", "error", "cancelled"]:
                  logger.debug(f"Agent {agent_id} reported state {state}. Considering cleanup/reuse.")
                  # Note: Actual cleanup might happen in _handle_task_completion callback for simplicity
         else:
              logger.warning(f"Received update from unknown agent ID: {agent_id}")

    async def _update_status_in_memory(self, clear_on_shutdown=False):
        """Stores the current controller status in the memory system."""
        if not self.memory_system:
            return
        
        if clear_on_shutdown:
             logger.info(f"Clearing status from memory key: {self.status_memory_key}")
             self.memory_system.delete(self.status_memory_key)
             return

        try:
            # Gather current state information
            agent_states = {aid: {'type': type(agent).__name__, 'state': agent.state, 'task': agent.current_task} 
                            for aid, agent in self.agents.items()}
            
            status_data = {
                'timestamp': time.time(),
                'task_queue_size': len(self.task_queue),
                'pending_tasks': list(self.task_queue), # Store limited queue info
                'active_agents': agent_states,
                'active_agent_count': len(self.agents),
                'max_concurrent_agents': self.max_concurrent_agents,
                'completed_tasks_history': list(self.completed_tasks_history) # Recent history
            }
            # Store as JSON string in memory
            self.memory_system.store(self.status_memory_key, json.dumps(status_data), is_short_term=True) # Store in short-term/cache
            logger.debug(f"Updated status in memory key: {self.status_memory_key}")
        except Exception as e:
            logger.exception(f"Error updating status in memory: {e}")

# Example Usage
async def main():
    controller = MasterController()

    # Example Tasks
    task1_id = controller.assign_task({
        'description': "Find 5 latest AI research papers on agentic workflows",
        'agent_type': 'info_hunter' # Hint for a future agent type
    })
    task2_id = controller.assign_task({
        'url': 'https://example.com',
        'action': 'scrape_text',
        'agent_type': 'browser'
    })
    task3_id = controller.assign_task({
        'description': "Create a python script that takes a number and prints its square.",
        'agent_type': 'tool_creator',
        'filename': 'square_tool.py' # Ask creator to save the tool
    })
    # Add a task to execute the created tool (assuming task 3 completes first)
    # In a real system, this would likely be triggered by task 3 completion
    task4_id = controller.assign_task({
         'description': 'Execute the square_tool.py script created previously.',
         # Let the controller infer the type based on 'code_key' or 'code'
         # We need the ToolCreatorAgent to store the code in memory or provide the path
         # For now, let's assume ToolCreatorAgent stored it with a known key:
         'code_key': 'toolcreatoragent-xxxx_generated_tool_Create a python scr...'
         # OR provide the code directly (less common between agents)
         # 'code': 'import sys\nnum=int(sys.argv[1])\nprint(num*num)' # Example code
    })

    # Run the controller's main loop
    await controller.run()

if __name__ == "__main__":
    # Ensure OPENAI_API_KEY etc. are set in environment if needed by components
    # Check README for setup.
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nMain execution stopped by user.") 