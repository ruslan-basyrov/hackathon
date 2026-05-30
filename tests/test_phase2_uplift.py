"""Phase 2 acceptance test.

Gate (BUILD_SPEC §5 Phase 2):
  * For each persona, success WITH coach > success WITHOUT, on identical seeds,
    scored by that persona's conversion definition.
  * Stay-coached personas (Judith, Franz) report a numeric annoyance rate.
    Peter is all-handoff, so his annoyance is legitimately None.

NOTE: Phase 1-3 uplift is parameter-driven (it validates the plumbing + measurement,
not real coaching efficacy). Efficacy only becomes real in Phase 4-5, when LLM persona
bots actually react to the wording. See BUILD_SPEC §4.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from coach import coach  # noqa: E402
from runner import load_config, run  # noqa: E402

CONFIG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml")
N = 20_000


def _pair(cfg, persona):
    base = run(cfg, coach_fn=None, persona=persona, n=N)
    coached = run(cfg, coach_fn=coach, persona=persona, n=N)
    return base, coached


def test_phase2_uplift():
    cfg = load_config(CONFIG)
    for persona in ("judith", "franz", "peter"):
        base, coached = _pair(cfg, persona)
        assert coached["success"] > base["success"], (
            persona, base["success"], coached["success"]
        )

    # Stay-coached personas must report a numeric annoyance rate.
    for persona in ("judith", "franz"):
        _, coached = _pair(cfg, persona)
        assert coached["annoyance_rate"] is not None, persona
        assert 0.0 <= coached["annoyance_rate"] <= 1.0, (persona, coached["annoyance_rate"])


if __name__ == "__main__":
    cfg = load_config(CONFIG)
    for p in ("judith", "franz", "peter"):
        b, c = _pair(cfg, p)
        ann = f"{c['annoyance_rate'] * 100:.1f}%" if c["annoyance_rate"] is not None else "n/a"
        print(f"{p:8s} success {b['success'] * 100:5.1f}% -> {c['success'] * 100:5.1f}%  "
              f"(uplift {(c['success'] - b['success']) * 100:+.1f}pp)  annoyance {ann}")
    test_phase2_uplift()
    print("PASS")
