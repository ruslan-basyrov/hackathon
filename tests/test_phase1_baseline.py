"""Phase 1 acceptance test.

Gate: stub agent, no coach -> online conversion in [5.3%, 5.9%] (calibrated ~5.68%),
and zero advisor routing (Phase 1 stays on the in-scope path).

Uses N=100_000 so the deterministic estimate sits comfortably inside the band
(95% CI at the true 5.68% is ~[5.54%, 5.82%] at this N).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runner import load_config, run  # noqa: E402

CONFIG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml")


def test_phase1_baseline():
    cfg = load_config(CONFIG)
    res = run(cfg, coach_fn=None, n=100_000, write_traces=False)
    conv = res["conversion"]
    assert 0.053 <= conv <= 0.059, f"baseline conversion {conv:.4f} outside [0.053, 0.059]"
    assert res["outcomes"].get("ROUTED_ADVISOR", 0) == 0, "Phase 1 must not route to advisor"


if __name__ == "__main__":
    cfg = load_config(CONFIG)
    res = run(cfg, coach_fn=None, n=100_000, write_traces=False)
    print(f"baseline conversion: {res['conversion'] * 100:.2f}%  outcomes: {res['outcomes']}")
    test_phase1_baseline()
    print("PASS")
