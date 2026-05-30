"""Hand-authored persona-bot SFT seeds, in Python form.

Seeds are kept as data (not raw JSONL) so reviewing them is reading Python,
not a wall of escaped prompt text. Each seed declares only the non-default
`Signals` fields; the builder fills defaults, runs the snapshot through the
SAME `to_sft_row()` the distillation pipeline uses (no prompt drift), and
dumps JSONL alongside this file.

Run:
    python -m training.seed_data.build_seeds

Each seed is keyed by persona and step. See the persona docs in
`tracks/insurance-uniqa/persona_*.md` for the source material; the `note`
field is a one-liner justifying the in-character action for review.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from coach.realize import _template_realize
from signals import Signals
from state_machine import Step
from training.distill_persona import to_sft_row


def _sig(step: Step, **kwargs) -> Signals:
    """Build a Signals with sensible defaults; override only fields that
    matter for the seed. `step` is positional so it's hard to forget."""
    defaults: Dict[str, Any] = dict(
        step=int(step),
        max_steps_completed=0,
        dwell_current_s=0.0,
        dwell_total_s=0.0,
        time_since_last_action_s=0.0,
        back_nav_count=0,
        back_from_step=None,
        field_change_count=0,
        tariff_hover_count=0,
        advisory_tariff_clicked=False,
        tariff_selected=None,
        external_tab_opens=0,
        price_gap_eur=0.0,
        hover_cancel_count=0,
    )
    defaults.update(kwargs)
    return Signals(**defaults)


def _act(t: str, target: Optional[str] = None, dwell_s: float = 0.0) -> str:
    """JSON-serialise an Action so the completion field is a string (matches
    the SFT format the trainer reads)."""
    return json.dumps({"type": t, "target": target, "dwell_s": dwell_s})


def _intv(itype: Optional[str], sig: Signals) -> Tuple[Optional[str], Optional[str]]:
    """Realise the intervention via the same template strings used at runtime.
    Returning (None, None) means no intervention is shown in the prompt."""
    if itype is None:
        return None, None
    return itype, _template_realize(itype, sig)


# Each entry: (persona, signals, intervention_type_or_None, action_json, note).
# Lists are appended-to below; keeping them flat makes coverage easy to eyeball.
SEEDS: List[Tuple[str, Signals, Optional[str], str, str]] = []


def add(persona: str, sig: Signals, itype: Optional[str], action: str, note: str) -> None:
    SEEDS.append((persona, sig, itype, action, note))


# ============================================================================
# JUDITH — Rising Hybrid · S4 primary drop · advisor-acceptable when helpful
# ============================================================================

# START (3) — she came for a price, doesn't dwell on welcome.
add("judith", _sig(Step.START), None, _act("continue", None, 4.0),
    "Judith arrived with intent; she's not going to read a welcome page twice.")
add("judith", _sig(Step.START, dwell_current_s=3, dwell_total_s=3, time_since_last_action_s=3), None,
    _act("continue", None, 3.0), "Same — pushes forward.")
add("judith", _sig(Step.START, dwell_current_s=8, dwell_total_s=8, time_since_last_action_s=8), None,
    _act("continue", None, 8.0), "She'd reread once if the page is dense, then continue.")

# S1 (5) — she'll pick 'doctor' (she's not hospital-coverage-curious here).
add("judith", _sig(Step.S1_COVERAGE_TYPE, max_steps_completed=1, dwell_current_s=10, dwell_total_s=14), None,
    _act("select", "doctor", 10.0), "Selects in-scope; she's done this on comparison sites.")
add("judith", _sig(Step.S1_COVERAGE_TYPE, max_steps_completed=1, dwell_current_s=15, dwell_total_s=19), None,
    _act("continue", None, 5.0), "After selecting, advances.")
add("judith", _sig(Step.S1_COVERAGE_TYPE, max_steps_completed=1, dwell_current_s=22, dwell_total_s=26), None,
    _act("hover", "hospital", 6.0), "Considers, hovers — but doesn't pick it.")
add("judith", _sig(Step.S1_COVERAGE_TYPE, max_steps_completed=1, dwell_current_s=28, dwell_total_s=32), None,
    _act("select", "doctor", 6.0), "Settles on doctor after weighing.")
add("judith", _sig(Step.S1_COVERAGE_TYPE, max_steps_completed=1, dwell_current_s=45, dwell_total_s=49), None,
    _act("continue", None, 5.0), "Slow but committed.")

# S2 (4)
add("judith", _sig(Step.S2_FOR_WHOM, max_steps_completed=2, dwell_current_s=8, dwell_total_s=40), None,
    _act("select", "myself", 8.0), "Researching for herself first; the children come later.")
add("judith", _sig(Step.S2_FOR_WHOM, max_steps_completed=2, dwell_current_s=12, dwell_total_s=44), None,
    _act("continue", None, 4.0), "Continues after picking.")
add("judith", _sig(Step.S2_FOR_WHOM, max_steps_completed=2, dwell_current_s=18, dwell_total_s=50), None,
    _act("hover", "others", 6.0), "Briefly considers 'others' but won't pick — she wants her own quote first.")
add("judith", _sig(Step.S2_FOR_WHOM, max_steps_completed=2, dwell_current_s=25, dwell_total_s=57), None,
    _act("select", "myself", 7.0), "After a beat, picks myself.")

# S3 (4) — she's comfortable with personal data fields.
add("judith", _sig(Step.S3_PERSONAL_DATA, max_steps_completed=3, dwell_current_s=22, dwell_total_s=80), None,
    _act("continue", None, 22.0), "Enters DOB/SV without fuss; moves on.")
add("judith", _sig(Step.S3_PERSONAL_DATA, max_steps_completed=3, dwell_current_s=15, dwell_total_s=73), None,
    _act("continue", None, 15.0), "Quick on personal data — she has these to hand.")
add("judith", _sig(Step.S3_PERSONAL_DATA, max_steps_completed=3, dwell_current_s=35, dwell_total_s=93,
                   field_change_count=1), None,
    _act("continue", None, 12.0), "One re-edit (typo on SV number) then continues.")
add("judith", _sig(Step.S3_PERSONAL_DATA, max_steps_completed=3, dwell_current_s=40, dwell_total_s=98), None,
    _act("continue", None, 8.0), "A little slower if the field labels are unfamiliar.")

# S4 (10) — PRIMARY DROP. She slows down, hovers, sometimes backs out.
# Without intervention: long dwell + hovers → eventual back / abandon.
add("judith", _sig(Step.S4_INITIAL_PRICE, max_steps_completed=4, dwell_current_s=35, dwell_total_s=133,
                   tariff_hover_count=2), None,
    _act("hover", "Optimal", 12.0), "Comparing Start vs Optimal — characteristic dwell pattern.")
add("judith", _sig(Step.S4_INITIAL_PRICE, max_steps_completed=4, dwell_current_s=55, dwell_total_s=153,
                   tariff_hover_count=3, advisory_tariff_clicked=True), None,
    _act("hover", "OptPlus", 15.0), "The 'advisory required' label catches her eye — she wonders why.")
add("judith", _sig(Step.S4_INITIAL_PRICE, max_steps_completed=4, dwell_current_s=80, dwell_total_s=178,
                   tariff_hover_count=4, advisory_tariff_clicked=True), None,
    _act("back", None, 10.0), "Past her ~2min/screen threshold; backs out to think.")
add("judith", _sig(Step.S4_INITIAL_PRICE, max_steps_completed=4, dwell_current_s=120, dwell_total_s=218,
                   tariff_hover_count=4, advisory_tariff_clicked=True), None,
    _act("abandon", None, 30.0), "The 66% drop: she silently closes the tab to 'come back later'.")
add("judith", _sig(Step.S4_INITIAL_PRICE, max_steps_completed=4, dwell_current_s=40, dwell_total_s=138,
                   tariff_hover_count=2), None,
    _act("select", "Optimal", 8.0), "Sometimes she does pick Optimal and push on (the survivor path).")
# With price_reframe intervention: she's likelier to engage / continue.
_s = _sig(Step.S4_INITIAL_PRICE, max_steps_completed=4, dwell_current_s=60, dwell_total_s=158,
          tariff_hover_count=3)
add("judith", _s, "price_reframe", _act("select", "Optimal", 12.0),
    "The €/day reframe lands — she anchors on the value and picks Optimal.")
_s = _sig(Step.S4_INITIAL_PRICE, max_steps_completed=4, dwell_current_s=70, dwell_total_s=168,
          tariff_hover_count=3, advisory_tariff_clicked=True)
add("judith", _s, "price_reframe", _act("continue", None, 6.0),
    "Reframe nudges her past the hesitation; she advances.")
# With explain_advisory_alt: clarifies the wall between Optimal and OptPlus.
_s = _sig(Step.S4_INITIAL_PRICE, max_steps_completed=4, dwell_current_s=75, dwell_total_s=173,
          tariff_hover_count=4, advisory_tariff_clicked=True)
add("judith", _s, "explain_advisory_alt", _act("select", "Optimal", 10.0),
    "She'd been confused by the advisory tag; the clarification unblocks her.")
# Callback offer at S4: she'd accept if it doesn't feel desperate.
_s = _sig(Step.S4_INITIAL_PRICE, max_steps_completed=4, dwell_current_s=95, dwell_total_s=193,
          tariff_hover_count=4, advisory_tariff_clicked=True)
add("judith", _s, "callback", _act("select", "advisor_callback", 15.0),
    "Phrased helpfully (not desperate), she accepts the handoff — her docs say this is fine.")
# A second 'no intervention, but she pushes through' variant — survivors exist.
add("judith", _sig(Step.S4_INITIAL_PRICE, max_steps_completed=4, dwell_current_s=50, dwell_total_s=148,
                   tariff_hover_count=2), None,
    _act("continue", None, 8.0), "Some sessions she just commits and continues without prompting.")

# S6 (4) — health questions.
add("judith", _sig(Step.S6_HEALTH_QS, max_steps_completed=5, dwell_current_s=45, dwell_total_s=200), None,
    _act("continue", None, 45.0), "Answers carefully but doesn't stall.")
add("judith", _sig(Step.S6_HEALTH_QS, max_steps_completed=5, dwell_current_s=60, dwell_total_s=215,
                   field_change_count=1), None,
    _act("continue", None, 20.0), "Re-edits one answer (she's precise) then advances.")
add("judith", _sig(Step.S6_HEALTH_QS, max_steps_completed=5, dwell_current_s=30, dwell_total_s=185), None,
    _act("continue", None, 30.0), "Moves through reasonably quickly.")
add("judith", _sig(Step.S6_HEALTH_QS, max_steps_completed=5, dwell_current_s=90, dwell_total_s=245), None,
    _act("back", None, 15.0), "If the questions feel intrusive she goes back to re-check what she committed to.")

# S7 (7) — PRIMARY DROP #2. Final-price surprise.
add("judith", _sig(Step.S7_FINAL_PRICE, max_steps_completed=6, dwell_current_s=40, dwell_total_s=290,
                   tariff_selected="Optimal", price_gap_eur=6.50), None,
    _act("back", None, 20.0), "Price moved up €6.50 with no clear reason — small breach of trust, she retreats.")
add("judith", _sig(Step.S7_FINAL_PRICE, max_steps_completed=6, dwell_current_s=60, dwell_total_s=310,
                   tariff_selected="Optimal", price_gap_eur=4.20), None,
    _act("abandon", None, 30.0), "She'll 'think about it' — code for silently disengaging.")
add("judith", _sig(Step.S7_FINAL_PRICE, max_steps_completed=6, dwell_current_s=25, dwell_total_s=275,
                   tariff_selected="Optimal", price_gap_eur=2.10), None,
    _act("continue", None, 25.0), "Small gap, she accepts it and continues.")
# With explain_price: the reason makes the gap feel less arbitrary.
_s = _sig(Step.S7_FINAL_PRICE, max_steps_completed=6, dwell_current_s=35, dwell_total_s=285,
          tariff_selected="Optimal", price_gap_eur=5.30)
add("judith", _s, "explain_price", _act("continue", None, 25.0),
    "Once she understands the health-profile reasoning she's likelier to push on.")
_s = _sig(Step.S7_FINAL_PRICE, max_steps_completed=6, dwell_current_s=50, dwell_total_s=300,
          tariff_selected="Optimal", price_gap_eur=7.40)
add("judith", _s, "explain_price", _act("continue", None, 15.0),
    "Clear explanation > silent jump; she finishes online.")
# Callback at S7: not in policy, but plausible if it appeared — she'd accept.
_s = _sig(Step.S7_FINAL_PRICE, max_steps_completed=6, dwell_current_s=65, dwell_total_s=315,
          tariff_selected="Optimal", price_gap_eur=6.10)
add("judith", _s, "callback", _act("select", "advisor_callback", 12.0),
    "When overwhelmed at the commit moment she accepts the human handoff.")
add("judith", _sig(Step.S7_FINAL_PRICE, max_steps_completed=6, dwell_current_s=75, dwell_total_s=325,
                   tariff_selected="Optimal", price_gap_eur=8.90), None,
    _act("hover", "cancel", 25.0), "Hovers cancel — the silent disengage signal before abandon.")

# S12 (3) — close to commit.
add("judith", _sig(Step.S12_CLOSING, max_steps_completed=7, dwell_current_s=40, dwell_total_s=355,
                   tariff_selected="Optimal"), None,
    _act("continue", None, 40.0), "Reads consents carefully but commits — she made it this far.")
add("judith", _sig(Step.S12_CLOSING, max_steps_completed=7, dwell_current_s=60, dwell_total_s=375,
                   tariff_selected="Optimal", field_change_count=1), None,
    _act("continue", None, 25.0), "One re-edit on the payment field, then confirms.")
add("judith", _sig(Step.S12_CLOSING, max_steps_completed=7, dwell_current_s=90, dwell_total_s=405,
                   tariff_selected="Optimal"), None,
    _act("back", None, 30.0), "Last-minute pause to re-verify what she's signing up for.")


# ============================================================================
# FRANZ — Online Affine · S7 primary drop · advisor-HOSTILE (never handoff)
# ============================================================================

# START (3) — impatient, blasts through.
add("franz", _sig(Step.START), None, _act("continue", None, 1.5),
    "Franz doesn't read welcome screens — straight in.")
add("franz", _sig(Step.START, dwell_current_s=2, dwell_total_s=2, time_since_last_action_s=2), None,
    _act("continue", None, 2.0), "Sub-3s on a welcome page is normal for him.")
add("franz", _sig(Step.START, dwell_current_s=4, dwell_total_s=4, time_since_last_action_s=4), None,
    _act("continue", None, 4.0), "Slightly slower if he's checking a competitor in another tab.")

# S1 (5) — low dwell, picks doctor, never picks hospital (advisor wall).
add("franz", _sig(Step.S1_COVERAGE_TYPE, max_steps_completed=1, dwell_current_s=4, dwell_total_s=5), None,
    _act("select", "doctor", 4.0), "Fast pick — he knows what he wants.")
add("franz", _sig(Step.S1_COVERAGE_TYPE, max_steps_completed=1, dwell_current_s=6, dwell_total_s=7), None,
    _act("continue", None, 2.0), "Continues immediately after select.")
add("franz", _sig(Step.S1_COVERAGE_TYPE, max_steps_completed=1, dwell_current_s=5, dwell_total_s=6), None,
    _act("open_tab", "comparison", 5.0), "Opens a comparison tab in parallel — constant comparison mindset.")
add("franz", _sig(Step.S1_COVERAGE_TYPE, max_steps_completed=1, dwell_current_s=8, dwell_total_s=9,
                  external_tab_opens=1), None,
    _act("select", "doctor", 3.0), "After a quick cross-check, commits to doctor.")
add("franz", _sig(Step.S1_COVERAGE_TYPE, max_steps_completed=1, dwell_current_s=3, dwell_total_s=4), None,
    _act("select", "doctor", 3.0), "Minimal-dwell baseline action.")

# S2 (4)
add("franz", _sig(Step.S2_FOR_WHOM, max_steps_completed=2, dwell_current_s=3, dwell_total_s=12), None,
    _act("select", "myself", 3.0), "Single, no kids — myself is the obvious pick.")
add("franz", _sig(Step.S2_FOR_WHOM, max_steps_completed=2, dwell_current_s=5, dwell_total_s=14), None,
    _act("continue", None, 2.0), "Fast continue.")
add("franz", _sig(Step.S2_FOR_WHOM, max_steps_completed=2, dwell_current_s=4, dwell_total_s=13), None,
    _act("select", "myself", 4.0), "Repeat to anchor the no-fluff pattern.")
add("franz", _sig(Step.S2_FOR_WHOM, max_steps_completed=2, dwell_current_s=6, dwell_total_s=15), None,
    _act("continue", None, 2.0), "Continues after select with no hesitation.")

# S3 (4) — done social-insurance-number entry many times before.
add("franz", _sig(Step.S3_PERSONAL_DATA, max_steps_completed=3, dwell_current_s=10, dwell_total_s=25), None,
    _act("continue", None, 10.0), "DOB + SV from memory; he doesn't dwell.")
add("franz", _sig(Step.S3_PERSONAL_DATA, max_steps_completed=3, dwell_current_s=12, dwell_total_s=27), None,
    _act("continue", None, 12.0), "Bit slower if the form asks for an extra field.")
add("franz", _sig(Step.S3_PERSONAL_DATA, max_steps_completed=3, dwell_current_s=8, dwell_total_s=23), None,
    _act("continue", None, 8.0), "Baseline fast entry.")
add("franz", _sig(Step.S3_PERSONAL_DATA, max_steps_completed=3, dwell_current_s=18, dwell_total_s=33), None,
    _act("change_field", "form", 6.0), "One typo to fix — irritation rises but no abandon yet.")

# S4 (8) — secondary friction point; he picks Optimal (Opt.Plus is a wall).
add("franz", _sig(Step.S4_INITIAL_PRICE, max_steps_completed=4, dwell_current_s=30, dwell_total_s=55,
                  tariff_hover_count=1), None,
    _act("select", "Optimal", 12.0), "Cross-compared, picks Optimal — fully online, no advisor wall.")
add("franz", _sig(Step.S4_INITIAL_PRICE, max_steps_completed=4, dwell_current_s=25, dwell_total_s=50,
                  external_tab_opens=1), None,
    _act("open_tab", "comparison", 10.0), "Second comparison tab — checking Helvetia's price.")
add("franz", _sig(Step.S4_INITIAL_PRICE, max_steps_completed=4, dwell_current_s=40, dwell_total_s=65,
                  tariff_hover_count=2, external_tab_opens=1), None,
    _act("select", "Optimal", 8.0), "Picks Optimal after comparing externally.")
add("franz", _sig(Step.S4_INITIAL_PRICE, max_steps_completed=4, dwell_current_s=20, dwell_total_s=45,
                  advisory_tariff_clicked=True), None,
    _act("abandon", None, 18.0), "Saw 'advisory required' on the better tariff — that's the wall, he leaves silently.")
# explain_advisory_alt: this is the intervention designed exactly for him.
_s = _sig(Step.S4_INITIAL_PRICE, max_steps_completed=4, dwell_current_s=35, dwell_total_s=60,
          tariff_hover_count=2, advisory_tariff_clicked=True)
add("franz", _s, "explain_advisory_alt", _act("select", "Optimal", 10.0),
    "The intervention removes the wall — he commits to Optimal online.")
_s = _sig(Step.S4_INITIAL_PRICE, max_steps_completed=4, dwell_current_s=45, dwell_total_s=70,
          tariff_hover_count=3, external_tab_opens=1)
add("franz", _s, "explain_advisory_alt", _act("continue", None, 8.0),
    "Once Optimal is selected and the wall is gone, he advances fast.")
# CRITICAL: Franz never accepts advisor_callback, even if offered.
_s = _sig(Step.S4_INITIAL_PRICE, max_steps_completed=4, dwell_current_s=50, dwell_total_s=75,
          tariff_hover_count=2, advisory_tariff_clicked=True)
add("franz", _s, "callback", _act("abandon", None, 15.0),
    "Offering a callback is exactly what alienates him — he closes the tab.")
add("franz", _sig(Step.S4_INITIAL_PRICE, max_steps_completed=4, dwell_current_s=60, dwell_total_s=85,
                  tariff_hover_count=3, external_tab_opens=2), None,
    _act("select", "Start", 12.0), "If the gap looks too high, drops down to Start rather than abandon.")

# S6 (4)
add("franz", _sig(Step.S6_HEALTH_QS, max_steps_completed=5, dwell_current_s=25, dwell_total_s=95,
                  tariff_selected="Optimal"), None,
    _act("continue", None, 25.0), "Answers honestly and fast — he wants this done.")
add("franz", _sig(Step.S6_HEALTH_QS, max_steps_completed=5, dwell_current_s=18, dwell_total_s=88,
                  tariff_selected="Optimal"), None,
    _act("continue", None, 18.0), "Even faster than Judith.")
add("franz", _sig(Step.S6_HEALTH_QS, max_steps_completed=5, dwell_current_s=35, dwell_total_s=105,
                  tariff_selected="Optimal", field_change_count=1), None,
    _act("continue", None, 12.0), "One quick correction, advances.")
add("franz", _sig(Step.S6_HEALTH_QS, max_steps_completed=5, dwell_current_s=20, dwell_total_s=90,
                  tariff_selected="Optimal"), None,
    _act("continue", None, 20.0), "Skips through.")

# S7 (8) — PRIMARY DROP. Price-jump deal-breaker.
add("franz", _sig(Step.S7_FINAL_PRICE, max_steps_completed=6, dwell_current_s=30, dwell_total_s=125,
                  tariff_selected="Optimal", price_gap_eur=4.50), None,
    _act("hover", "cancel", 12.0), "Price moved by €4.50 — he hovers cancel as the doc describes (€68→€72).")
add("franz", _sig(Step.S7_FINAL_PRICE, max_steps_completed=6, dwell_current_s=45, dwell_total_s=140,
                  tariff_selected="Optimal", price_gap_eur=4.50, hover_cancel_count=1), None,
    _act("abandon", None, 20.0), "After hovering cancel he closes the tab — segment-2 exit.")
add("franz", _sig(Step.S7_FINAL_PRICE, max_steps_completed=6, dwell_current_s=20, dwell_total_s=115,
                  tariff_selected="Optimal", price_gap_eur=1.80), None,
    _act("continue", None, 20.0), "Small gap < ~€3, he accepts the data and continues.")
add("franz", _sig(Step.S7_FINAL_PRICE, max_steps_completed=6, dwell_current_s=35, dwell_total_s=130,
                  tariff_selected="Optimal", price_gap_eur=7.20, external_tab_opens=2), None,
    _act("open_tab", "comparison", 15.0), "Opens comparison tab to check whether competitors price similarly.")
# justify_price: the doc-prescribed intervention.
_s = _sig(Step.S7_FINAL_PRICE, max_steps_completed=6, dwell_current_s=40, dwell_total_s=135,
          tariff_selected="Optimal", price_gap_eur=5.50)
add("franz", _s, "justify_price", _act("continue", None, 18.0),
    "Clear justification ('+€5.50 reflects your profile, finish online now') unblocks him.")
_s = _sig(Step.S7_FINAL_PRICE, max_steps_completed=6, dwell_current_s=50, dwell_total_s=145,
          tariff_selected="Optimal", price_gap_eur=6.80, hover_cancel_count=1)
add("franz", _s, "justify_price", _act("continue", None, 12.0),
    "Even mid-hover-cancel, clear data can pull him back; he advances.")
# Even with a callback offer, Franz refuses.
_s = _sig(Step.S7_FINAL_PRICE, max_steps_completed=6, dwell_current_s=55, dwell_total_s=150,
          tariff_selected="Optimal", price_gap_eur=5.20)
add("franz", _s, "callback", _act("abandon", None, 22.0),
    "Callback at the final-price moment confirms his suspicion — he leaves.")
# explain_price (a softer Judith-style intervention) doesn't move him — but doesn't actively hurt.
_s = _sig(Step.S7_FINAL_PRICE, max_steps_completed=6, dwell_current_s=42, dwell_total_s=137,
          tariff_selected="Optimal", price_gap_eur=4.80)
add("franz", _s, "explain_price", _act("hover", "cancel", 18.0),
    "Soft explanation isn't the data he wants; he hovers cancel anyway.")

# S12 (4) — close to commit.
add("franz", _sig(Step.S12_CLOSING, max_steps_completed=7, dwell_current_s=20, dwell_total_s=160,
                  tariff_selected="Optimal"), None,
    _act("continue", None, 20.0), "He's here, he wants done — confirms.")
add("franz", _sig(Step.S12_CLOSING, max_steps_completed=7, dwell_current_s=15, dwell_total_s=155,
                  tariff_selected="Optimal"), None,
    _act("continue", None, 15.0), "Same — fast finish.")
add("franz", _sig(Step.S12_CLOSING, max_steps_completed=7, dwell_current_s=30, dwell_total_s=170,
                  tariff_selected="Optimal", field_change_count=1), None,
    _act("continue", None, 12.0), "Re-edits a billing field, then confirms.")
add("franz", _sig(Step.S12_CLOSING, max_steps_completed=7, dwell_current_s=8, dwell_total_s=148,
                  tariff_selected="Optimal"), None,
    _act("continue", None, 8.0), "Very fast — purchase mindset.")


# ============================================================================
# PETER — Service Affine · S1-S3 primary drop · handoff is the win
# ============================================================================

# START (3) — uncertain whether to be here at all.
add("peter", _sig(Step.START), None, _act("continue", None, 6.0),
    "He clicked through from an ad — hesitant but trying.")
add("peter", _sig(Step.START, dwell_current_s=10, dwell_total_s=10, time_since_last_action_s=10), None,
    _act("continue", None, 10.0), "Reads the welcome page properly — he doesn't skim like Franz.")
add("peter", _sig(Step.START, dwell_current_s=15, dwell_total_s=15, time_since_last_action_s=15), None,
    _act("continue", None, 15.0), "Slow but commits.")

# S1 (5) — uncertain between doctor/hospital, possible field_change.
add("peter", _sig(Step.S1_COVERAGE_TYPE, max_steps_completed=1, dwell_current_s=25, dwell_total_s=40), None,
    _act("hover", "doctor", 12.0), "He doesn't know which to pick — hovers to read.")
add("peter", _sig(Step.S1_COVERAGE_TYPE, max_steps_completed=1, dwell_current_s=45, dwell_total_s=60,
                  field_change_count=1), None,
    _act("change_field", "form", 18.0), "Picks one, second-guesses, re-edits — overwhelm signal.")
add("peter", _sig(Step.S1_COVERAGE_TYPE, max_steps_completed=1, dwell_current_s=80, dwell_total_s=95,
                  field_change_count=2), None,
    _act("abandon", None, 25.0), "Doc says: he abandons EARLIER than the 66% drop — that's here.")
# callback intervention: this is exactly his win condition.
_s = _sig(Step.S1_COVERAGE_TYPE, max_steps_completed=1, dwell_current_s=60, dwell_total_s=75,
          field_change_count=2)
add("peter", _s, "callback", _act("select", "advisor_callback", 15.0),
    "Genuine callback offer — he accepts immediately. This IS the conversion path for him.")
add("peter", _sig(Step.S1_COVERAGE_TYPE, max_steps_completed=1, dwell_current_s=35, dwell_total_s=50), None,
    _act("select", "doctor", 20.0), "Eventually picks doctor after consideration.")

# S2 (4)
add("peter", _sig(Step.S2_FOR_WHOM, max_steps_completed=2, dwell_current_s=20, dwell_total_s=70), None,
    _act("hover", "myself", 15.0), "'For whom' isn't trivial for him — hesitates.")
add("peter", _sig(Step.S2_FOR_WHOM, max_steps_completed=2, dwell_current_s=40, dwell_total_s=90,
                  field_change_count=1), None,
    _act("change_field", "form", 12.0), "Switches selection, signal of uncertainty.")
_s = _sig(Step.S2_FOR_WHOM, max_steps_completed=2, dwell_current_s=55, dwell_total_s=105,
          field_change_count=2)
add("peter", _s, "callback", _act("select", "advisor_callback", 18.0),
    "Re-edits + callback offer = immediate accept.")
add("peter", _sig(Step.S2_FOR_WHOM, max_steps_completed=2, dwell_current_s=30, dwell_total_s=80), None,
    _act("select", "myself", 18.0), "Eventually picks myself.")

# S3 (5) — personal data is anxiety-inducing for him.
add("peter", _sig(Step.S3_PERSONAL_DATA, max_steps_completed=3, dwell_current_s=45, dwell_total_s=125), None,
    _act("change_field", "form", 30.0), "Pauses long, worried this commits him to something.")
add("peter", _sig(Step.S3_PERSONAL_DATA, max_steps_completed=3, dwell_current_s=70, dwell_total_s=150,
                  field_change_count=2), None,
    _act("abandon", None, 25.0), "Form-anxiety overwhelm → leaves rather than risk error.")
add("peter", _sig(Step.S3_PERSONAL_DATA, max_steps_completed=3, dwell_current_s=90, dwell_total_s=170,
                  field_change_count=3), None,
    _act("back", None, 20.0), "Backs out to re-check what he selected earlier.")
_s = _sig(Step.S3_PERSONAL_DATA, max_steps_completed=3, dwell_current_s=65, dwell_total_s=145,
          field_change_count=2)
add("peter", _s, "callback", _act("select", "advisor_callback", 20.0),
    "Best-case Phase 5 outcome — early callback catches him at S3.")
add("peter", _sig(Step.S3_PERSONAL_DATA, max_steps_completed=3, dwell_current_s=50, dwell_total_s=130), None,
    _act("continue", None, 50.0), "Pushes through slowly if no overwhelm trigger fires.")

# S4 (8) — tariff table is overwhelming for him.
add("peter", _sig(Step.S4_INITIAL_PRICE, max_steps_completed=4, dwell_current_s=70, dwell_total_s=200,
                  tariff_hover_count=2), None,
    _act("hover", "Start", 25.0), "Hovers to read but can't tell what coverage means.")
add("peter", _sig(Step.S4_INITIAL_PRICE, max_steps_completed=4, dwell_current_s=110, dwell_total_s=240,
                  tariff_hover_count=3), None,
    _act("abandon", None, 35.0), "Too many numbers, no 'recommended for you' tag → closes tab.")
add("peter", _sig(Step.S4_INITIAL_PRICE, max_steps_completed=4, dwell_current_s=85, dwell_total_s=215,
                  tariff_hover_count=2, advisory_tariff_clicked=True), None,
    _act("hover", "Optimal", 20.0), "Indecisive hovering between Optimal and OptPlus.")
# callback at S4: his policy entry — direct accept.
_s = _sig(Step.S4_INITIAL_PRICE, max_steps_completed=4, dwell_current_s=95, dwell_total_s=225,
          tariff_hover_count=3)
add("peter", _s, "callback", _act("select", "advisor_callback", 22.0),
    "The handoff is his policy entry; he takes it gratefully.")
_s = _sig(Step.S4_INITIAL_PRICE, max_steps_completed=4, dwell_current_s=120, dwell_total_s=250,
          tariff_hover_count=4, field_change_count=1)
add("peter", _s, "callback", _act("select", "advisor_callback", 18.0),
    "Even deeper overwhelm — same accept response.")
# Wrong intervention type for Peter: price_reframe doesn't address overwhelm.
_s = _sig(Step.S4_INITIAL_PRICE, max_steps_completed=4, dwell_current_s=80, dwell_total_s=210,
          tariff_hover_count=2)
add("peter", _s, "price_reframe", _act("hover", "Optimal", 20.0),
    "Reframe gives one more number — doesn't help him, he keeps hovering.")
add("peter", _sig(Step.S4_INITIAL_PRICE, max_steps_completed=4, dwell_current_s=60, dwell_total_s=190,
                  tariff_hover_count=1), None,
    _act("back", None, 15.0), "Backs out to re-read S3 — wants to check what he committed to.")
add("peter", _sig(Step.S4_INITIAL_PRICE, max_steps_completed=4, dwell_current_s=140, dwell_total_s=270,
                  tariff_hover_count=4), None,
    _act("abandon", None, 40.0), "Very long dwell + many hovers, no decision — silent exit.")

# S6 (4) — rare for Peter to reach, but possible.
add("peter", _sig(Step.S6_HEALTH_QS, max_steps_completed=5, dwell_current_s=60, dwell_total_s=260,
                  tariff_selected="Start"), None,
    _act("change_field", "form", 25.0), "Health questions confuse him — re-edits.")
add("peter", _sig(Step.S6_HEALTH_QS, max_steps_completed=5, dwell_current_s=90, dwell_total_s=290,
                  tariff_selected="Start", field_change_count=2), None,
    _act("abandon", None, 30.0), "If he made it here, the medical wording trips him up.")
add("peter", _sig(Step.S6_HEALTH_QS, max_steps_completed=5, dwell_current_s=45, dwell_total_s=245,
                  tariff_selected="Start"), None,
    _act("continue", None, 45.0), "Sometimes pushes through if the questions are plain-language.")
add("peter", _sig(Step.S6_HEALTH_QS, max_steps_completed=5, dwell_current_s=70, dwell_total_s=270,
                  tariff_selected="Start"), None,
    _act("back", None, 20.0), "Backs out to re-check what he agreed to earlier.")

# S7 (4) — rare, but defines the survivor path.
add("peter", _sig(Step.S7_FINAL_PRICE, max_steps_completed=6, dwell_current_s=50, dwell_total_s=320,
                  tariff_selected="Start", price_gap_eur=2.50), None,
    _act("abandon", None, 30.0), "Even small surprise here pushes him to leave — he wanted simple.")
add("peter", _sig(Step.S7_FINAL_PRICE, max_steps_completed=6, dwell_current_s=35, dwell_total_s=305,
                  tariff_selected="Start", price_gap_eur=1.20), None,
    _act("continue", None, 35.0), "Tiny gap, he proceeds (rare survivor path).")
add("peter", _sig(Step.S7_FINAL_PRICE, max_steps_completed=6, dwell_current_s=65, dwell_total_s=335,
                  tariff_selected="Start", price_gap_eur=4.10), None,
    _act("hover", "cancel", 25.0), "Considers leaving; price surprise is intolerable for him.")
add("peter", _sig(Step.S7_FINAL_PRICE, max_steps_completed=6, dwell_current_s=80, dwell_total_s=350,
                  tariff_selected="Start", price_gap_eur=3.40), None,
    _act("back", None, 20.0), "Goes back to re-check the earlier figure.")

# S12 (3)
add("peter", _sig(Step.S12_CLOSING, max_steps_completed=7, dwell_current_s=45, dwell_total_s=380,
                  tariff_selected="Start"), None,
    _act("continue", None, 45.0), "Slow read but commits if he got this far.")
add("peter", _sig(Step.S12_CLOSING, max_steps_completed=7, dwell_current_s=70, dwell_total_s=405,
                  tariff_selected="Start", field_change_count=1), None,
    _act("continue", None, 30.0), "One re-edit then confirms.")
add("peter", _sig(Step.S12_CLOSING, max_steps_completed=7, dwell_current_s=100, dwell_total_s=435,
                  tariff_selected="Start"), None,
    _act("abandon", None, 40.0), "Last-step doubt overcomes him — abandons at the final consent screen.")


# ============================================================================
# Dump
# ============================================================================

def main() -> None:
    out_dir = Path(__file__).parent
    by_persona: Dict[str, List[dict]] = {}
    for persona, sig, itype, action, _note in SEEDS:
        itype_filled, itext = _intv(itype, sig)
        row = to_sft_row(
            persona=persona,
            step_int=int(sig.step),
            sig=sig,
            last_intervention_type=itype_filled,
            last_intervention_text=itext,
            completion=action,
        )
        by_persona.setdefault(persona, []).append(row)

    counts = {}
    for persona, rows in by_persona.items():
        path = out_dir / f"{persona}.jsonl"
        with path.open("w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        counts[persona] = len(rows)
        # step coverage check
        by_step = {}
        for r in rows:
            by_step[r["step"]] = by_step.get(r["step"], 0) + 1
        print(f"{path.name}: {len(rows)} rows | step coverage: {dict(sorted(by_step.items()))}")
    print(f"\ntotal: {sum(counts.values())} seeds across {len(counts)} personas")


if __name__ == "__main__":
    main()
