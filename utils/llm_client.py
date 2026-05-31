import os
from openai import OpenAI


def resolve_endpoint():
    """Returns (api_key, base_url) using env vars. Featherless first, then OpenAI.
    Exposed so other modules (e.g. simulation.engine building a coach.realize cfg)
    can target the same endpoint without duplicating the lookup logic."""
    api_key = os.environ.get("FEATHERLESS_API_KEY")
    base_url = "https://api.featherless.ai/v1"
    if not api_key:
        api_key = os.environ.get("OPENAI_API_KEY")
        base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    return api_key, base_url


class LLMClient:
    """Wrapper for the LLM API calls."""
    def __init__(self, model="deepseek-ai/DeepSeek-V4-Pro"):
        api_key, base_url = resolve_endpoint()

        # Promoted to instance attributes so callers (e.g. the engine assembling
        # a coach.realize cfg) can read the same endpoint values back out.
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

        # If API key isn't set, we mock the response for testing purposes without an API key
        self.mock_mode = not api_key

        if not self.mock_mode:
            self.client = OpenAI(api_key=api_key, base_url=base_url)

    def chat_completion(self, messages, json_mode=True):
        """Sends a request to the LLM and returns the response content."""
        if self.mock_mode:
            # Fallback for testing if no API key is provided
            print("WARNING: LLMClient running in MOCK mode. Returning hardcoded JSON. "
                  "Please set FEATHERLESS_API_KEY environment variable.")
            if json_mode:
                return '{"action": "PROCEED", "dwell_time_seconds": 15, "reasoning": "Mock reasoning"}'
            return "This is a mock response."

        response_format = {"type": "json_object"} if json_mode else None
        
        # When response_format is None, the kwarg shouldn't be passed at all to older OpenAI client versions,
        # but modern ones handle None fine. To be safe, we conditionally pass it.
        kwargs = {
            "model": self.model,
            "messages": messages,
        }
        if response_format:
            kwargs["response_format"] = response_format

        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content
