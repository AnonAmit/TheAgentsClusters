# browser_agent.py
import asyncio
from agent_template import Agent
from llm_interface import LLMInterface
from memory import MemorySystem

# Import Playwright
try:
    from playwright.async_api import async_playwright, Playwright, Browser, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("Warning: Playwright library not found. BrowserAgent functionality will be limited.")
    print("Please run `pip install playwright` and `playwright install`")
    # Define dummy types for type hinting if playwright is not installed
    Playwright, Browser, Page = type(None), type(None), type(None)

class BrowserAgent(Agent):
    def __init__(self, agent_id: str, master_controller, llm_interface: LLMInterface, memory_system: MemorySystem, config: dict):
        super().__init__(agent_id, master_controller, llm_interface, memory_system, config)
        self.browser_config = config.get('browser', {})
        self.playwright_config = self.browser_config.get('playwright', {})
        self.headless = self.browser_config.get('headless', True)
        self.browser_type = self.playwright_config.get('browser_type', 'chromium')
        self.user_agent = self.playwright_config.get('user_agent')

        self.playwright: Playwright | None = None
        self.browser: Browser | None = None
        self.page: Page | None = None

        print(f"BrowserAgent {self.agent_id} initialized. Playwright available: {PLAYWRIGHT_AVAILABLE}")
        # Initialize browser lazily or explicitly via a setup method

    async def _ensure_browser_page(self) -> Page | None:
        """Initializes Playwright, Browser, and Page if they don't exist."""
        if not PLAYWRIGHT_AVAILABLE:
             print("Error: Playwright is not installed. Cannot perform browser actions.")
             return None

        if self.page and not self.page.is_closed():
            return self.page

        try:
            if not self.playwright:
                print(f"Agent {self.agent_id}: Initializing Playwright...")
                self.playwright = await async_playwright().start()

            if not self.browser or not self.browser.is_connected():
                print(f"Agent {self.agent_id}: Launching browser ({self.browser_type})...")
                browser_launcher = getattr(self.playwright, self.browser_type)
                launch_options = {'headless': self.headless}
                # Add other Playwright options from config if needed
                self.browser = await browser_launcher.launch(**launch_options)

            if not self.page or self.page.is_closed():
                print(f"Agent {self.agent_id}: Opening new page...")
                context_options = {}
                if self.user_agent:
                    context_options['user_agent'] = self.user_agent
                browser_context = await self.browser.new_context(**context_options)
                self.page = await browser_context.new_page()
            
            return self.page

        except Exception as e:
            print(f"Error initializing browser components for Agent {self.agent_id}: {e}")
            await self.shutdown_browser() # Attempt cleanup
            return None

    async def process_task(self, task_details):
        """Overrides the base Agent method to handle browser-specific tasks."""
        print(f"BrowserAgent {self.agent_id} received task: {task_details}")
        url = task_details.get('url')
        action = task_details.get('action', 'get_content') # Default action
        selector = task_details.get('selector') # Optional CSS selector
        task_prompt = task_details.get('prompt') # Optional prompt for LLM interaction

        if not url:
            return "Error: Missing 'url' in task details for BrowserAgent."
        if not PLAYWRIGHT_AVAILABLE:
             return "Error: Playwright is not installed. Cannot execute browser task."

        page = await self._ensure_browser_page()
        if not page:
            return "Error: Failed to initialize browser page."

        result = None
        try:
            print(f"Agent {self.agent_id}: Navigating to {url}...")
            await page.goto(url, wait_until='domcontentloaded', timeout=60000) # Increased timeout
            print(f"Agent {self.agent_id}: Navigation successful.")

            if action == 'get_content':
                print(f"Agent {self.agent_id}: Getting page content...")
                content = await page.content()
                result = content
                # Option: Use LLM to summarize or extract specific info from content
                if task_prompt and self.llm and self.llm.client:
                     llm_prompt = f"Extract the key information related to '{task_prompt}' from the following HTML content:\n\n{content[:3000]}..."
                     summary = await asyncio.to_thread(self.llm.generate, llm_prompt, max_tokens=500)
                     result = summary # Return the LLM-processed result instead
                     print(f"Agent {self.agent_id}: LLM processed content based on prompt.")
                else:
                     # Truncate result if too long for simple reporting
                     result = result[:5000] + "... (truncated)" if len(result) > 5000 else result
            
            elif action == 'scrape_text':
                target_locator = page.locator(selector) if selector else page.locator('body')
                print(f"Agent {self.agent_id}: Scraping text content (selector: {selector or 'body'})...")
                text_content = await target_locator.text_content()
                result = text_content.strip()
                result = result[:5000] + "... (truncated)" if len(result) > 5000 else result
            
            elif action == 'click':
                if not selector:
                     return "Error: Missing 'selector' for click action."
                print(f"Agent {self.agent_id}: Clicking element: {selector}")
                await page.locator(selector).click()
                # Maybe wait for navigation or return success status?
                await page.wait_for_load_state('domcontentloaded', timeout=30000)
                result = f"Clicked element '{selector}' on {url}. Current URL: {page.url}"
            
            # Add more actions: fill, screenshot, etc.
            elif action == 'screenshot':
                filename = task_details.get('filename', f'{self.agent_id}_screenshot.png')
                print(f"Agent {self.agent_id}: Taking screenshot ({filename})...")
                await page.screenshot(path=filename)
                result = f"Screenshot saved to {filename}"

            else:
                result = f"Error: Unknown browser action '{action}'."
        
        except Exception as e:
            print(f"Error during browser action '{action}' for Agent {self.agent_id} on {url}: {e}")
            # Capture screenshot on error maybe?
            try:
                 error_path = f'{self.agent_id}_error.png'
                 await page.screenshot(path=error_path)
                 print(f"Saved screenshot on error to {error_path}")
            except Exception as screenshot_e:
                 print(f"Could not save screenshot on error: {screenshot_e}")
            result = f"Error performing action '{action}' on {url}: {e}"
        
        # Don't close the browser/page here, keep it open for potential next task
        # await self.shutdown_browser() # Call this explicitly when agent is done

        return result

    async def shutdown_browser(self):
        """Closes the browser and Playwright instance gracefully."""
        print(f"Agent {self.agent_id}: Shutting down browser components...")
        if self.page and not self.page.is_closed():
            await self.page.close()
            self.page = None
        if self.browser and self.browser.is_connected():
            await self.browser.close()
            self.browser = None
        if self.playwright:
             try:
                 await self.playwright.stop()
             except Exception as e:
                  print(f"Error stopping playwright: {e}") # Might happen if already stopped
             self.playwright = None
        print(f"Agent {self.agent_id}: Browser shutdown complete.")

    # Override stop method to ensure browser cleanup
    def stop(self):
        super().stop()
        # Since stop isn't async, we might need a separate async cleanup or run sync
        # For simplicity now, we rely on explicit shutdown or program exit
        # A better approach might be to trigger async shutdown from master
        print(f"BrowserAgent {self.agent_id} stop called. Remember to call async shutdown_browser if needed.")

    # Ensure browser is shut down when the agent is deleted (best effort)
    def __del__(self):
         # This is synchronous, so calling async shutdown directly is problematic.
         # Rely on explicit shutdown call from the master or managing code.
         if self.browser and self.browser.is_connected():
              print(f"Warning: BrowserAgent {self.agent_id} deleted without explicit browser shutdown.")

    # Override spawn_sub_agents if needed, or use default
    # Override report_back if specific formatting needed 