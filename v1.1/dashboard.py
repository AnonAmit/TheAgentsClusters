# dashboard.py
# Basic Streamlit dashboard to view TAC status from memory.

import streamlit as st
import yaml
import json
import time
import pandas as pd
from datetime import datetime

from memory import MemorySystem # Import MemorySystem to read status

def load_config(config_path='config.yaml'):
    """Loads configuration safely."""
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        st.error(f"Error: Configuration file '{config_path}' not found.")
        return None
    except yaml.YAMLError as e:
        st.error(f"Error parsing configuration file '{config_path}': {e}.")
        return None
    except Exception as e:
        st.error(f"An unexpected error occurred loading configuration: {e}.")
        return None

@st.cache_resource # Cache the memory system resource
def get_memory_system(config):
    """Initializes and returns the memory system."""
    if config:
        try:
            return MemorySystem(config)
        except Exception as e:
             st.error(f"Failed to initialize Memory System: {e}")
             return None
    return None

def display_dashboard(memory_system):
    """Retrieves status from memory and displays it."""
    if not memory_system:
        st.warning("Memory System not available.")
        return

    status_key = "tac_controller_status"
    status_json = memory_system.retrieve(status_key, check_long_term_if_missing=True)

    if not status_json:
        st.warning(f"No status data found in memory key '{status_key}'. Is the Master Controller running?")
        # Display placeholder values or structure
        st.metric("Task Queue Size", "N/A")
        st.metric("Active Agents", "N/A")
        st.write("Pending Tasks: []")
        st.write("Active Agents Details: {}")
        st.write("Completed Tasks History: []")
        return

    try:
        status_data = json.loads(status_json)
    except json.JSONDecodeError:
        st.error(f"Failed to decode status data from memory key '{status_key}'. Content: {status_json[:200]}...")
        return
    except Exception as e:
         st.error(f"Error processing status data: {e}")
         return

    # --- Display Metrics ---
    col1, col2, col3 = st.columns(3)
    col1.metric("Task Queue Size", status_data.get('task_queue_size', 'N/A'))
    active_agents = status_data.get('active_agent_count', 'N/A')
    max_agents = status_data.get('max_concurrent_agents', '?')
    col2.metric("Active Agents", f"{active_agents}/{max_agents}")
    last_updated = datetime.fromtimestamp(status_data.get('timestamp', 0)).strftime('%Y-%m-%d %H:%M:%S')
    col3.metric("Last Updated", last_updated)

    st.divider()

    # --- Display Task Queue (Limited) ---
    st.subheader("Pending Tasks (Queue)")
    pending_tasks = status_data.get('pending_tasks', [])
    if pending_tasks:
         # Convert task details to string for display if they are dicts
         display_tasks = []
         for task in pending_tasks[:10]: # Limit display
              task_display = task.copy()
              if isinstance(task_display.get('details'), dict):
                   task_display['details'] = json.dumps(task_display['details']) 
              display_tasks.append(task_display)
         st.dataframe(display_tasks, use_container_width=True)
         if len(pending_tasks) > 10:
              st.caption(f"... and {len(pending_tasks) - 10} more tasks in queue.")
    else:
        st.write("Task queue is empty.")

    st.divider()

    # --- Display Active Agents ---
    st.subheader("Active Agents")
    active_agents_dict = status_data.get('active_agents', {})
    if active_agents_dict:
        agent_list = []
        for agent_id, agent_info in active_agents_dict.items():
            current_task_str = json.dumps(agent_info.get('task')) if agent_info.get('task') else "None"
            agent_list.append({
                'ID': agent_id,
                'Type': agent_info.get('type', 'Unknown'),
                'State': agent_info.get('state', 'Unknown'),
                'Current Task': current_task_str[:100] + ("..." if len(current_task_str)>100 else "")
            })
        st.dataframe(pd.DataFrame(agent_list), use_container_width=True)
    else:
        st.write("No agents are currently active.")

    st.divider()
    
    # --- Display Completed Task History ---
    st.subheader("Recent Task History (Last 50)")
    history = status_data.get('completed_tasks_history', [])
    if history:
         history_list = []
         for task_entry in reversed(history): # Show newest first
              task_id = list(task_entry.keys())[0]
              task_info = task_entry[task_id]
              details_str = json.dumps(task_info.get('details')) if isinstance(task_info.get('details'), dict) else str(task_info.get('details', ''))
              history_list.append({
                   'Task ID': task_id,
                   'Status': task_info.get('status', 'unknown'),
                   'Details': details_str[:100] + ("..." if len(details_str)>100 else ""),
                   'Error': task_info.get('error', 'None')
              })
         st.dataframe(pd.DataFrame(history_list), use_container_width=True)
    else:
         st.write("No completed tasks in recent history.")


# --- Main App Logic ---
st.set_page_config(page_title="TAC Dashboard", layout="wide")
st.title("🤖 THE AGENTS CLUSTER [TAC] Dashboard")
st.caption("Monitoring the status of the Master Controller and Agents.")

config = load_config()
memory_system = get_memory_system(config)

# Placeholder for the main display area
display_placeholder = st.empty()

# Auto-refresh loop
while True:
    with display_placeholder.container():
        display_dashboard(memory_system)
    time.sleep(5) # Refresh interval in seconds 