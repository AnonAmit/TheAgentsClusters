# sub_agent_template.py
import asyncio
from typing import Any, Dict

async def execute_sub_agent_task(sub_agent_id: str, task_input: Any) -> Dict[str, Any]:
    """Represents the execution of a lightweight, atomic sub-task.

    Args:
        sub_agent_id (str): A unique identifier for this sub-agent instance.
        task_input (Any): The specific data or instruction for this sub-task.

    Returns:
        Dict[str, Any]: A dictionary containing the status ('success' or 'error')
                      and the result or error message.
    """
    print(f"Sub-agent [{sub_agent_id}] starting task with input: {str(task_input)[:100]}...")
    try:
        # Simulate atomic work (e.g., a specific calculation, API call, data transformation)
        # Replace this with actual sub-task logic
        await asyncio.sleep(0.2) # Simulate I/O or computation
        if isinstance(task_input, dict) and 'operation' in task_input:
            op = task_input['operation']
            # Example specific operation
            if op == 'square':
                num = task_input.get('number', 0)
                result = num * num
            else:
                result = f"Unknown operation: {op}"
        else:
            # Generic processing
            result = f"Processed_{str(task_input)[:50]}"

        print(f"Sub-agent [{sub_agent_id}] finished processing. Result: {str(result)[:100]}...")
        return {"status": "success", "result": result}

    except Exception as e:
        print(f"Sub-agent [{sub_agent_id}] encountered an error: {e}")
        return {"status": "error", "error_message": str(e)}

# Example of how an agent might invoke a sub-agent
async def example_sub_agent_invocation():
    task_data = {'operation': 'square', 'number': 5}
    sub_agent_result = await execute_sub_agent_task("sub-worker-001", task_data)
    print(f"Invocation Example Result: {sub_agent_result}")

    task_data_2 = "Simple text processing"
    sub_agent_result_2 = await execute_sub_agent_task("sub-worker-002", task_data_2)
    print(f"Invocation Example Result 2: {sub_agent_result_2}")

if __name__ == "__main__":
    asyncio.run(example_sub_agent_invocation()) 