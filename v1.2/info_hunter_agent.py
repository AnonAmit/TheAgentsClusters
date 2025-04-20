# info_hunter_agent.py

import asyncio
import logging
from agent_template import Agent
from llm_interface import LLMInterface
from memory import MemorySystem
# May need BrowserAgent or other tools depending on implementation

logger = logging.getLogger(__name__)

class InfoHunterAgent(Agent):
    """An agent specialized in finding and gathering information based on a query."""
    def __init__(self, agent_id: str, master_controller, llm_interface: LLMInterface, memory_system: MemorySystem, config: dict):
        super().__init__(agent_id, master_controller, llm_interface, memory_system, config)
        logger.info(f"InfoHunterAgent {self.agent_id} initialized.")

    async def process_task(self, task_details):
        """Overrides the base Agent method to handle information gathering tasks."""
        query = task_details.get('description') or task_details.get('query')
        if not query:
            logger.error(f"Agent {self.agent_id}: No query or description provided in task details: {task_details}")
            return "Error: Missing query/description for InfoHunterAgent task."

        logger.info(f"Agent {self.agent_id} starting information hunt for query: '{query}'")

        # --- Planning Phase --- 
        # Use LLM to break down the query and decide on search strategies
        plan = await self._generate_search_plan(query)
        logger.debug(f"Agent {self.agent_id} generated search plan: {plan}")

        # --- Execution Phase --- 
        # This is where the agent would use tools like:
        # 1. BrowserAgent (via master or direct call if allowed) to search web/scrape sites
        # 2. LLM calls for quick facts or known information
        # 3. Future database/API agents
        # 4. Sub-agents for parallel searches
        # Placeholder for actual search execution:
        await asyncio.sleep(2) # Simulate search time
        search_results = [
            f"Simulated result 1 for '{query}'",
            f"Simulated result 2 mentioning related topic",
        ]
        logger.info(f"Agent {self.agent_id} gathered {len(search_results)} raw results.")

        # --- Synthesis Phase --- 
        # Use LLM to synthesize the gathered information into a coherent report
        report = await self._synthesize_results(query, search_results)
        logger.info(f"Agent {self.agent_id} synthesized report for query '{query}'. Length: {len(report)}")
        
        return report # Return the final synthesized report

    async def _generate_search_plan(self, query: str) -> str:
        """Uses LLM to generate a search plan (e.g., keywords, sites, tools to use)."""
        if not self.llm or not self.llm.client:
            logger.warning(f"Agent {self.agent_id}: LLM client not available for planning.")
            return "No plan generated (LLM unavailable)."
        
        plan_prompt = f"Create a concise search plan to find information about: '{query}'. Specify keywords, potential websites (if applicable), and types of information to look for."
        try:
            plan = await asyncio.to_thread(
                self.llm.generate, 
                plan_prompt, 
                system_prompt="You are a research planning assistant.",
                max_tokens=150
            )
            return plan
        except Exception as e:
             logger.error(f"Agent {self.agent_id}: Error generating search plan: {e}")
             return f"Error generating plan: {e}"

    async def _synthesize_results(self, query: str, results: list) -> str:
         """Uses LLM to synthesize raw search results into a report."""
         if not self.llm or not self.llm.client:
            logger.warning(f"Agent {self.agent_id}: LLM client not available for synthesis.")
            return "Synthesis failed (LLM unavailable). Raw results: " + "\n".join(results)
         
         synthesis_prompt = f"Synthesize the following information found regarding the query '{query}' into a concise report:\n\nRAW DATA:\n"+"\n---\n".join(results[:5]) # Limit input tokens
         if len(results)>5:
             synthesis_prompt += "\n... (more results truncated)"
         synthesis_prompt += "\n\nSYNTHESIZED REPORT:"
         
         try:
            report = await asyncio.to_thread(
                self.llm.generate, 
                synthesis_prompt, 
                system_prompt="You are a research synthesis assistant.",
                max_tokens=500
            )
            return report
         except Exception as e:
             logger.error(f"Agent {self.agent_id}: Error synthesizing results: {e}")
             return f"Error synthesizing results: {e}. Raw data: {str(results)}" 