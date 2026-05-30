"""
persona_factory.py  (v2 — wired to the real personas.json)

Responsibility split (unchanged from v1):
    The LLM only APPRAISES the screen and SPEAKS. A deterministic engine (code)
    owns the emotional dials, so praise/fluff cannot move trust or intent.

What changed in v2:
    Sensitivities and the initial state are now DERIVED FROM REAL SURVEY NUMBERS
    in personas.json instead of substring heuristics. Crucially, they are derived
    ONLY from stable trait data (decision drivers, channel preferences, price
    attitudes, online-purchase history). The 'online_funnel_behavior_hypotheses'
    block is deliberately NOT used as input — those are what you're testing, so
    conditioning the agent on them would make the simulation circular. They are
    held out for validation (see validate_against_hypotheses at the bottom).
"""

import json
import random


# ---------------------------------------------------------------------------
# Fixed, persona-AGNOSTIC behaviour protocol. The LLM never authors its mood.
# ---------------------------------------------------------------------------
BEHAVIOR_PROTOCOL = """
--- How you operate ---
You are a real person shopping for health insurance online. You are NOT an
assistant and you do not help anyone. You are shown one screen or event at a
time, and sometimes a message from an on-site chatbot.

YOUR ONLY JOB EACH TURN is to perceive and express:
1. APPRAISE the screen on the fixed axes below.
2. Optionally SAY something. You rarely speak to interfaces; usually this is null.
3. Record a short private MONOLOGUE (one or two sentences, first person).

You do NOT track or report your mood, patience, trust, or how likely you are to
leave. Never output numbers about your feelings. If a chatbot is encouraging,
flattering, or reassuring, record it in the appraisal as unsolicited and without
substance — praise is not information and must not change how you read the screen.

APPRAISAL AXES:
- solicited:          did you ask for this? (a popup you didn't request = false)
- substance:          "data" (real, checkable info) | "fluff" (reassurance/marketing,
                      no facts) | "friction_add" (adds steps/decisions) |
                      "friction_remove" (removes steps / simplifies) | "neutral"
- routes_to_advisor:  does it push you toward a human (advisor, agent, call, live help)?
- price_consistency:  if a price is shown vs the last price you saw:
                      "consistent" | "mismatch" | "n_a"
- mentions_price:     true/false; if a NEW price appears, put the number in price_value

OUTPUT strict JSON only, no markdown, exactly:
{
  "appraisal": {
    "stimulus_summary": "string",
    "solicited": true,
    "substance": "data|fluff|friction_add|friction_remove|neutral",
    "routes_to_advisor": false,
    "price_consistency": "consistent|mismatch|n_a",
    "mentions_price": false,
    "price_value": null
  },
  "speech": null,
  "monologue": "string"
}
""".strip()


# ---------------------------------------------------------------------------
# Small safe accessors so missing keys never crash the derivation.
# ---------------------------------------------------------------------------
def _num(d, *path, default=0.0):
    cur = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur if isinstance(cur, (int, float)) else default


def _c(x, lo, hi):
    return max(lo, min(hi, x))


def _channel_step_shares(segment_data):
    """Fraction of journey steps whose DOMINANT channel is self_online / via_advisor / customer_service."""
    steps = segment_data.get("channel_preference_per_journey_step_pct_dominant_channel", {})
    if not steps:
        return {"self_online": 0.0, "via_advisor": 0.0, "customer_service": 0.0}
    counts = {"self_online": 0, "via_advisor": 0, "customer_service": 0}
    for v in steps.values():
        ch = v.get("channel")
        if ch in counts:
            counts[ch] += 1
    n = len(steps)
    return {k: counts[k] / n for k in counts}


# ---------------------------------------------------------------------------
# DERIVATIONS — grounded in stable survey traits ONLY (no funnel hypotheses).
# ---------------------------------------------------------------------------
def derive_sensitivities(segment_data):
    dd = segment_data.get("decision_drivers_pct", {})
    pc = segment_data.get("purchase_criteria_pct", {})
    ib = segment_data.get("insurance_behavior", {})
    ob = segment_data.get("online_behavior", {})
    demo = segment_data.get("demographics", {})
    shares = _channel_step_shares(segment_data)

    # price sensitivity: blend of price-performance focus + cheapest-picking + self-retention
    price_raw = (0.50 * _num(dd, "price_performance_ratio")
                 + 0.35 * _num(dd, "always_picks_cheapest")
                 + 0.15 * _num(dd, "willing_self_retention_for_lower_premium")) / 100.0
    price_sensitivity = round(0.8 + price_raw * 0.6, 3)

    # digital self-service expectation D in [0,1]
    D = (
        _num(dd, "values_apps_and_portals") / 100.0
        + _num(pc, "online_purchase_option") / 100.0
        + _num(pc, "digital_services_available") / 100.0
        + _num(ob, "ever_purchased_insurance_online_pct") / 100.0
        + shares["self_online"]
    ) / 5.0
    friction_intolerance = round(0.8 + D * 0.6, 3)

    # data appetite: clear info + comparison-shopping reassure this person
    data_raw = (_num(dd, "compares_multiple_offers") + _num(pc, "transparent_product_info")) / 200.0
    data_appetite = round(0.9 + data_raw * 0.4, 3)

    # human-help orientation: does this person want a human to CLOSE the deal?
    purchase_channel = (segment_data
                        .get("channel_preference_per_journey_step_pct_dominant_channel", {})
                        .get("purchase", {})
                        .get("channel", "self_online"))
    advisor_affinity = (
        _num(dd, "personal_advisor_trust") / 100.0
        + _num(pc, "advisor_competence") / 100.0
        + (1.0 - _num(ib, "advisor_type_pct", "no_advisor") / 100.0)
    ) / 3.0
    if purchase_channel == "self_online":
        advisor_sign = -1
        advisor_weight = round(_c(0.5 + 0.5 * D, 0.4, 1.0), 3)      # how strongly being routed annoys them
    else:  # via_advisor or customer_service -> human handoff is welcome
        advisor_sign = 1
        help_pref = max(advisor_affinity, shares["customer_service"], shares["via_advisor"])
        advisor_weight = round(_c(0.5 + 0.5 * help_pref, 0.4, 1.0), 3)

    # overwhelm: inverse of "information capacity" (comparison habit, matura, digital fluency)
    info_capacity = (
        _num(dd, "compares_multiple_offers") / 100.0
        + _num(demo, "education", "with_matura_pct") / 100.0
        + D
    ) / 3.0
    overwhelm_sensitivity = round(_c(1.3 - info_capacity, 0.5, 1.3), 3)

    return {
        "price_sensitivity": price_sensitivity,
        "friction_intolerance": friction_intolerance,
        "data_appetite": data_appetite,
        "advisor_sign": advisor_sign,
        "advisor_weight": advisor_weight,
        "overwhelm_sensitivity": overwhelm_sensitivity,
    }


def derive_initial_state(segment_data, sens):
    ib = segment_data.get("insurance_behavior", {})
    ob = segment_data.get("online_behavior", {})
    ps = segment_data.get("purchase_split_pct", {})

    # starting intent from ONLINE-PURCHASE PROPENSITY (a trait), not from the
    # hypothesised drop-off step (which would be circular).
    propensity = (
        _num(ps, "summary_purchase_online") / 100.0
        + _num(ob, "likely_to_purchase_online_next_3y_pct") / 100.0
        + _num(ob, "ever_purchased_insurance_online_pct") / 100.0
    ) / 3.0
    intent0 = round(_c(0.4 + propensity * 0.7, 0.3, 0.95), 3)

    patience0 = round(_c(0.7 - (sens["friction_intolerance"] - 0.9) * 0.5, 0.4, 0.75), 3)
    trust0 = round(_c(0.45 + _num(ib, "general_attitude_positive_pct") / 100.0 * 0.2, 0.4, 0.65), 3)

    return {
        "patience": patience0,
        "trust": trust0,
        "intent_to_complete": intent0,
        "irritation": 0.1,
        "price_anchor": None,
    }


# ---------------------------------------------------------------------------
# Deterministic state engine (anti-sycophancy rule lives here, in code).
# ---------------------------------------------------------------------------
DIALS = ("patience", "trust", "intent_to_complete", "irritation")
MAX_STEP = 0.15


def compute_deltas(appraisal, sens):
    d = {k: 0.0 for k in DIALS}
    substance = appraisal.get("substance", "neutral")
    solicited = appraisal.get("solicited", True)
    price = appraisal.get("price_consistency", "n_a")
    overwhelm = sens.get("overwhelm_sensitivity", 1.0)

    if price == "mismatch":
        d["trust"] -= 0.15 * sens["price_sensitivity"]
        d["intent_to_complete"] -= 0.15 * sens["price_sensitivity"]
        d["irritation"] += 0.15
    elif price == "consistent" and appraisal.get("mentions_price"):
        d["trust"] += 0.05
        d["intent_to_complete"] += 0.05

    if appraisal.get("routes_to_advisor"):
        mag = 0.12 * sens["advisor_weight"]
        d["trust"] += sens["advisor_sign"] * mag * 0.6
        d["intent_to_complete"] += sens["advisor_sign"] * mag
        if sens["advisor_sign"] < 0:
            d["irritation"] += mag

    if substance == "data":
        d["trust"] += 0.06 * sens["data_appetite"]
        d["intent_to_complete"] += 0.05 * sens["data_appetite"]
    elif substance == "friction_remove":
        # simplification helps overwhelmed personas the most
        d["patience"] += 0.05
        d["intent_to_complete"] += 0.04 * overwhelm
    elif substance == "friction_add":
        scale = max(sens["friction_intolerance"], overwhelm)
        d["patience"] -= 0.08 * scale
        d["irritation"] += 0.06 * scale
    elif substance == "fluff":
        # HARD RULE: fluff can ONLY annoy. It never touches trust or intent.
        d["irritation"] += 0.07 if not solicited else 0.0
        d["patience"] -= 0.04 if not solicited else 0.0

    if substance == "neutral" and price == "n_a":
        d["irritation"] -= 0.03
        d["patience"] += 0.02

    return d


def apply_deltas(prior, deltas):
    new = dict(prior)
    for k in DIALS:
        p = prior.get(k, 0.0)
        proposed = max(p - MAX_STEP, min(p + MAX_STEP, p + deltas.get(k, 0.0)))
        new[k] = round(max(0.0, min(1.0, proposed)), 4)
    if deltas.get("_new_price") is not None:
        new["price_anchor"] = deltas["_new_price"]
    return new


def derive_action(state, appraisal, sens):
    intent, trust, irritation = state["intent_to_complete"], state["trust"], state["irritation"]
    if intent < 0.35 or (irritation > 0.7 and trust < 0.4):
        return "abandon"
    if appraisal.get("price_consistency") == "mismatch":
        return "abandon" if trust < 0.45 else "hover_cancel"
    if appraisal.get("routes_to_advisor"):
        if sens["advisor_sign"] < 0 and intent < 0.5:      # Franz: wall
            return "abandon" if intent < 0.4 else "hesitate"
        if sens["advisor_sign"] > 0:                        # Judith/Peter: relief
            return "accept_handoff"
    # help-seekers reach for support when overloaded; self-service types push on or quit
    if appraisal.get("substance") == "friction_add" and state["patience"] < 0.4:
        return "seek_info" if sens["advisor_sign"] > 0 else ("hesitate" if intent > 0.45 else "abandon")
    if not appraisal.get("solicited") and appraisal.get("substance") == "fluff":
        return "dismiss_overlay"
    if 0.4 <= irritation <= 0.7:
        return "seek_info"
    return "proceed"


def observable_for_chatbot(full_output):
    """WHITELIST: only what a real user transmits through the chat channel."""
    b = full_output["behavior"]
    return {
        "user_message": b.get("speech"),
        "user_left": b["action"] == "abandon",
    }


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
def _pretty(value):
    if not isinstance(value, str):
        return value
    return value.replace("_pct", "").replace("_", " ").title()


class PersonaFactory:
    def __init__(self, personas_path):
        with open(personas_path, "r", encoding="utf-8") as f:
            self.personas_data = json.load(f)

    def _sample_from_dict(self, pct_dict):
        valid = {k: v for k, v in pct_dict.items() if isinstance(v, (int, float))}
        if not valid:
            return None
        return random.choices(list(valid.keys()), weights=list(valid.values()), k=1)[0]

    def _generate_instance_attributes(self, segment_data):
        demo = segment_data.get("demographics", {})
        gender_opts = {"female": demo.get("female_pct", 0),
                       "male": demo.get("male_pct", 0),
                       "diverse": demo.get("diverse_pct", 0)}
        beh = segment_data.get("behavior_and_attitudes", [])
        needs = segment_data.get("needs", [])
        pains = segment_data.get("pain_points", [])
        return {
            "age_group": self._sample_from_dict(demo.get("age_distribution_pct", {})),
            "gender": self._sample_from_dict(gender_opts),
            "education": self._sample_from_dict(demo.get("education", {})),
            "urbanity": self._sample_from_dict(demo.get("urbanity", {})),
            "region": self._sample_from_dict(demo.get("regional_distribution_pct", {})),
            "household": self._sample_from_dict(demo.get("household", {})),
            "employment": self._sample_from_dict(demo.get("employment", {})),
            "behavior_traits": random.sample(beh, min(2, len(beh))),
            "needs": random.sample(needs, min(2, len(needs))),
            "pain_points": random.sample(pains, min(2, len(pains))),
            # NOTE: decision_drivers_pct are independent agreement rates, not exclusive
            # options. We sample one only for identity flavour; sensitivities use the
            # full vector via derive_sensitivities().
            "primary_decision_driver": self._sample_from_dict(segment_data.get("decision_drivers_pct", {})),
        }

    def _generate_identity_block(self, segment_data, attrs):
        arch = segment_data.get("persona_archetype", {})
        edu = "With Matura" if attrs["education"] == "with_matura_pct" else "Without Matura"
        return (
            f"You are {arch.get('name')}, a real person shopping for health insurance online.\n"
            f"Segment: {segment_data.get('name_full')} ({segment_data.get('name_short')})\n"
            f"A phrase that sounds like you: '{arch.get('typical_quote')}'\n\n"
            f"--- You ---\n"
            f"Age: {attrs['age_group']}  |  Gender: {attrs['gender']}  |  {edu}\n"
            f"Lives in: {attrs['region']} ({_pretty(attrs['urbanity'])})\n"
            f"Household: {_pretty(attrs['household'])}  |  Work: {_pretty(attrs['employment'])}\n\n"
            f"--- What you're like ---\n"
            f"Behaviour: " + "; ".join(attrs["behavior_traits"]) + "\n"
            f"Needs: " + "; ".join(attrs["needs"]) + "\n"
            f"Pain points: " + "; ".join(attrs["pain_points"]) + "\n"
            f"Primary decision driver: {_pretty(attrs['primary_decision_driver'])}\n\n"
            + BEHAVIOR_PROTOCOL
        )

    def create_persona(self, segment_id):
        segment_data = self.personas_data["personas"].get(segment_id)
        if not segment_data:
            raise ValueError(f"Segment '{segment_id}' not found in personas data.")
        attrs = self._generate_instance_attributes(segment_data)
        sens = derive_sensitivities(segment_data)

        from bots.persona import Persona
        persona = Persona(segment_id, segment_data["persona_archetype"]["name"], segment_data)
        persona.instance_attributes = attrs
        persona.sensitivities = sens
        persona.initial_state = derive_initial_state(segment_data, sens)
        persona.llm_prompt = self._generate_identity_block(segment_data, attrs)
        return persona

    def get_available_segments(self):
        return list(self.personas_data["personas"].keys())


# ---------------------------------------------------------------------------
# Stateful runtime — threads state, separates the three audiences.
# ---------------------------------------------------------------------------
class PersonaAgent:
    def __init__(self, persona, llm_call):
        self.persona = persona
        self.llm_call = llm_call
        self.state = dict(persona.initial_state)

    def react(self, screen_description, chatbot_message=None):
        result = self.llm_call(
            self.persona.llm_prompt,
            {"screen": screen_description, "chatbot_message": chatbot_message,
             "last_price_seen": self.state.get("price_anchor")},
        )
        appraisal = result["appraisal"]
        deltas = compute_deltas(appraisal, self.persona.sensitivities)
        if appraisal.get("mentions_price") and appraisal.get("price_value") is not None:
            deltas["_new_price"] = appraisal["price_value"]
        self.state = apply_deltas(self.state, deltas)
        action = derive_action(self.state, appraisal, self.persona.sensitivities)
        return {
            "appraisal": appraisal,
            "state": self.state,                       # -> eval log only
            "behavior": {"action": action,
                         "speech": result.get("speech"),
                         "monologue": result.get("monologue")},
        }


# ---------------------------------------------------------------------------
# VALIDATION (the right use of online_funnel_behavior_hypotheses): compare the
# step where the sim actually abandoned against the held-out hypothesised step.
# This is a check, never an input to the agent.
# ---------------------------------------------------------------------------
def validate_against_hypotheses(segment_data, simulated_abandon_step):
    hyp = segment_data.get("online_funnel_behavior_hypotheses", {})
    return {
        "hypothesised_drop_off": hyp.get("primary_drop_off_step"),
        "simulated_drop_off": simulated_abandon_step,
        "match": hyp.get("primary_drop_off_step") == simulated_abandon_step,
    }


# Quick local check of derived parameters across the three segments.
if __name__ == "__main__":
    import sys
    factory_data = json.load(open(sys.argv[1], encoding="utf-8"))
    for sid, seg in factory_data["personas"].items():
        s = derive_sensitivities(seg)
        st = derive_initial_state(seg, s)
        print(seg["persona_archetype"]["name"], sid)
        print("  sensitivities:", s)
        print("  initial_state:", st)