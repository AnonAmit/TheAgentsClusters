# logging_config.py

import logging
import sys
import yaml

def setup_logging(config_path='config.yaml', default_level=logging.INFO):
    """Sets up logging based on configuration file."""
    config = {}
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f).get('logging', {})
    except FileNotFoundError:
        print(f"Warning: Logging config file '{config_path}' not found. Using defaults.")
    except yaml.YAMLError as e:
        print(f"Warning: Error parsing logging config file '{config_path}': {e}. Using defaults.")
    except Exception as e:
        print(f"Warning: Unexpected error loading logging config: {e}. Using defaults.")

    log_level_str = config.get('level', 'INFO').upper()
    log_level = getattr(logging, log_level_str, default_level)
    log_format = config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    log_file = config.get('log_file')

    # Get root logger
    logger = logging.getLogger()
    logger.setLevel(log_level) # Set root logger level

    # Clear existing handlers to avoid duplication if called multiple times
    if logger.hasHandlers():
        logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(log_format)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    # Set console handler level explicitly (might differ from root)
    # console_handler.setLevel(log_level) 
    logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(formatter)
            # Set file handler level explicitly (might differ from root)
            # file_handler.setLevel(log_level)
            logger.addHandler(file_handler)
            print(f"Logging to file: {log_file}")
        except Exception as e:
            print(f"Error setting up file logging to {log_file}: {e}")

    print(f"Logging setup complete. Level: {log_level_str}")

# Example basic setup if run directly (for testing)
if __name__ == "__main__":
    setup_logging()
    logging.info("Logging test info message.")
    logging.warning("Logging test warning message.")
    logging.error("Logging test error message.") 