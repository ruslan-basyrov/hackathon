"""Phase 2 acceptance test (paired counterfactual).

Gate (BUILD_SPEC §5 Phase 2):
  * For each persona, success WITH coach > success WITHOUT, on identical seeds,
    scored by that persona's conversion definition.
  * Every persona reports a wasted_rate (the cost of intervening) in [0, 1].
  * The Franz fix holds: most of his interventions are NOT wasted (his S4 over-firing
    is gone), so his wasted_rate is well under half.

NOTE: Phase 1-3 uplift is parameter-driven (it validates plumbing + measurement, not
real coaching efficacy). Efficacy becomes real in Phase 4-5, when LLM persona bots
actually react to the wording. See BUILD_SPEC §4.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runner import compare, load_config  # noqa: E402

CONFIG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml")
N = 20_000


def test_phase2_uplift():
    cfg = load_config(CONFIG)
    for persona in ("judith", "franz", "peter"):
        r = compare(cfg, persona, n=N)
        assert r["uplift"] > 0, (persona, r["success_without"], r["success_with"])
        assert r["wasted_rate"] is not None and 0.0 <= r["wasted_rate"] <= 1.0, (persona, r["wasted_rate"])

    # The Franz fix: coaching is no longer dominated by unnecessary S4 nudges.
    franz = compare(cfg, "franz", n=N)
    assert franz["wasted_rate"] < 0.40, franz["wasted_rate"]


if __name__ == "__main__":
    cfg = load_config(CONFIG)
    for p in ("judith", "franz", "peter"):
        r = compare(cfg, p, n=N)
        f = lambda x: f"{x * 100:.1f}%" if x is not None else "n/a"
        print(f"{p:8s} success {f(r['success_without'])} -> {f(r['success_with'])}  "
              f"(uplift {r['uplift'] * 100:+.1f}pp)  fired {f(r['fired_rate'])}  "
              f"wasted {f(r['wasted_rate'])}  saved {f(r['saved_rate'])}")
    test_phase2_uplift()
    print("PASS")
