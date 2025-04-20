# cli.py

import argparse
import asyncio
import sys
import json
import logging # Import logging
from master_controller import MasterController
from logging_config import setup_logging # Import setup function

async def main():
    parser = argparse.ArgumentParser(description="Run THE AGENTS CLUSTER [TAC] Master Controller.")
    
    parser.add_argument(
        "-t", "--task", 
        type=str, 
        help="Assign an initial task using a description string."
    )
    parser.add_argument(
        "-d", "--details",
        type=str,
        help='Assign an initial task using a JSON string for detailed configuration (e.g., {\'url\': \'http://example.com\', \'action\': \'scrape_text\'}). Overrides --task if provided.'
    )
    parser.add_argument(
        "-c", "--config", 
        type=str, 
        default="config.yaml", 
        help="Path to the configuration file (default: config.yaml)."
    )

    args = parser.parse_args()

    # --- Setup Logging --- 
    # Setup logging early, using the specified config file
    setup_logging(config_path=args.config)
    logger = logging.getLogger(__name__) # Get logger for this module

    # --- Initialize Master Controller ---
    logger.info(f"Loading configuration from: {args.config}")
    try:
        controller = MasterController(config_path=args.config)
        logger.info("Master Controller initialized successfully.")
    except Exception as e:
        logger.exception(f"Fatal: Failed to initialize Master Controller: {e}") # Use logger.exception for errors with tracebacks
        sys.exit(1)

    # --- Assign Initial Task (if provided) ---
    initial_task_details = None
    if args.details:
        try:
            initial_task_details = json.loads(args.details)
            if not isinstance(initial_task_details, dict):
                 raise ValueError("Task details must be a JSON object.")
            logger.info(f"Assigning initial task from --details: {initial_task_details}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON provided for --details: {e}")
            sys.exit(1)
        except ValueError as e:
            logger.error(f"Error in task details: {e}")
            sys.exit(1)
    elif args.task:
        initial_task_details = {"description": args.task}
        logger.info(f"Assigning initial task from --task: {initial_task_details}")

    if initial_task_details:
        controller.assign_task(initial_task_details)
    else:
         logger.info("No initial task assigned via command line.")
         # Optionally assign a default task or just start
         # controller.assign_task({'description': 'Default startup task: Report status.'}) 

    # --- Run the Controller ---
    logger.info("Starting Master Controller run loop... Press Ctrl+C to stop.")
    await controller.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Logger might already be shut down here, use print
        print("\nCLI detected KeyboardInterrupt. Controller shutdown should be handled internally.") 
    except Exception as e:
        # Use logger if possible, otherwise print
        try:
            logging.getLogger(__name__).exception(f"An unexpected error occurred in the CLI: {e}")
        except Exception:
             print(f"\nAn unexpected error occurred in the CLI: {e}")