# tool_creator_agent.py
import asyncio
import inspect # To help format the generated code
from agent_template import Agent
from llm_interface import LLMInterface
from memory import MemorySystem

class ToolCreatorAgent(Agent):
    def __init__(self, agent_id: str, master_controller, llm_interface: LLMInterface, memory_system: MemorySystem, config: dict):
        super().__init__(agent_id, master_controller, llm_interface, memory_system, config)
        print(f"ToolCreatorAgent {self.agent_id} initialized.")
        if not self.llm or not self.llm.client:
             print(f"Warning: ToolCreatorAgent {self.agent_id} requires an initialized LLM client, but it's not available.")

    async def process_task(self, task_details):
        """Overrides the base Agent method to handle tool creation tasks."""
        print(f"ToolCreatorAgent {self.agent_id} received task: {task_details}")
        description = task_details.get('description')
        target_filename = task_details.get('filename') # Optional filename to save to

        if not description:
            return "Error: Missing 'description' for ToolCreatorAgent task."
        if not self.llm or not self.llm.client:
            return "Error: LLM client not available for ToolCreatorAgent."

        # Generate the tool code using LLM
        tool_code = await self.generate_tool_code(description)

        if tool_code.startswith("Error:"):
            return tool_code # Propagate error message

        result_message = f"Generated tool code for: '{description}'\n```python\n{tool_code}\n```"

        # Optionally save the generated code to a file
        if target_filename:
            try:
                with open(target_filename, 'w') as f:
                    f.write(tool_code)
                print(f"Agent {self.agent_id}: Saved generated tool to {target_filename}")
                result_message += f"\nSaved to: {target_filename}"
            except Exception as e:
                print(f"Agent {self.agent_id}: Error saving tool to {target_filename}: {e}")
                result_message += f"\nError saving to file: {e}"

        # Store the code in memory as well
        self.memory.store(f"{self.agent_id}_generated_tool_{description[:20]}...", tool_code, is_short_term=False)

        return result_message

    async def generate_tool_code(self, description):
        print(f"ToolCreatorAgent {self.agent_id} generating tool for: {description}")

        # Construct a more specific prompt for the LLM
        prompt = f"""
        Based on the following description, generate a complete, self-contained Python script that performs the described task.
        The script should be ready to run.
        Include necessary imports.
        If the task involves processing data, include example usage within an `if __name__ == \"__main__\":` block.
        Focus on clarity and correctness.

        Description: "{description}"

        Python Code:
        ```python
        """

        # Use asyncio.to_thread for the potentially blocking LLM call
        try:
            generated_code = await asyncio.to_thread(
                self.llm.generate,
                prompt=prompt,
                system_prompt="You are an expert Python programmer generating executable scripts based on descriptions.",
                max_tokens=1500, # Allow longer code generation
                temperature=0.5 # Slightly more deterministic for code
            )

            # Basic cleanup of the generated code (remove markdown backticks, etc.)
            if generated_code.startswith("```python"):
                generated_code = generated_code[len("```python"):].strip()
            if generated_code.endswith("```"):
                generated_code = generated_code[:-len("```")].strip()
            
            # Attempt to make indentation consistent (basic approach)
            generated_code = inspect.cleandoc(generated_code)

            print(f"Agent {self.agent_id}: Code generation successful.")
            return generated_code
        except Exception as e:
            error_msg = f"Error during LLM code generation for '{description}': {e}"
            print(f"Agent {self.agent_id}: {error_msg}")
            return f"Error: {error_msg}"

    # No specific browser shutdown needed here
    # Override spawn_sub_agents if needed
    # Override report_back if specific formatting needed 