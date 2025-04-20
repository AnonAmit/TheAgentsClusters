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

# Import Google Gemini if available
try:
    import google.generativeai as genai
    from google.api_core import exceptions as GoogleAPIErrors
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    genai = None # Define for type hinting
    GoogleAPIErrors = None

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
        
        elif self.provider == 'google':
            if not GOOGLE_AVAILABLE:
                 logger.error("Google provider configured, but library not installed. Run `pip install google-generativeai`")
                 return
            try:
                 genai.configure(api_key=api_key)
                 # Create a dummy model instance to check API key validity (optional but good practice)
                 # model_check = genai.GenerativeModel(self.default_model or 'gemini-pro')
                 # model_check.generate_content("test", generation_config=genai.types.GenerationConfig(max_output_tokens=1))
                 # The client is implicitly configured via genai.configure
                 self.client = genai # Store the module itself as client for consistency
                 logger.info(f"Google Gemini client configured. Default model: {self.default_model}")
            except GoogleAPIErrors.PermissionDenied as e:
                 logger.exception(f"Permission denied initializing Google Gemini (check API key permissions): {e}")
                 self.client = None
            except Exception as e:
                 logger.exception(f"An unexpected error occurred during Google Gemini configuration: {e}")
                 self.client = None
        
        # Add elif blocks for other providers
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
            
            elif self.provider == 'google':
                 if not self.client: # Check if genai was configured
                      return "Error: Google Gemini client not configured."
                 
                 gemini_model = self.client.GenerativeModel(
                     model_name=model_to_use,
                     system_instruction=system_prompt # Use system instruction if model supports it
                 )
                 # Configure generation parameters
                 generation_config = self.client.types.GenerationConfig(
                     max_output_tokens=int(max_tokens),
                     temperature=temperature
                 )
                 # Handle safety settings if needed (optional)
                 # safety_settings = [...]

                 response = gemini_model.generate_content(
                     prompt,
                     generation_config=generation_config,
                     # safety_settings=safety_settings
                 )
                 
                 # Handle potential blocks/errors in response
                 if not response.candidates:
                      block_reason = response.prompt_feedback.block_reason if response.prompt_feedback else 'Unknown'
                      safety_ratings = response.prompt_feedback.safety_ratings if response.prompt_feedback else []
                      logger.error(f"Google Gemini generation blocked. Reason: {block_reason}, Safety Ratings: {safety_ratings}")
                      return f"Error: Google Gemini generation blocked (Reason: {block_reason})"
                 
                 # Accessing generated text might vary slightly based on response structure
                 try:
                      generated_text = response.text
                 except ValueError as e:
                     # Sometimes response.text raises error if function calls or other non-text parts exist
                     logger.warning(f"Could not directly get response.text from Gemini, checking parts: {e}")
                     generated_text = "".join(part.text for part in response.candidates[0].content.parts)
                     if not generated_text:
                          logger.error(f"Gemini response blocked or empty. Response: {response}")
                          return "Error: Gemini response blocked or empty."

                 logger.info(f"Google Gemini generation successful.")
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
        except GoogleAPIErrors.GoogleAPIError as e:
             logger.exception(f"Error during Google Gemini generation ({model_to_use}): {e}")
             return f"Error: Google API error - {e}"
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
    provider_in_config = app_config.get('llm', {}).get('provider', 'openai')
    api_key_env_var = f"{provider_in_config.upper()}_API_KEY"
    if not os.getenv(api_key_env_var):
        logger.warning(f"--- {api_key_env_var} environment variable is not set. LLM operations for {provider_in_config} may fail. --- \n")

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