import json
import os

from coach.detection import detect
from utils.llm_client import LLMClient

from simulation.json_utils import loads_lenient


class LLMInterventionModel:
    """
    LLM-based decider for whether the coach should intervene.
    Sees the current state name, the bot's Action, and a flattened Signals dict.
    """
    def __init__(self, model_name):
        self.llm_client = LLMClient(model=model_name)
        self.history = []
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self):
        prompt = (
            "You are an AI orchestrator observing a user navigating a health insurance funnel.\n"
            "Your job is to decide whether a human-like customer service coach should intervene.\n"
            "Below is the context of the three main customer segments you need to identify:\n\n"
        )

        base_dir = os.path.join(os.path.dirname(__file__), '..', 'tracks', 'insurance-uniqa')
        files = [
            'persona_judith_segment_1.md',
            'persona_franz_segment_2.md',
            'persona_peter_segment_3.md',
        ]

        for file in files:
            filepath = os.path.join(base_dir, file)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    prompt += f"--- {file} ---\n{f.read()}\n\n"
            except FileNotFoundError:
                prompt += f"--- {file} ---\n(File not found. Rely on general segment knowledge: 1=Hybrids, 2=Online Affine, 3=Service Affine)\n\n"

        prompt += (
            "At each turn, you will receive the user's current step (e.g. S4_INITIAL_PRICE), "
            "the structured action they just took (type/target/dwell_s), the running Signals "
            "(dwell totals, back-nav counts, tariff hovers, hover_cancel_count, price_gap_eur, ...), "
            "and any collected personal data.\n"
            "Keep track of their behavior over time. Intervene if they show signs of drop-off, hesitation, or overwhelm.\n"
            "Your response MUST be a single JSON object with the following keys:\n"
            " - 'trigger': (boolean) true if the coach should intervene, false otherwise.\n"
            " - 'strategy': (string) If trigger is true, describe the guessed personality and the intervention strategy. If false, output 'None'."
        )
        return prompt

    def should_trigger(self, turn_data, signals=None):
        # signals is unused here — kept for interface parity with GBMInterventionModel.
        user_prompt = (
            f"Turn Data:\n{json.dumps(turn_data, indent=2, default=str)}\n\n"
            "Based on the history and this new turn data, should the coach intervene now? Respond with JSON."
        )

        messages = [
            {"role": "system", "content": self.system_prompt},
            *self.history,
            {"role": "user", "content": user_prompt},
        ]

        raw_response = self.llm_client.chat_completion(messages)

        parsed_response = loads_lenient(raw_response)
        if parsed_response is None:
            print(f"ERROR: Intervention LLM failed to return JSON: {raw_response}")
            return False, "Failed to parse."

        trigger = parsed_response.get("trigger", False)
        strategy = parsed_response.get("strategy", "No strategy provided.")

        self.history.append({"role": "user", "content": user_prompt})
        self.history.append({"role": "assistant", "content": raw_response})

        return trigger, strategy


class RuleBasedInterventionModel:
    """
    Simple rule-based decider, rewritten for the state_machine step names.
    Reads from the Signals when available (richer than the raw Action).
    """
    def should_trigger(self, turn_data, signals=None):
        state = turn_data.get("state")

        if signals is not None:
            if state == "S4_INITIAL_PRICE" and signals.dwell_current_s > 30:
                return (True, "High dwell at the price table — likely 'Online Affine' comparing options.")
            if state == "S7_FINAL_PRICE" and signals.hover_cancel_count >= 1:
                return (True, "Hover on cancel at the final price — possible 'Service Affine' feeling overwhelmed.")
            if signals.back_nav_count >= 3:
                return (True, "Repeated back-nav — generic friction, may need help.")
            return (False, "No trigger condition met.")

        # Fallback if signals weren't provided (shouldn't happen with current engine).
        action = turn_data.get("action", {})
        dwell = action.get("dwell_s", 0)
        if state == "S4_INITIAL_PRICE" and dwell > 30:
            return (True, "High dwell at the price table (fallback path).")
        return (False, "No trigger condition met.")


class GBMInterventionModel:
    """
    Plug-and-play GBM (or threshold) detector from coach/detection.py.
    Same `should_trigger` signature as the other two so SimulationEngine can swap them.

    cfg_detection example (gbm):
        {"method": "gbm", "gbm_model_path": "models/gbm.json", "gbm_threshold": 0.5}
    cfg_detection example (threshold):
        {"method": "threshold", "price_gap_threshold": 10.0, "dwell_threshold_s": 30.0,
         "overwhelm_changes": 3, "early_overwhelm_max_steps": 3, "back_nav_threshold": 3}
    """
    def __init__(self, cfg_detection: dict):
        self.cfg = cfg_detection

    def should_trigger(self, turn_data, signals=None):
        if signals is None:
            return False, "no_signals"
        fire, reason = detect(signals, self.cfg)
        return bool(fire), reason
