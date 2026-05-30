import os
from functools import lru_cache
from pathlib import Path

import yaml
from openai import OpenAI


# Resolve config.yaml relative to the repo root (utils/ -> repo root).
_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


@lru_cache(maxsize=1)
def load_config() -> dict:
    """Load config.yaml once. Returns {} if the file is missing so callers
    can still rely on env / defaults without crashing."""
    if not _CONFIG_PATH.exists():
        return {}
    with _CONFIG_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def resolve_endpoint():
    """Returns (api_key, base_url).

    Precedence:
      1. FEATHERLESS_API_KEY env  -> Featherless cloud
      2. OPENAI_API_KEY env       -> OpenAI (or OPENAI_BASE_URL override)
      3. config.yaml              -> inference_base_url + inference_api_key
                                     (this is the Leonardo / local-vLLM path)

    Exposed so other modules (e.g. simulation.engine building a coach.realize
    cfg) can target the same endpoint without duplicating the lookup logic.
    """
    api_key = os.environ.get("FEATHERLESS_API_KEY")
    if api_key:
        return api_key, "https://api.featherless.ai/v1"

    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        return api_key, os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

    cfg = load_config()
    base_url = cfg.get("inference_base_url")
    if base_url:
        # Most local vLLM servers ignore the key but the OpenAI client requires
        # *something* non-empty.
        return cfg.get("inference_api_key") or "local", base_url

    return None, "https://api.openai.com/v1"


def resolve_model(model: str | None = None) -> str:
    """Pick the model name. Explicit arg wins, then config.yaml's model_name,
    then a sensible cloud fallback."""
    if model:
        return model
    cfg = load_config()
    return cfg.get("model_name") or "deepseek-ai/DeepSeek-V4-Flash"


class LLMClient:
    """Wrapper for the LLM API calls."""
    def __init__(self, model: str | None = None):
        api_key, base_url = resolve_endpoint()

        # Promoted to instance attributes so callers (e.g. the engine assembling
        # a coach.realize cfg) can read the same endpoint values back out.
        self.api_key = api_key
        self.base_url = base_url
        self.model = resolve_model(model)

        # If API key isn't set, we mock the response for testing purposes without an API key
        self.mock_mode = not api_key

        if not self.mock_mode:
            self.client = OpenAI(api_key=api_key, base_url=base_url)

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
