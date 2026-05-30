"""Persona-action labeler — the "distillation" step's judgment function.

This is the labeling source for the bulk SFT corpus (vs. the ~120 hand-crafted
seeds in `build_seeds.py`). The user picked "Hand-authored seed set +
distillation, do it yourself" — so this is Claude's judgment encoded as a
documented decision tree rather than typed out as 400 individual JSON labels.

Design choices, made explicit so the training signal is auditable:

  * Outputs are derived deterministically from (persona, step, signals,
    intervention_type) so the corpus is reproducible from the snapshot pool.

  * The branches encode the same persona rules the BUILD_SPEC §5 Phase 2
    decision table prescribes (Judith S4 dwell → back/abandon, Franz S7
    price-jump → abandon, Peter early overwhelm → handoff), plus the
    intervention-reaction policy from `coach/policy.py`. So a model trained
    on this corpus learns "see intervention text X at step S → emit action
    Y for persona P", which IS the Phase 5 contract (BUILD_SPEC §5: bots
    that react to wording).

  * Small randomness (a couple of branches sample `rng.random()`) so the
    same `(step, signals)` doesn't always map to one action — necessary so
    the LoRA doesn't memorise a single completion per state.

  * The labeler is NOT meant to replicate StubAgent — StubAgent ignores
    intervention text entirely (that's why scripted-bot uplift is parameter-
    driven per BUILD_SPEC §5 ⚠️). This labeler reacts to interventions,
    which is the whole point of Phase 5.
"""
from __future__ import annotations

import json
import random
from typing import Optional

from signals import Signals


def _act(t: str, target: Optional[str] = None, dwell_s: float = 0.0) -> str:
    return json.dumps({"type": t, "target": target, "dwell_s": dwell_s})


# ============================================================================
# Per-persona branches
# ============================================================================

def _label_judith(step: int, s: Signals, itype: Optional[str], rng: random.Random) -> str:
    dwell = max(2.0, s.dwell_current_s * 0.3 + rng.gauss(8, 3))

    # START — push through.
    if step == 0:
        return _act("continue", None, dwell)

    # S1 — pick doctor, sometimes hover first.
    if step == 1:
        if s.dwell_current_s > 30 and rng.random() < 0.3:
            return _act("hover", "Premium" if rng.random() < 0.3 else "Optimal", dwell)
        if "doctor" in (s.tariff_selected or ""):
            return _act("continue", None, dwell)
        if rng.random() < 0.7:
            return _act("select", "doctor", dwell)
        return _act("continue", None, dwell)

    # S2 — myself.
    if step == 2:
        if rng.random() < 0.7:
            return _act("select", "myself", dwell)
        return _act("continue", None, dwell)

    # S3 — comfortable with personal data.
    if step == 3:
        if s.field_change_count >= 2 and rng.random() < 0.2:
            return _act("change_field", "form", dwell)
        return _act("continue", None, dwell)

    # S4 — THE primary drop. Long dwell + advisory engagement → back/abandon
    # unless an intervention catches her.
    if step == 4:
        if itype == "price_reframe":
            # Reframe lands — high chance of continuing / selecting.
            if not s.tariff_selected:
                return _act("select", "Optimal", dwell)
            return _act("continue", None, dwell)
        if itype == "explain_advisory_alt":
            return _act("select", "Optimal", dwell)
        if itype == "callback":
            return _act("select", "advisor_callback", dwell)
        # No intervention path: severity scales with dwell + advisory engagement.
        if s.dwell_current_s >= 100:
            return _act("abandon", None, dwell)
        if s.dwell_current_s >= 60 and s.advisory_tariff_clicked:
            return _act("back", None, dwell) if rng.random() < 0.6 else _act("abandon", None, dwell)
        if s.tariff_hover_count >= 3:
            return _act("hover", "OptPlus" if rng.random() < 0.4 else "Optimal", dwell)
        if not s.tariff_selected:
            return _act("select", "Optimal", dwell) if rng.random() < 0.6 else _act("hover", "Optimal", dwell)
        return _act("continue", None, dwell)

    # S6 — answers carefully but rarely abandons here.
    if step == 6:
        if s.dwell_current_s >= 80 and rng.random() < 0.3:
            return _act("back", None, dwell)
        if s.field_change_count >= 1 and rng.random() < 0.2:
            return _act("change_field", "form", dwell)
        return _act("continue", None, dwell)

    # S7 — primary drop #2. Final price surprise.
    if step == 7:
        gap = s.price_gap_eur
        if itype == "explain_price":
            return _act("continue", None, dwell)
        if itype == "callback":
            return _act("select", "advisor_callback", dwell)
        if itype == "justify_price":
            return _act("continue", None, dwell) if rng.random() < 0.7 else _act("hover", "cancel", dwell)
        # No intervention: gap-driven.
        if gap >= 7:
            return _act("abandon", None, dwell) if rng.random() < 0.5 else _act("hover", "cancel", dwell)
        if gap >= 4:
            return _act("back", None, dwell) if rng.random() < 0.5 else _act("abandon", None, dwell)
        if gap >= 2:
            return _act("continue", None, dwell)
        return _act("continue", None, dwell)

    # S12 — close to commit, usually finishes.
    if step == 12:
        if s.dwell_current_s >= 90 and rng.random() < 0.2:
            return _act("back", None, dwell)
        if s.field_change_count >= 1 and rng.random() < 0.2:
            return _act("change_field", "form", dwell)
        return _act("continue", None, dwell)

    return _act("continue", None, dwell)


def _label_franz(step: int, s: Signals, itype: Optional[str], rng: random.Random) -> str:
    # Franz is fast — lower dwell baseline.
    dwell = max(1.0, s.dwell_current_s * 0.2 + rng.gauss(4, 2))

    if step == 0:
        return _act("continue", None, dwell)

    if step == 1:
        if rng.random() < 0.15 and s.external_tab_opens == 0:
            return _act("open_tab", "comparison", dwell)
        if rng.random() < 0.7:
            return _act("select", "doctor", dwell)
        return _act("continue", None, dwell)

    if step == 2:
        if rng.random() < 0.7:
            return _act("select", "myself", dwell)
        return _act("continue", None, dwell)

    if step == 3:
        if s.field_change_count >= 1 and rng.random() < 0.3:
            return _act("change_field", "form", dwell)
        return _act("continue", None, dwell)

    # S4 — picks Optimal; advisor wall = silent exit; callback offer = exit.
    if step == 4:
        # CRITICAL: Franz never accepts a callback. The plan + persona doc.
        if itype == "callback":
            return _act("abandon", None, dwell)
        if itype == "explain_advisory_alt":
            return _act("select", "Optimal", dwell)
        if s.advisory_tariff_clicked and not s.tariff_selected and rng.random() < 0.4:
            return _act("abandon", None, dwell)
        if rng.random() < 0.2 and s.external_tab_opens < 2:
            return _act("open_tab", "comparison", dwell)
        if not s.tariff_selected:
            return _act("select", "Optimal", dwell)
        return _act("continue", None, dwell)

    if step == 6:
        return _act("continue", None, dwell)

    # S7 — THE primary drop for Franz. Price-gap deal-breaker.
    if step == 7:
        if itype == "callback":
            return _act("abandon", None, dwell)
        if itype == "justify_price":
            # Clear data unblocks him — but not always.
            if s.price_gap_eur >= 8 and rng.random() < 0.4:
                return _act("hover", "cancel", dwell)
            return _act("continue", None, dwell)
        if itype == "explain_price":
            # Soft-explanation doesn't move him.
            return _act("hover", "cancel", dwell) if rng.random() < 0.6 else _act("abandon", None, dwell)
        # No intervention: gap-driven.
        gap = s.price_gap_eur
        if gap >= 5:
            if s.hover_cancel_count >= 1:
                return _act("abandon", None, dwell)
            return _act("hover", "cancel", dwell)
        if gap >= 3:
            if rng.random() < 0.4:
                return _act("open_tab", "comparison", dwell)
            return _act("hover", "cancel", dwell)
        return _act("continue", None, dwell)

    if step == 12:
        return _act("continue", None, dwell)

    return _act("continue", None, dwell)


def _label_peter(step: int, s: Signals, itype: Optional[str], rng: random.Random) -> str:
    # Peter is slow and uncertain — higher dwell baseline.
    dwell = max(5.0, s.dwell_current_s * 0.4 + rng.gauss(15, 5))

    # Callback is HIS conversion path — accept it whenever offered.
    if itype == "callback":
        return _act("select", "advisor_callback", dwell)

    if step == 0:
        return _act("continue", None, dwell)

    # S1-S3 = his primary drop zone. Field changes / long dwell = abandon
    # unless callback fires.
    if step == 1:
        if s.dwell_current_s >= 70 and s.field_change_count >= 2:
            return _act("abandon", None, dwell)
        if s.field_change_count >= 1 and rng.random() < 0.4:
            return _act("change_field", "form", dwell)
        if s.dwell_current_s >= 30 and rng.random() < 0.4:
            return _act("hover", "doctor" if rng.random() < 0.5 else "hospital", dwell)
        if rng.random() < 0.5:
            return _act("select", "doctor", dwell)
        return _act("continue", None, dwell)

    if step == 2:
        if s.field_change_count >= 2 and rng.random() < 0.4:
            return _act("abandon", None, dwell)
        if s.dwell_current_s >= 40 and rng.random() < 0.5:
            return _act("change_field", "form", dwell)
        if s.dwell_current_s >= 20 and rng.random() < 0.3:
            return _act("hover", "myself", dwell)
        if rng.random() < 0.5:
            return _act("select", "myself", dwell)
        return _act("continue", None, dwell)

    if step == 3:
        if s.dwell_current_s >= 80 or s.field_change_count >= 3:
            return _act("abandon", None, dwell)
        if s.field_change_count >= 1 and rng.random() < 0.5:
            return _act("change_field", "form", dwell)
        if s.dwell_current_s >= 60 and rng.random() < 0.3:
            return _act("back", None, dwell)
        return _act("continue", None, dwell)

    # S4 — overwhelm + many hovers → abandon. Otherwise indecisive hovering.
    if step == 4:
        if s.tariff_hover_count >= 4 and s.dwell_current_s >= 100:
            return _act("abandon", None, dwell)
        if s.dwell_current_s >= 130:
            return _act("abandon", None, dwell)
        if s.tariff_hover_count >= 2 and rng.random() < 0.4:
            return _act("hover", rng.choice(["Optimal", "Start", "OptPlus"]), dwell)
        if rng.random() < 0.3:
            return _act("back", None, dwell)
        if not s.tariff_selected and rng.random() < 0.4:
            return _act("select", "Start", dwell)
        return _act("hover", "Optimal", dwell)

    if step == 6:
        if s.field_change_count >= 2 and rng.random() < 0.5:
            return _act("abandon", None, dwell)
        if s.dwell_current_s >= 70 and rng.random() < 0.3:
            return _act("change_field", "form", dwell)
        return _act("continue", None, dwell)

    if step == 7:
        gap = s.price_gap_eur
        if gap >= 3:
            return _act("abandon", None, dwell) if rng.random() < 0.5 else _act("hover", "cancel", dwell)
        if gap >= 1.5 and rng.random() < 0.3:
            return _act("back", None, dwell)
        return _act("continue", None, dwell)

    if step == 12:
        if s.dwell_current_s >= 95 and rng.random() < 0.3:
            return _act("abandon", None, dwell)
        return _act("continue", None, dwell)

    return _act("continue", None, dwell)


_BRANCHES = {"judith": _label_judith, "franz": _label_franz, "peter": _label_peter}


def label(persona: str, step: int, sig: Signals, itype: Optional[str],
          rng: Optional[random.Random] = None) -> str:
    """Return a JSON Action string for this snapshot. `rng` is optional so the
    labeler can be called either reproducibly (seeded rng) or freshly (None).
    """
    rng = rng or random.Random()
    fn = _BRANCHES.get(persona)
    if fn is None:
        return _act("continue", None, 5.0)
    return fn(step, sig, itype, rng)
