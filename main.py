import argparse
import random
from simulation.engine import SimulationEngine, VALID_COACH_MODES, VALID_MODES
from bots.persona_factory import PersonaFactory


def run_simulations(
    personas_path,
    num_simulations,
    model_name,
    intervention_mode,
    coach_mode,
    gbm_cfg=None,
    realize_cfg=None
):
    print(
        f"--- Running {num_simulations} simulation(s) "
        f"[Intervention: {intervention_mode.upper()} | Coach: {coach_mode.upper()}] "
        f"using model: {model_name} ---"
    )

    engine = SimulationEngine(
        personas_path,
        model_name=model_name,
        intervention_mode=intervention_mode,
        coach_mode=coach_mode,
        gbm_cfg=gbm_cfg,
        realize_cfg=realize_cfg,
    )
    factory = PersonaFactory(personas_path)
    available_segments = factory.get_available_segments()

    for i in range(num_simulations):
        print(f"\n--- Simulation Run {i+1}/{num_simulations} ---")
        random_segment = random.choice(available_segments)
        engine.run_simulation(random_segment)


def main():
    parser = argparse.ArgumentParser(
        description="Run persona-based simulations of an insurance funnel."
    )
    parser.add_argument(
        '--generate-training-data',
        action='store_true',
        help="Run in data generation mode (forces --intervention-mode off).",
    )
    parser.add_argument(
        '--intervention-mode',
        choices=VALID_MODES,
        default='llm',  # Changed default to 'llm'
        help="Decider for whether the coach intervenes: off | rule | llm | gbm.",
    )
    parser.add_argument(
        '--coach-mode',
        choices=VALID_COACH_MODES,
        default='chat',
        help=(
            "Coach wording engine: 'chat' (LLMCoachBot, free-form chat) | "
            "'realize' (coach.policy.lookup + coach.realize.realize, template-or-LLM with fallback)."
        ),
    )
    parser.add_argument(
        '--realize-method',
        choices=('llm', 'template'),
        default='llm',
        help="Only used with --coach-mode realize. 'llm' calls coach.llm_realize; "
             "'template' uses hand-written wording.",
    )
    parser.add_argument(
        '--gbm-model-path',
        type=str,
        default='models/gbm.json',
        help="Path to the trained xgboost model (only used when --intervention-mode gbm).",
    )
    parser.add_argument(
        '--gbm-threshold',
        type=float,
        default=0.5,
        help="Probability threshold for the GBM detector.",
    )
    parser.add_argument(
        '--num-simulations',
        type=int,
        default=1,
        help="Number of simulations to run.",
    )
    parser.add_argument(
        '--model',
        type=str,
        default="deepseek-ai/DeepSeek-V4-Flash",  # "meta-llama/Meta-Llama-3.1-8B-Instruct",
        help="The name of the LLM model to use.",
    )
    args = parser.parse_args()

    personas_json_path = 'tracks/insurance-uniqa/personas.json'

    intervention_mode = 'off' if args.generate_training_data else args.intervention_mode
    gbm_cfg = None
    if intervention_mode == 'gbm':
        gbm_cfg = {
            "method": "gbm",
            "gbm_model_path": args.gbm_model_path,
            "gbm_threshold": args.gbm_threshold,
        }

    realize_cfg = None
    if args.coach_mode == 'realize':
        realize_cfg = {"realize": {"method": args.realize_method, "graceful_fallback": True}}

    run_simulations(
        personas_path=personas_json_path,
        num_simulations=args.num_simulations,
        model_name=args.model,
        intervention_mode=intervention_mode,
        coach_mode=args.coach_mode,
        gbm_cfg=gbm_cfg,
        realize_cfg=realize_cfg,
    )


if __name__ == "__main__":
    main()
