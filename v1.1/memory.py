# memory.py

import json
import os
import redis
import logging

# Import ChromaDB if available
try:
    import chromadb
    from chromadb.utils import embedding_functions
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    chromadb = None # Define for type hinting
    embedding_functions = None
    logging.getLogger(__name__).warning("ChromaDB library not found. Vector DB functionality disabled. Run `pip install chromadb`")

logger = logging.getLogger(__name__)

class MemorySystem:
    def __init__(self, config):
        self.config = config.get('memory', {})
        self.backend_type = self.config.get('backend', 'json_file') # Default to json_file
        self.short_term_memory = {} # In-memory cache, regardless of backend
        self.backend_client = None
        self.chroma_collection = None # Specific attribute for Chroma collection

        logger.info(f"Initializing Memory System with backend: {self.backend_type}")

        if self.backend_type == 'redis':
            try:
                redis_conf = self.config.get('redis', {})
                self.backend_client = redis.Redis(
                    host=redis_conf.get('host', 'localhost'),
                    port=redis_conf.get('port', 6379),
                    db=redis_conf.get('db', 0),
                    decode_responses=True # Decode responses to strings
                )
                # Test connection
                self.backend_client.ping()
                logger.info(f"Redis connection successful to {redis_conf.get('host', 'localhost')}:{redis_conf.get('port', 6379)}")
            except redis.exceptions.ConnectionError as e:
                logger.error(f"Error connecting to Redis: {e}. Falling back to JSON file.")
                self.backend_type = 'json_file'
                self._initialize_json_backend()
            except Exception as e:
                 logger.exception(f"An unexpected error occurred during Redis initialization: {e}. Falling back to JSON file.")
                 self.backend_type = 'json_file'
                 self._initialize_json_backend()

        elif self.backend_type == 'json_file':
            self._initialize_json_backend()

        elif self.backend_type == 'vector_db' and self.config.get('vector_db', {}).get('provider') == 'chromadb':
             if not CHROMA_AVAILABLE:
                  logger.error("ChromaDB backend configured, but library not installed. Falling back to JSON.")
                  self.backend_type = 'json_file'
                  self._initialize_json_backend()
             else:
                  self._initialize_chromadb()
        
        elif self.backend_type == 'vector_db':
             logger.warning(f"Vector DB backend configured, but provider is not 'chromadb' or not supported: {self.config.get('vector_db',{}).get('provider')}. Falling back to JSON.")
             self.backend_type = 'json_file'
             self._initialize_json_backend()

        else:
            logger.warning(f"Unknown memory backend '{self.backend_type}'. Using default short-term memory only.")
            self.backend_type = 'short_term_only'

    def _initialize_json_backend(self):
        json_conf = self.config.get('json_file', {})
        self.json_file_path = json_conf.get('path', './tac_memory.json')
        logger.info(f"Using JSON file backend at: {self.json_file_path}")
        # Load existing data if file exists
        if os.path.exists(self.json_file_path):
            try:
                with open(self.json_file_path, 'r') as f:
                    self.backend_client = json.load(f)
            except json.JSONDecodeError:
                logger.warning(f"Warning: Could not decode JSON from {self.json_file_path}. Starting with empty memory.")
                self.backend_client = {}
            except Exception as e:
                logger.error(f"Error reading JSON file {self.json_file_path}: {e}. Starting with empty memory.")
                self.backend_client = {}
        else:
            self.backend_client = {}
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.json_file_path) or '.', exist_ok=True)
            self._save_json()

    def _initialize_chromadb(self):
        chroma_conf = self.config.get('vector_db', {})
        db_path = chroma_conf.get('path', './tac_chroma_store')
        collection_name = chroma_conf.get('collection_name', 'tac_agent_memory')
        # embedding_func_name = chroma_conf.get('embedding_function', 'default')
        # distance_func = chroma_conf.get('distance_function', 'cosine')

        logger.info(f"Initializing ChromaDB backend. Path: {db_path}, Collection: {collection_name}")
        try:
             # Use persistent client if path is provided
             self.backend_client = chromadb.PersistentClient(path=db_path)
             # TODO: Add support for embedding functions if needed for actual vector search
             # ef = embedding_functions.DefaultEmbeddingFunction() # Example, requires sentence-transformers
             # self.chroma_collection = self.backend_client.get_or_create_collection(name=collection_name, embedding_function=ef, metadata={"hnsw:space": distance_func})
             self.chroma_collection = self.backend_client.get_or_create_collection(name=collection_name)
             logger.info(f"ChromaDB collection '{collection_name}' loaded/created successfully.")
        except Exception as e:
            logger.exception(f"Error initializing ChromaDB client/collection: {e}. Falling back to JSON.")
            self.backend_type = 'json_file'
            self.backend_client = None
            self.chroma_collection = None
            self._initialize_json_backend()

    def _save_json(self):
        if self.backend_type == 'json_file' and self.backend_client is not None:
            try:
                with open(self.json_file_path, 'w') as f:
                    json.dump(self.backend_client, f, indent=4)
            except Exception as e:
                logger.exception(f"Error saving memory to JSON file {self.json_file_path}: {e}")

    def store(self, key, value, is_short_term=False):
        """Stores a value in memory.

        Args:
            key (str): The key to store the value under.
            value (any): The value to store (must be JSON serializable for json_file backend).
            is_short_term (bool): If True, stores only in the in-memory cache.
                                  If False, stores in the backend (and cache).
        """
        self.short_term_memory[key] = value
        logger.debug(f"Stored in short-term memory: {key}=\"{str(value)[:50]}...\"")

        if not is_short_term:
            if self.backend_type == 'redis' and self.backend_client:
                try:
                    # Redis stores strings, serialize complex types if needed
                    serialized_value = json.dumps(value) if not isinstance(value, (str, int, float)) else value
                    self.backend_client.set(key, serialized_value)
                    logger.debug(f"Stored in Redis backend: {key}")
                except Exception as e:
                    logger.exception(f"Error storing key '{key}' in Redis: {e}")
            elif self.backend_type == 'json_file' and self.backend_client is not None:
                self.backend_client[key] = value
                self._save_json()
                logger.debug(f"Stored in JSON backend: {key}")
            elif self.backend_type == 'vector_db' and self.chroma_collection is not None:
                try:
                     # Basic key-value store using Chroma metadata
                     # We use the key as the ID. The value is stored in metadata.
                     # The document itself can be empty or a summary if needed for search later.
                     serialized_value = json.dumps(value) # Ensure value is string for metadata
                     self.chroma_collection.upsert(
                         ids=[key],
                         documents=["placeholder_document"], # Document needed, content optional for key-value use
                         metadatas=[{'value': serialized_value}] # Store actual value here
                     )
                     logger.debug(f"Stored key '{key}' in ChromaDB backend.")
                except Exception as e:
                     logger.exception(f"Error storing key '{key}' in ChromaDB: {e}")
            elif self.backend_type == 'short_term_only':
                 logger.warning(f"Key '{key}' stored only in short-term memory (no backend configured).")
            else:
                logger.warning(f"Cannot store key '{key}' in long-term memory. Backend ('{self.backend_type}') not available or misconfigured.")


    def retrieve(self, key, check_long_term_if_missing=True):
        """Retrieves a value from memory.

        Checks short-term memory first. If not found and `check_long_term_if_missing` is True,
        it checks the configured long-term backend.

        Args:
            key (str): The key to retrieve.
            check_long_term_if_missing (bool): Whether to check the backend if not in short-term memory.

        Returns:
            any: The retrieved value, or None if not found.
        """
        value = self.short_term_memory.get(key)
        if value is not None:
            logger.debug(f"Retrieved from short-term memory: {key}")
            return value

        if check_long_term_if_missing:
            logger.debug(f"Key '{key}' not in short-term memory. Checking backend ({self.backend_type})...")
            if self.backend_type == 'redis' and self.backend_client:
                try:
                    retrieved_value = self.backend_client.get(key)
                    if retrieved_value is not None:
                        logger.debug(f"Retrieved from Redis backend: {key}")
                        # Attempt to deserialize if it looks like JSON
                        try:
                            value = json.loads(retrieved_value)
                        except json.JSONDecodeError:
                            value = retrieved_value # Assume it was stored as a plain string
                        # Cache it in short-term memory for faster access next time
                        self.short_term_memory[key] = value
                        return value
                except Exception as e:
                    logger.exception(f"Error retrieving key '{key}' from Redis: {e}")
            elif self.backend_type == 'json_file' and self.backend_client is not None:
                value = self.backend_client.get(key)
                if value is not None:
                    logger.debug(f"Retrieved from JSON backend: {key}")
                    self.short_term_memory[key] = value # Cache it
                    return value
            elif self.backend_type == 'vector_db' and self.chroma_collection is not None:
                try:
                     # Retrieve by ID (our key)
                     result = self.chroma_collection.get(ids=[key], include=['metadatas'])
                     if result and result['ids']:
                         metadata = result['metadatas'][0]
                         if metadata and 'value' in metadata:
                             serialized_value = metadata['value']
                             value = json.loads(serialized_value) # Deserialize from metadata
                             logger.debug(f"Retrieved key '{key}' from ChromaDB backend.")
                             self.short_term_memory[key] = value # Cache it
                             return value
                         else:
                              logger.warning(f"Key '{key}' found in ChromaDB but missing 'value' in metadata: {metadata}")
                     else:
                          logger.debug(f"Key '{key}' not found in ChromaDB collection.")
                except Exception as e:
                     logger.exception(f"Error retrieving key '{key}' from ChromaDB: {e}")

        logger.debug(f"Key '{key}' not found in any memory.")
        return None

    def delete(self, key):
         """Deletes a key from both short-term and long-term memory."""
         deleted_short = self.short_term_memory.pop(key, None)
         deleted_long = False

         if self.backend_type == 'redis' and self.backend_client:
             try:
                 deleted_count = self.backend_client.delete(key)
                 deleted_long = deleted_count > 0
             except Exception as e:
                 logger.exception(f"Error deleting key '{key}' from Redis: {e}")
         elif self.backend_type == 'json_file' and self.backend_client is not None:
             if key in self.backend_client:
                 del self.backend_client[key]
                 self._save_json()
                 deleted_long = True
         elif self.backend_type == 'vector_db' and self.chroma_collection is not None:
              try:
                  self.chroma_collection.delete(ids=[key])
                  deleted_long = True # Assume success if no error
                  logger.debug(f"Deleted key '{key}' from ChromaDB backend.")
              except Exception as e:
                  logger.exception(f"Error deleting key '{key}' from ChromaDB: {e}")

         if deleted_short or deleted_long:
            logger.info(f"Deleted key '{key}' (found in short-term: {deleted_short is not None}, found in backend: {deleted_long})")
            return True
         else:
            logger.info(f"Key '{key}' not found for deletion.")
            return False

# Example Usage (will be integrated into agents/master)
if __name__ == "__main__":
    import yaml
    # Load config from YAML
    try:
        with open('config.yaml', 'r') as f:
            app_config = yaml.safe_load(f)
    except FileNotFoundError:
        logger.warning("config.yaml not found, using default memory config.")
        app_config = {'memory': {'backend': 'json_file', 'json_file': {'path': './tac_memory_test.json'}}}
    except Exception as e:
        logger.error(f"Error loading config.yaml: {e}")
        app_config = {'memory': {'backend': 'json_file', 'json_file': {'path': './tac_memory_test.json'}}}

    # --- Setup Logging --- 
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    memory_system = MemorySystem(app_config)

    # Test storing and retrieving
    memory_system.store("task_1_result", "Some data", is_short_term=True)
    retrieved_data_short = memory_system.retrieve("task_1_result")
    logger.info(f"Retrieved short-term only: {retrieved_data_short}")

    memory_system.store("agent_history", ["action1", "action2"], is_short_term=False)
    history = memory_system.retrieve("agent_history", check_long_term_if_missing=True)
    logger.info(f"Retrieved potentially long-term: {history}")

    # Retrieve something not present in short-term initially
    retrieved_again = memory_system.retrieve("agent_history")
    logger.info(f"Retrieved again (should be cached): {retrieved_again}")

    # Test deletion
    memory_system.delete("task_1_result")
    memory_system.delete("agent_history")
    logger.info(f"Attempting to retrieve deleted key: {memory_system.retrieve('agent_history')}")

    # Clean up test json file if created
    if memory_system.backend_type == 'json_file' and 'test' in memory_system.json_file_path:
        if os.path.exists(memory_system.json_file_path):
            os.remove(memory_system.json_file_path)
            logger.info(f"Cleaned up test file: {memory_system.json_file_path}") 