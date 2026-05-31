from state_machine import Action
from utils.llm_client import LLMClient

from simulation.json_utils import loads_lenient


class LLMBot:
    """
    Persona LLM driver. Each turn it emits ONE Action (state_machine.Action)
    plus an optional `personal_data_entered` blob for data-entry steps. The
    engine appends the Action to the funnel history so signals.extract() can
    derive the feature vector used by coach/detection.py.
    """

    # The fields signals.extract reads from the Action history live in the
    # Action.type/target pair (hover/change_field/open_tab/select). The bot
    # emits exactly one Action per turn; multi-action sequences happen across
    # turns (e.g. select Optimal at S4, then continue).
    SCHEMA_DOC = (
        "Respond with a single JSON object:\n"
        " - 'type': one of the allowed action types listed below.\n"
        "    * 'cancel' means: drop out of the funnel without converting (terminal).\n"
        "    * 'purchase' (only available at S12_CLOSING) means: confirm and complete the purchase (terminal).\n"
        "    * 'continue' advances to the next step at non-S12 steps; at S12 use 'purchase' instead.\n"
        " - 'target': string or null. Required for 'select'; for 'hover' name what you hovered; "
        "for 'change_field' name the field; null otherwise.\n"
        " - 'dwell_s': number of seconds spent on the current screen BEFORE acting.\n"
        " - 'reasoning': brief, in-character explanation.\n"
        " - 'personal_data_entered': object, only on data-entry steps (S3/S12). "
        "May be empty if you didn't fill anything in.\n"
    )

    def __init__(self, persona_prompt, model_name):
        self.system_prompt = persona_prompt
        self.llm_client = LLMClient(model=model_name)
        self.history = []

    def get_next_action(self, step_name, step_description, allowed_types,
                        select_targets, hover_hints):
        user_prompt = (
            f"You are at step {step_name}: {step_description}\n"
            f"Allowed action types: {allowed_types}\n"
            f"Valid `select` targets: {select_targets}\n"
            f"Common hover targets here: {hover_hints}\n\n"
            "Decide how you behave in character. "
            + self.SCHEMA_DOC
        )
        return self._send_prompt(user_prompt)

    def react_to_coach(self, coach_message, step_name, allowed_types,
                       select_targets, hover_hints):
        user_prompt = (
            f"A customer service coach just appeared and said: '{coach_message}'\n"
            f"You are still at step {step_name}.\n"
            f"Allowed action types: {allowed_types}\n"
            f"Valid `select` targets: {select_targets}\n"
            f"Common hover targets here: {hover_hints}\n\n"
            "How does this change what you do next? "
            + self.SCHEMA_DOC
        )
        return self._send_prompt(user_prompt)

    def chat_with_coach(self, coach_message, chat_history):
        """Generates a conversational reply to the coach."""
        user_prompt = (
            "A customer service coach is talking to you.\n"
            f"Your conversation so far:\n{chat_history}\n"
            f"The coach just said: '{coach_message}'\n\n"
            "Reply naturally, in character. DO NOT emit JSON. Just your conversational reply."
        )
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        # Note: we don't append this to the main action history
        return self.llm_client.chat_completion(messages, json_mode=False)

    def _send_prompt(self, user_prompt):
        messages = [
            {"role": "system", "content": self.system_prompt},
            *self.history,
            {"role": "user", "content": user_prompt},
        ]

        raw_response = self.llm_client.chat_completion(messages)

        parsed = loads_lenient(raw_response)
        if parsed is None:
            print(f"FATAL ERROR: Failed to decode LLM response into JSON: {raw_response}")
            return None

        self.history.append({"role": "user", "content": user_prompt})
        self.history.append({"role": "assistant", "content": raw_response})
        return parsed

    @staticmethod
    def parse_action(parsed: dict) -> Action:
        """Coerce the LLM's JSON into a state_machine.Action."""
        return Action(
            type=parsed.get("type", "abandon"),
            target=parsed.get("target"),
            dwell_s=float(parsed.get("dwell_s", 0.0)),
        )