import json
import os
from dataclasses import asdict
from datetime import datetime

from bots.persona_factory import PersonaFactory
from signals import extract as extract_signals
from state_machine import Step
from utils.llm_client import resolve_endpoint
from simulation.funnel import Funnel
from simulation.llm_bot import LLMBot
from simulation.llm_coach_bot import LLMCoachBot, RealizeCoachBot
from simulation.intervention_model import (
    GBMInterventionModel,
    LLMInterventionModel,
    RuleBasedInterventionModel,
)


# Fixed default price gap injected when the persona reaches S7 — mirrors the
# "final price is ~15% higher than the estimate" assumption documented in
# bots/persona.py. Kept as a single constant so it's easy to make persona- or
# segment-specific later.
S7_PRICE_GAP_EUR = 15.0


VALID_MODES = ("off", "rule", "llm", "gbm")
VALID_COACH_MODES = ("chat", "realize")


class SimulationEngine:
    """
    Orchestrates the simulation against the state_machine + signals contracts.

    Trigger decider — `intervention_mode`:
      * "off"  - no coach
      * "rule" - RuleBasedInterventionModel
      * "llm"  - LLMInterventionModel
      * "gbm"  - GBMInterventionModel (wraps coach.detection.detect)

    Wording engine — `coach_mode` (only used when a coach is on):
      * "chat"    - LLMCoachBot (free-form chat, JSON-output LLMClient)
      * "realize" - RealizeCoachBot (coach.policy.lookup + coach.realize.realize,
                    template-or-LLM with graceful fallback)
    """
    def __init__(
        self,
        personas_path,
        model_name,
        intervention_mode="rule",
        coach_mode="chat",
        gbm_cfg=None,
        realize_cfg=None,
        output_dir="outputs",
    ):
        if intervention_mode not in VALID_MODES:
            raise ValueError(f"intervention_mode must be one of {VALID_MODES}, got {intervention_mode!r}")
        if coach_mode not in VALID_COACH_MODES:
            raise ValueError(f"coach_mode must be one of {VALID_COACH_MODES}, got {coach_mode!r}")

        self.persona_factory = PersonaFactory(personas_path)
        self.model_name = model_name
        self.intervention_mode = intervention_mode
        self.coach_mode = coach_mode
        self.realize_cfg = realize_cfg
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

        if intervention_mode == "llm":
            self.intervention_model = LLMInterventionModel(model_name=self.model_name)
        elif intervention_mode == "rule":
            self.intervention_model = RuleBasedInterventionModel()
        elif intervention_mode == "gbm":
            cfg = gbm_cfg or {"method": "gbm", "gbm_model_path": "models/gbm.json", "gbm_threshold": 0.5}
            self.intervention_model = GBMInterventionModel(cfg_detection=cfg)
        else:
            self.intervention_model = None

    def _build_realize_cfg(self) -> dict:
        """Build a cfg dict for coach.realize.realize() that targets the same
        endpoint LLMClient picks up from env vars. Caller-supplied realize_cfg
        keys take precedence."""
        api_key, base_url = resolve_endpoint()
        cfg = {
            "model_name": self.model_name,
            "inference_base_url": base_url,
            "inference_api_key": api_key or "local",
            "realize": {"method": "llm", "graceful_fallback": True},
        }
        if self.realize_cfg:
            # Shallow merge top-level, deep merge "realize" subdict.
            user_realize = self.realize_cfg.get("realize") or {}
            cfg.update({k: v for k, v in self.realize_cfg.items() if k != "realize"})
            cfg["realize"] = {**cfg["realize"], **user_realize}
        return cfg

    def _make_coach_bot(self):
        if self.intervention_mode == "off":
            return None
        if self.coach_mode == "realize":
            return RealizeCoachBot(cfg=self._build_realize_cfg())
        return LLMCoachBot(model_name=self.model_name)

    def run_simulation(self, segment_id, max_turns=15):
        persona = self.persona_factory.create_persona(segment_id)
        persona_bot = LLMBot(persona.llm_prompt, model_name=self.model_name)

        coach_bot = self._make_coach_bot()

        funnel = Funnel()

        print(f"--- Starting LLM Simulation for {persona.name} ({segment_id}) ---")
        print(f"--- Intervention Mode: {self.intervention_mode.upper()} | Coach Mode: {self.coach_mode.upper()} ---")

        simulation_log = []
        turn = 0

        while not funnel.is_terminal() and turn < max_turns:
            turn += 1
            step_name = funnel.current_state.name
            allowed_types = funnel.get_allowed_action_types()
            select_targets = funnel.get_select_targets()
            hover_hints = funnel.get_hover_hints()

            print(f"\n[Turn {turn}] State: {step_name}")

            parsed = persona_bot.get_next_action(
                step_name=step_name,
                step_description=funnel.describe(),
                allowed_types=allowed_types,
                select_targets=select_targets,
                hover_hints=hover_hints,
            )
            if parsed is None:
                funnel.current_state = Step.ABANDONED
                break

            action = LLMBot.parse_action(parsed)
            print(f"  Bot decided: type={action.type} target={action.target} dwell={action.dwell_s}s")

            personal_data = parsed.get("personal_data_entered") or {}
            if personal_data:
                funnel.session_data.update(personal_data)
                print(f"  Bot entered data: {personal_data}")

            # Apply the action -> advances funnel state and appends to history.
            funnel.apply(action)

            # Now compute signals over the (state, history) the coach detector expects.
            signals = extract_signals(funnel.current_state, funnel.history)
            if funnel.current_state == Step.S7_FINAL_PRICE:
                signals.price_gap_eur = S7_PRICE_GAP_EUR

            turn_data = {
                "turn": turn,
                "state": step_name,                       # state BEFORE the action
                "next_state": funnel.current_state.name,  # state AFTER the action
                "action": {"type": action.type, "target": action.target, "dwell_s": action.dwell_s},
                "reasoning": parsed.get("reasoning"),
                "session_data_so_far": dict(funnel.session_data),
                "signals": asdict(signals),
                "intervention_model_decision": None,
                "coach_intervention": None,
            }

            if self.intervention_model is not None:
                trigger, trigger_context = self.intervention_model.should_trigger(turn_data, signals=signals)
                decision = {"trigger": trigger, "strategy": trigger_context}
                turn_data["intervention_model_decision"] = decision
                print(f"  [Intervention Model] Decided: {decision}")

                if trigger:
                    print(f"  [COACH TRIGGERED] Strategy: {trigger_context}")
                    coach_message = coach_bot.get_intervention(
                        funnel_step=step_name,
                        turn_data=turn_data,
                        trigger_reason=trigger_context,
                        persona_hint=persona.name.lower(),
                        signals=signals,
                    )
                    print(f"  [COACH SAYS] '{coach_message}'")

                    print("  Persona bot is now reacting to the coach...")
                    # Recompute the action menu for the (possibly already-advanced) current state.
                    reaction_allowed = funnel.get_allowed_action_types()
                    reaction_targets = funnel.get_select_targets()
                    reaction_hovers = funnel.get_hover_hints()
                    reaction_step = funnel.current_state.name

                    reaction_parsed = persona_bot.react_to_coach(
                        coach_message=coach_message,
                        step_name=reaction_step,
                        allowed_types=reaction_allowed,
                        select_targets=reaction_targets,
                        hover_hints=reaction_hovers,
                    )
                    if reaction_parsed is None:
                        funnel.current_state = Step.ABANDONED
                        break

                    reaction_action = LLMBot.parse_action(reaction_parsed)
                    print(f"  Bot's new decision: type={reaction_action.type} target={reaction_action.target}")
                    funnel.apply(reaction_action)

                    if funnel.current_state == Step.S7_FINAL_PRICE:
                        signals = extract_signals(funnel.current_state, funnel.history)
                        signals.price_gap_eur = S7_PRICE_GAP_EUR
                    else:
                        signals = extract_signals(funnel.current_state, funnel.history)

                    turn_data["coach_intervention"] = {
                        "trigger_context": trigger_context,
                        "coach_message": coach_message,
                        "bot_reaction": {
                            "action": {
                                "type": reaction_action.type,
                                "target": reaction_action.target,
                                "dwell_s": reaction_action.dwell_s,
                            },
                            "reasoning": reaction_parsed.get("reasoning"),
                            "post_state": funnel.current_state.name,
                            "post_signals": asdict(signals),
                        },
                    }

            simulation_log.append(turn_data)

        final_state = funnel.current_state.name
        print(f"\n--- Simulation finished. Final state: {final_state} ---")
        self._save_log(persona.name, segment_id, final_state, simulation_log, funnel.session_data)
        return final_state

    def _save_log(self, persona_name, segment_id, final_state, simulation_log, session_data):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{persona_name.replace(' ', '_')}_{timestamp}_{final_state}.json"
        filepath = os.path.join(self.output_dir, filename)

        output_data = {
            "metadata": {
                "timestamp": timestamp,
                "persona_name": persona_name,
                "segment_id": segment_id,
                "final_state": final_state,
                "total_turns": len(simulation_log),
                "model_name": self.model_name,
                "intervention_mode": self.intervention_mode,
                "coach_mode": self.coach_mode,
                "final_collected_data": session_data,
            },
            "journey_log": simulation_log,
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        print(f"Simulation log saved to: {filepath}")
