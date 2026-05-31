import json
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from bots.persona_factory import PersonaFactory
from signals import extract as extract_signals
from state_machine import Step, Action
from utils.llm_client import resolve_endpoint
from simulation.funnel import Funnel
from simulation.llm_bot import LLMBot
from simulation.llm_coach_bot import LLMCoachBot, RealizeCoachBot
from simulation.intervention_model import (
    GBMInterventionModel,
    LLMInterventionModel,
    RuleBasedInterventionModel,
)

# Project root, so config.yaml and other assets can be found.
_REPO_ROOT = Path(__file__).resolve().parents[1]

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
        personas_path=None,
        model_name="deepseek-ai/DeepSeek-V4-Flash",
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

        if personas_path is None:
            personas_path = os.path.join(_REPO_ROOT, "tracks", "insurance-uniqa", "personas.json")
        elif not os.path.isabs(personas_path):
            personas_path = os.path.join(_REPO_ROOT, personas_path)

        self.persona_factory = PersonaFactory(personas_path)
        self.model_name = model_name
        self.intervention_mode = intervention_mode
        self.coach_mode = coach_mode
        self.realize_cfg = realize_cfg
        self.output_dir = output_dir
        if not os.path.isabs(self.output_dir):
            self.output_dir = os.path.join(_REPO_ROOT, self.output_dir)
        os.makedirs(self.output_dir, exist_ok=True)

        if intervention_mode == "llm":
            self.intervention_model = LLMInterventionModel(model_name=self.model_name)
        elif intervention_mode == "rule":
            self.intervention_model = RuleBasedInterventionModel()
        elif intervention_mode == "gbm":
            if gbm_cfg and not os.path.isabs(gbm_cfg.get("gbm_model_path")):
                gbm_cfg["gbm_model_path"] = os.path.join(_REPO_ROOT, gbm_cfg["gbm_model_path"])
            cfg = gbm_cfg or {"method": "gbm", "gbm_model_path": os.path.join(_REPO_ROOT, "models/gbm.json"), "gbm_threshold": 0.5}
            self.intervention_model = GBMInterventionModel(cfg_detection=cfg)
        else:
            self.intervention_model = None

        # State for step-able simulation
        self.persona = None
        self.persona_bot = None
        self.coach_bot = None
        self.funnel = None
        self.turn = 0
        self.max_turns = 15
        self.simulation_log = []
        self.segment_id = None

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

    def start_simulation(self, segment_id, max_turns=15):
        """Initializes the simulation state for a step-able run."""
        self.segment_id = segment_id
        self.persona = self.persona_factory.create_persona(segment_id)
        self.persona_bot = LLMBot(self.persona.llm_prompt, model_name=self.model_name)
        self.coach_bot = self._make_coach_bot()
        self.funnel = Funnel()
        self.turn = 0
        self.max_turns = max_turns
        self.simulation_log = []
        print(f"--- Starting LLM Simulation for {self.persona.name} ({segment_id}) ---")
        print(f"--- Intervention Mode: {self.intervention_mode.upper()} | Coach Mode: {self.coach_mode.upper()} ---")

    def step(self):
        """Runs a single turn of the simulation."""
        if self.funnel.is_terminal() or self.turn >= self.max_turns:
            return None

        self.turn += 1
        step_name = self.funnel.current_state.name
        allowed_types = self.funnel.get_allowed_action_types()
        select_targets = self.funnel.get_select_targets()
        hover_hints = self.funnel.get_hover_hints()

        print(f"\n[Turn {self.turn}] State: {step_name}")

        parsed = self.persona_bot.get_next_action(
            step_name=step_name,
            step_description=self.funnel.describe(),
            allowed_types=allowed_types,
            select_targets=select_targets,
            hover_hints=hover_hints,
        )
        if parsed is None:
            self.funnel.current_state = Step.ABANDONED
            self._finish_simulation()
            return {"action": Action("abandon"), "state": self.funnel.current_state}

        action = LLMBot.parse_action(parsed)
        print(f"  Bot decided: type={action.type} target={action.target} dwell={action.dwell_s}s")

        personal_data = parsed.get("personal_data_entered") or {}
        if personal_data:
            self.funnel.session_data.update(personal_data)
            print(f"  Bot entered data: {personal_data}")

        self.funnel.apply(action)

        signals = extract_signals(self.funnel.current_state, self.funnel.history)
        if self.funnel.current_state == Step.S7_FINAL_PRICE:
            signals.price_gap_eur = S7_PRICE_GAP_EUR

        turn_data = {
            "turn": self.turn,
            "state": step_name,
            "next_state": self.funnel.current_state.name,
            "action": action,
            "reasoning": parsed.get("reasoning"),
            "session_data_so_far": dict(self.funnel.session_data),
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
                chat_history = []
                coach_message = self.coach_bot.get_intervention(
                    funnel_step=step_name,
                    turn_data=turn_data,
                    trigger_reason=trigger_context,
                    persona_hint=self.persona.name.lower(),
                    signals=signals,
                )
                chat_history.append({"role": "assistant", "content": coach_message})
                print(f"  [COACH SAYS] '{coach_message}'")

                # Allow for a few turns of conversation
                for _ in range(3):
                    persona_reply = self.persona_bot.chat_with_coach(coach_message, chat_history)
                    chat_history.append({"role": "user", "content": persona_reply})
                    print(f"  [PERSONA REPLIES] '{persona_reply}'")

                    coach_message = self.coach_bot.get_intervention(
                        funnel_step=step_name,
                        turn_data=turn_data,
                        trigger_reason="follow_up",
                        persona_hint=self.persona.name.lower(),
                        signals=signals,
                        chat_history=chat_history,
                    )
                    chat_history.append({"role": "assistant", "content": coach_message})
                    print(f"  [COACH SAYS] '{coach_message}'")
                    # A simple condition to break the loop if the conversation seems over
                    if "thank you" in persona_reply.lower() or "bye" in persona_reply.lower():
                        break

                print("  Persona bot is now reacting to the coach...")
                reaction_allowed = self.funnel.get_allowed_action_types()
                reaction_targets = self.funnel.get_select_targets()
                reaction_hovers = self.funnel.get_hover_hints()
                reaction_step = self.funnel.current_state.name

                reaction_parsed = self.persona_bot.react_to_coach(
                    coach_message=coach_message,
                    step_name=reaction_step,
                    allowed_types=reaction_allowed,
                    select_targets=reaction_targets,
                    hover_hints=reaction_hovers,
                )
                if reaction_parsed is None:
                    self.funnel.current_state = Step.ABANDONED
                    self._finish_simulation()
                    return {"action": Action("abandon"), "state": self.funnel.current_state}

                reaction_action = LLMBot.parse_action(reaction_parsed)
                print(f"  Bot's new decision: type={reaction_action.type} target={reaction_action.target}")
                self.funnel.apply(reaction_action)

                if self.funnel.current_state == Step.S7_FINAL_PRICE:
                    signals = extract_signals(self.funnel.current_state, self.funnel.history)
                    signals.price_gap_eur = S7_PRICE_GAP_EUR
                else:
                    signals = extract_signals(self.funnel.current_state, self.funnel.history)

                turn_data["coach_intervention"] = {
                    "trigger_context": trigger_context,
                    "coach_message": coach_message,
                    "chat_history": chat_history,
                    "bot_reaction": {
                        "action": {
                            "type": reaction_action.type,
                            "target": reaction_action.target,
                            "dwell_s": reaction_action.dwell_s,
                        },
                        "reasoning": reaction_parsed.get("reasoning"),
                        "post_state": self.funnel.current_state.name,
                        "post_signals": asdict(signals),
                    },
                }

        self.simulation_log.append(turn_data)

        if self.funnel.is_terminal():
            self._finish_simulation()

        return turn_data

    def run_simulation(self, segment_id, max_turns=15):
        self.start_simulation(segment_id, max_turns)
        while self.step() is not None:
            pass
        return self.funnel.current_state.name

    def _finish_simulation(self):
        """Saves the log file at the end of the simulation."""
        final_state = self.funnel.current_state.name
        print(f"\n--- Simulation finished. Final state: {final_state} ---")
        self._save_log(self.persona.name, self.segment_id, final_state, self.simulation_log, self.funnel.session_data)

    def _save_log(self, persona_name, segment_id, final_state, simulation_log, session_data):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{persona_name.replace(' ', '_')}_{timestamp}_{final_state}.json"
        filepath = os.path.join(self.output_dir, filename)

        # Convert Action objects in log to dicts for serialization
        log_copy = json.loads(json.dumps(simulation_log, default=lambda o: o.__dict__))

        output_data = {
            "metadata": {
                "timestamp": timestamp,
                "persona_name": persona_name,
                "segment_id": segment_id,
                "final_state": final_state,
                "total_turns": len(log_copy),
                "model_name": self.model_name,
                "intervention_mode": self.intervention_mode,
                "coach_mode": self.coach_mode,
                "final_collected_data": session_data,
            },
            "journey_log": log_copy,
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        print(f"Simulation log saved to: {filepath}")
