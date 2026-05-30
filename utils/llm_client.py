import os
from openai import OpenAI

class LLMClient:
    """Wrapper for the LLM API calls."""
    def __init__(self, model="deepseek-ai/DeepSeek-V4-Pro"):
        # We check for FEATHERLESS_API_KEY first as that was the default in your project
        api_key = os.environ.get("FEATHERLESS_API_KEY")
        base_url = "https://api.featherless.ai/v1"
        
        # Fallback to OPENAI_API_KEY if featherless is not set
        if not api_key:
            api_key = os.environ.get("OPENAI_API_KEY")
            base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        
        # If API key isn't set, we mock the response for testing purposes without an API key
        self.mock_mode = not api_key
        
        if not self.mock_mode:
            self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def chat_completion(self, messages):
        """Sends a request to the LLM and returns the response content."""
        if self.mock_mode:
            # Fallback for testing if no API key is provided
            print("WARNING: LLMClient running in MOCK mode. Returning hardcoded JSON. Please set FEATHERLESS_API_KEY environment variable.")
            return '{"action": "PROCEED", "dwell_time_seconds": 15, "reasoning": "Mock reasoning"}'

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format={"type": "json_object"} # Force JSON output
        )
        return response.choices[0].message.content
