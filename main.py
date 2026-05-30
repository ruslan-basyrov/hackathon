import argparse
import random
from simulation.engine import SimulationEngine, VALID_MODES
from bots.persona_factory import PersonaFactory


def run_simulations(personas_path, num_simulations, model_name, intervention_mode, gbm_cfg=None):
    print(f"--- Running {num_simulations} simulation(s) [Intervention Mode: {intervention_mode.upper()}] using model: {model_name} ---")

    engine = SimulationEngine(
        personas_path,
        model_name=model_name,
        intervention_mode=intervention_mode,
        gbm_cfg=gbm_cfg,
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
        default='llm',
        help="Decider for whether the coach intervenes: off | rule | llm | gbm.",
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
        default="deepseek-ai/DeepSeek-V4-Flash",#"meta-llama/Meta-Llama-3.1-8B-Instruct",
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

    run_simulations(
        personas_path=personas_json_path,
        num_simulations=args.num_simulations,
        model_name=args.model,
        intervention_mode=intervention_mode,
        gbm_cfg=gbm_cfg,
    )


if __name__ == "__main__":
    main()
