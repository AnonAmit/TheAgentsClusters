# llm_interface.py
import os
import yaml
import logging
from openai import OpenAI, OpenAIError
# Import Anthropic if available
try:
    from anthropic import Anthropic, APIError as AnthropicAPIError
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    Anthropic = None # Define for type hinting
    AnthropicAPIError = None

logger = logging.getLogger(__name__)

class LLMInterface:
    def __init__(self, config):
        self.config = config.get('llm', {})
        self.client = None
        self.provider = self.config.get('provider', 'openai').lower()
        api_key = os.getenv(f"{self.provider.upper()}_API_KEY")
        self.default_model = self._get_default_model()
        self.request_timeout = self.config.get('request_timeout', 120)

        logger.info(f"Initializing LLM Interface for provider: {self.provider}")

        if not api_key:
            logger.error(f"{self.provider.upper()}_API_KEY environment variable not set. LLM client cannot be initialized for this provider.")
            return

        if self.provider == 'openai':
            try:
                self.client = OpenAI(
                    api_key=api_key,
                    timeout=self.request_timeout
                )
                logger.info(f"OpenAI client initialized. Default model: {self.default_model}")
            except OpenAIError as e:
                 logger.exception(f"Error initializing OpenAI client: {e}")
                 self.client = None
            except Exception as e:
                logger.exception(f"An unexpected error occurred during OpenAI initialization: {e}")
                self.client = None
        
        elif self.provider == 'anthropic':
            if not ANTHROPIC_AVAILABLE:
                 logger.error("Anthropic provider configured, but library not installed. Run `pip install anthropic`")
                 return
            try:
                 self.client = Anthropic(
                      api_key=api_key,
                      timeout=float(self.request_timeout) # Timeout might need to be float
                 )
                 # Test connection optional - maybe list models or simple call?
                 logger.info(f"Anthropic client initialized. Default model: {self.default_model}")
            except AnthropicAPIError as e:
                 logger.exception(f"Error initializing Anthropic client: {e}")
                 self.client = None
            except Exception as e:
                 logger.exception(f"An unexpected error occurred during Anthropic initialization: {e}")
                 self.client = None
        
        # Add elif blocks for other providers like 'google'
        else:
            logger.error(f"Unsupported LLM provider configured: {self.provider}")

    def _get_default_model(self):
        """Gets the default model based on the configured provider."""
        provider_models = self.config.get(f'{self.provider}_models', {})
        # Fallback to top-level default_model if provider-specific isn't set
        return provider_models.get('default', self.config.get('default_model'))

    def generate(self, prompt, system_prompt="You are a helpful assistant.", model=None, max_tokens=1000, temperature=0.7):
        if not self.client:
            logger.error("LLM client not initialized. Cannot generate.")
            return "Error: LLM client not ready."

        # Use specific model if provided, else use default for the provider
        model_to_use = model or self.default_model

        if not model_to_use:
             logger.error("No LLM model specified or configured for generation.")
             return "Error: No model specified or configured."

        logger.info(f"Generating text using {self.provider} model '{model_to_use}'...")
        logger.debug(f"Generation Params: max_tokens={max_tokens}, temperature={temperature}")
        logger.debug(f"System Prompt: {system_prompt[:100]}...")
        logger.debug(f"User Prompt: {prompt[:100]}...")

        try:
            if self.provider == 'openai':
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ]
                response = self.client.chat.completions.create(
                    model=model_to_use,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                generated_text = response.choices[0].message.content.strip()
                logger.info(f"OpenAI generation successful. Tokens used: {response.usage.total_tokens}")
                return generated_text
            
            elif self.provider == 'anthropic':
                # Ensure max_tokens is integer for Anthropic
                max_tokens_int = int(max_tokens)
                message = self.client.messages.create(
                     model=model_to_use,
                     system=system_prompt, # Use the dedicated system parameter
                     messages=[{"role": "user", "content": prompt}],
                     max_tokens=max_tokens_int,
                     temperature=temperature
                 )
                generated_text = message.content[0].text # Response structure is different
                # Log token usage if needed (structure might vary)
                # logger.info(f"Anthropic generation successful. Input tokens: {message.usage.input_tokens}, Output tokens: {message.usage.output_tokens}")
                logger.info(f"Anthropic generation successful.")
                return generated_text
            
            # Add elif for other providers
            else:
                logger.error(f"Generation not implemented for provider: {self.provider}")
                return f"Error: Generation not implemented for {self.provider}"
        
        except OpenAIError as e:
            logger.exception(f"Error during OpenAI generation ({model_to_use}): {e}")
            return f"Error: OpenAI API error - {e}"
        except AnthropicAPIError as e:
             logger.exception(f"Error during Anthropic generation ({model_to_use}): {e}")
             return f"Error: Anthropic API error - {e}"
        except Exception as e:
            logger.exception(f"An unexpected error occurred during LLM generation ({self.provider}, {model_to_use}): {e}")
            return f"Error: Failed to generate text - {e}"

# Example Usage
if __name__ == "__main__":
    # --- Setup Logging --- 
    # This basic setup won't read the config file unless logging_config is imported and used
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Load config from YAML
    try:
        with open('config.yaml', 'r') as f:
            app_config = yaml.safe_load(f)
    except FileNotFoundError:
        print("config.yaml not found, using default LLM config.")
        app_config = {'llm': {'provider': 'openai', 'default_model': 'gpt-3.5-turbo'}}
    except Exception as e:
        print(f"Error loading config.yaml: {e}")
        app_config = {'llm': {'provider': 'openai', 'default_model': 'gpt-3.5-turbo'}}

    # --- Check API Keys --- 
    # Check keys based on configured provider
    provider_in_config = app_config.get('llm', {}).get('provider', 'openai')
    api_key_env_var = f"{provider_in_config.upper()}_API_KEY"
    if not os.getenv(api_key_env_var):
        logger.warning(f"--- {api_key_env_var} environment variable is not set. --- \n")

    llm_interface = LLMInterface(app_config)

    if llm_interface.client:
        logger.info("--- Running LLM Generation Example --- ")
        prompt_example = "Explain the concept of agentic workflows in AI in about 50 words."
        response = llm_interface.generate(prompt_example)
        logger.info(f"\nLLM Response ({llm_interface.provider} - {llm_interface.default_model}):\n{response}")

        # Example switching provider in code (requires config setup for both)
        # if provider_in_config == 'openai':
        #      print("\n--- Attempting Anthropic call (requires ANTHROPIC_API_KEY and config) ---")
        #      app_config['llm']['provider'] = 'anthropic'
        #      anthropic_interface = LLMInterface(app_config)
        #      if anthropic_interface.client:
        #           anthropic_response = anthropic_interface.generate("What is the capital of France?")
        #           logger.info(f"\nAnthropic Response ({anthropic_interface.provider} - {anthropic_interface.default_model}):\n{anthropic_response}")
        #      else:
        #           logger.warning("Could not initialize Anthropic client for comparison.")

    else:
        logger.warning("Skipping LLM generation example as client initialization failed.") 