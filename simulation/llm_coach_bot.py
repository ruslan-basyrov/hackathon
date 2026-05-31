import json
from dataclasses import asdict

from coach import policy
from coach.llm_realize import llm_realize as realize
from signals import Signals
from simulation.json_utils import loads_lenient
from utils.llm_client import LLMClient


class LLMCoachBot:
    """
    LLM-based coach. Sees the user's Action, the derived Signals, and a brief
    persona description. Emits a single conversational intervention string.
    """
    SCHEMA_DOC = (
        "You are a helpful, human-like customer service coach for an online insurance flow.\n"
        "Your goal is to keep the user moving toward purchase, NOT to answer general questions.\n"
        "Keep your tone encouraging and brief. Start with a friendly acknowledgement.\n"
        "If the user seems stuck, offer a specific, actionable tip relevant to their current step.\n"
        "If they seem frustrated, offer to connect them with a human advisor.\n"
        "If they are moving smoothly, offer a simple, positive reinforcement.\n"
        "DO NOT ask more than one question at a time. No lists. No markdown.\n"
        "Your entire response must be a single string, no more than two sentences."
    )

    def __init__(self, model_name):
        self.llm_client = LLMClient(model=model_name)

    def get_intervention(self, funnel_step, turn_data, trigger_reason, persona_hint, signals, chat_history=None):
        """
        Generate a coach intervention message.
        """
        system_prompt = self.SCHEMA_DOC
        user_prompt = self._build_user_prompt(
            funnel_step, turn_data, trigger_reason, persona_hint, signals, chat_history
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        raw_response = self.llm_client.chat_completion(messages, json_mode=False)
        return raw_response.strip().strip('"')

    def _build_user_prompt(self, funnel_step, turn_data, trigger_reason, persona_hint, signals, chat_history):
        action = turn_data.get("action", {})
        prompt = (
            f"Context:\n"
            f"- User persona hint: {persona_hint}\n"
            f"- Funnel step: {funnel_step}\n"
            f"- Last action: {action.get('type')} (target: {action.get('target')}, dwell: {action.get('dwell_s')}s)\n"
            f"- Triggering condition: {trigger_reason}\n"
            f"- Signals: {json.dumps(asdict(signals))}\n"
        )
        if chat_history:
            prompt += f"\nConversation history:\n{json.dumps(chat_history)}\n"

        prompt += "\nYour task: Generate a single, brief, encouraging sentence to help the user."
        return prompt


class RealizeCoachBot:
    """Coach backed by coach.policy.lookup + coach.realize.realize().

    The pipeline is deterministic on the choice of intervention (per-persona/step
    table in coach.policy) and LLM-or-template on the wording (coach.realize
    dispatches on cfg["realize"]["method"], falling back to templates if the LLM
    call fails when graceful_fallback is on). Same get_intervention(...) interface
    as LLMCoachBot so the engine can swap them.

    Expected cfg shape (built by SimulationEngine when coach_mode="realize"):
        {
          "model_name": "...",
          "inference_base_url": "https://...",
          "inference_api_key": "...",
          "realize": {"method": "llm" | "template", "graceful_fallback": True, ...},
        }

    Falls back to a generic nudge when:
      * no policy entry exists for (persona, step) and the trigger isn't
        repeated_back_nav (mirroring coach.__init__.coach() behaviour);
      * realize() raises and the engine asked for an explicit non-fallback mode.
    """

    GENERIC_FALLBACK = "Need a hand? I can talk you through any part of this — just ask."

    def __init__(self, cfg: dict):
        self.cfg = cfg

    def get_intervention(
        self,
        funnel_step: str,
        turn_data: dict,
        trigger_reason: str,
        persona_hint: str,
        signals: Signals,
        chat_history: list = None,
    ) -> str:
        """Look up the intervention type in the policy table, then realize the wording."""
        # The persona_hint from the engine is the segment ID (e.g. "judith").
        # The policy table is keyed on this.
        intervention_type, _ = policy.lookup(
            persona_hint,
            signals.step
        )
        if intervention_type is None:
            return self.GENERIC_FALLBACK

        try:
            return realize(
                intervention_type,
                signals,
                persona=persona_hint,
                cfg=self.cfg,
                chat_history=chat_history,
            )
        except Exception as e:
            print(f"ERROR: realize() failed, falling back to generic. Details: {e}")
            return self.GENERIC_FALLBACK
