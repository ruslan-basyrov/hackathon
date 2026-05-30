"""Customer-facing journey at `/journey` (BUILD_SPEC §Phase 3.5).

A stylized "HealthCover" insurance signup. Two driver modes share the same
visual layout and the same `Session`:

  * **auto mode** (default, `?mode=auto`) - `StubAgent` drives via auto-play;
    the audience watches a persona traverse the funnel; popups overlay on
    coach fire. This is the on-stage demo path.

  * **interactive mode** (`?mode=interactive`) - the human is the user. Every
    interactive element is clickable and builds a real `Action`; wall-clock
    dwell feeds the signals; a watchdog timer consults the coach every second
    so dwell-based interventions fire while you sit on a page.

Stable element IDs (test contract):
  journey-page, journey-step-label, journey-progress,
  journey-popup, journey-popup-type, journey-popup-text, journey-popup-close,
  journey-narration, journey-autoplay-toggle, journey-step-button,
  journey-persona-select, journey-method-select,
  journey-mode-toggle, journey-quick-judith, journey-quick-franz, journey-quick-peter,
  journey-cancel-link, journey-edit-dob, journey-continue
"""
from __future__ import annotations

from nicegui import ui

from services.ui.session import Session
from state_machine import Action


# Step int -> page title.
PAGE_TITLES = {
    0: "Welcome", 1: "What kind of coverage?", 2: "Who is this for?",
    3: "Your details", 4: "Choose your tariff", 6: "A few health questions",
    7: "Your personalised price", 12: "Confirm and finish",
    90: "You're covered", 91: "Session ended",
    92: "An advisor will be in touch", 93: "We'll call you back",
}
FUNNEL_STEPS = [1, 2, 3, 4, 6, 7, 12]
TERMINALS = {90, 91, 92, 93}

# Brand colours
BRAND_PRIMARY = "bg-sky-600"
BRAND_PRIMARY_HOVER = "hover:bg-sky-700"


def render(
    seed: int = 0,
    episode: int = 0,
    persona: str = "judith",
    method: str = "threshold",
    gbm_threshold: float = 0.85,
    narration: str = "",
    autoplay_ms: int = 900,
    mode: str = "auto",
):
    interactive = (mode == "interactive")
    sess = Session(
        seed=seed, episode=episode, persona=persona,
        method=method, gbm_threshold=gbm_threshold, interactive=interactive,
    )

    # ---- top branding bar --------------------------------------------------
    with ui.element("div").classes("w-full bg-sky-600 text-white px-6 py-3 shadow"):
        with ui.row().classes("w-full items-center max-w-5xl mx-auto"):
            ui.label("HealthCover").classes("text-2xl font-bold tracking-tight")
            ui.label("private medical insurance").classes("text-sky-100 text-sm ml-2")
            ui.element("div").classes("flex-grow")
            if interactive:
                ui.label("manual mode — your clicks are the user").classes(
                    "text-xs bg-sky-700 px-2 py-1 rounded font-mono"
                )
            ui.label("Need help? 0800 123 456").classes("text-sm ml-3")

    # ---- narration strip ---------------------------------------------------
    if narration:
        ui.label(narration).props('id="journey-narration"').classes(
            "max-w-5xl mx-auto mt-2 px-6 italic text-sky-900 text-sm"
        )
    else:
        ui.label("").props('id="journey-narration"').classes("hidden")

    # ---- progress bar ------------------------------------------------------
    with ui.row().classes("max-w-5xl mx-auto mt-4 px-6 items-center gap-3 w-full"):
        progress_label = ui.label("").props('id="journey-step-label"').classes(
            "text-sm font-semibold text-gray-700"
        )
        with ui.row().props('id="journey-progress"').classes("gap-1 flex-grow items-center"):
            progress_dots = []
            for _ in FUNNEL_STEPS:
                dot = ui.element("div").classes("h-2 flex-1 rounded-full bg-gray-200")
                progress_dots.append(dot)

    page_container = ui.column().props('id="journey-page"').classes(
        "max-w-3xl mx-auto mt-6 px-6 pb-4 w-full"
    )

    # ---- live detection-rules panel (visible especially in interactive mode)
    rules_panel = ui.column().props('id="journey-rules"').classes(
        "max-w-3xl mx-auto px-6 w-full mt-2 gap-2"
    )

    # ---- popup overlay -----------------------------------------------------
    with ui.dialog().props('id="journey-popup"') as popup, ui.card().classes(
        "min-w-[28rem] max-w-md p-6 border-l-4 border-sky-600"
    ):
        with ui.row().classes("items-center gap-2"):
            ui.icon("auto_awesome").classes("text-sky-600 text-2xl")
            ui.label("A nudge from HealthCover").classes("text-lg font-bold")
        ui.separator().classes("my-2")
        popup_type = ui.label("").props('id="journey-popup-type"').classes(
            "text-xs font-mono uppercase tracking-wide text-sky-700"
        )
        popup_text = ui.label("").props('id="journey-popup-text"').classes(
            "text-base text-gray-800 mt-2 leading-relaxed"
        )
        with ui.row().classes("mt-4 justify-end w-full"):
            ui.button("Got it", on_click=lambda: popup.close()).props(
                'id="journey-popup-close" flat'
            ).classes("bg-sky-600 text-white px-4")

    # ---- styling helpers ---------------------------------------------------
    def _h1(text: str):
        ui.label(text).classes("text-3xl font-bold text-gray-900 mb-2")

    def _subtitle(text: str):
        ui.label(text).classes("text-base text-gray-600 mb-6")

    def _selected_tariff_name() -> str:
        p = sess.provisional
        if p is None:
            return "Optimal"
        if abs(p - 38.74) < 0.01:
            return "Start"
        if abs(p - 68.14) < 0.01:
            return "Optimal"
        return "Optimal"

    # ---- generic option card ------------------------------------------------
    def _option_card(title: str, sub: str, selected: bool = False,
                     advisory: bool = False, on_click=None, elem_id: str = ""):
        cls = "p-5 rounded-lg border-2 transition-all flex-1 min-w-48 max-w-72 "
        if selected:
            cls += "border-sky-600 bg-sky-50 shadow-md "
        elif advisory:
            cls += "border-amber-300 bg-amber-50 "
        else:
            cls += "border-gray-200 bg-white "
        if on_click is not None:
            cls += "cursor-pointer hover:shadow-lg hover:border-sky-400 "
        card = ui.element("div").classes(cls)
        if elem_id:
            card.props(f'id="{elem_id}"')
        if on_click is not None:
            card.on("click", lambda _=None, h=on_click: h())
        with card:
            ui.label(title).classes("text-lg font-semibold mb-1")
            ui.label(sub).classes("text-sm text-gray-600")
        return card

    # ---- action emit (interactive mode) ------------------------------------
    def emit_action(type_: str, target: str = None):
        """Build a wall-clock-dwell Action from a user click and apply it."""
        if sess.is_done():
            return
        dwell = sess.wall_clock_dwell()
        sig, intervention = sess.consult_coach()   # coach sees pre-action signals
        sess.apply_action(Action(type=type_, target=target, dwell_s=dwell))
        # show popup if intervention fired AND we haven't already shown it for this step
        if intervention is not None and sess.shown_intervention_step != sig.step:
            sess.shown_intervention_step = sig.step
            popup_type.set_text(f"{intervention.type}  ·  {intervention.mode}")
            popup_text.set_text(intervention.text)
            popup.open()
        render_for_step(int(sess.state))

    # ============================================================================
    # AUTO-mode renderers (current behaviour - disabled UI, agent drives)
    # ============================================================================
    def _render_start_auto():
        _h1("Health insurance, online in minutes")
        _subtitle("A personalised quote in under five minutes. No paperwork. "
                  "No phone calls unless you want them.")
        with ui.row().classes("mt-8"):
            ui.button("Get a quote").props("disable").classes(
                f"{BRAND_PRIMARY} text-white px-8 py-3 text-base font-semibold"
            )

    def _render_s1_auto():
        _h1("What kind of coverage are you looking for?")
        _subtitle("You can change this later. We'll tailor the rest of the journey.")
        with ui.row().classes("gap-4 mt-6 flex-wrap"):
            _option_card("Private doctor visits",
                         "Outpatient care, specialists, diagnostics, therapies.",
                         selected=True)
            _option_card("Hospital stay", "Inpatient care, surgery, private room. Advisory.",
                         advisory=True)
            _option_card("Both", "Comprehensive coverage. Advisory.", advisory=True)

    def _render_s2_auto():
        _h1("Who would you like to insure?")
        _subtitle("")
        with ui.row().classes("gap-4 mt-6"):
            _option_card("Just me", "Personal coverage.", selected=True)
            _option_card("Family or other persons",
                         "Coverage for multiple people. Advisory.", advisory=True)

    def _render_s3_auto():
        _h1("Tell us a bit about yourself")
        _subtitle("We need a couple of basics before we can show you a price.")
        with ui.column().classes("gap-4 mt-4 max-w-md"):
            ui.input(label="Date of birth", value="15.07.1985").props("disable outlined").classes("w-full")
            ui.input(label="Social insurance number",
                     value="1234 150785").props("disable outlined").classes("w-full")

    def _render_s4_auto():
        _h1("Choose your tariff")
        _subtitle("Two tariffs you can buy online; two require a short advisory call.")
        with ui.row().classes("gap-3 mt-6 flex-wrap"):
            _tariff_card("Start", "€38.74 / mo",
                         "Outpatient essentials. Fully online.", online=True,
                         selected=(sess.last_action and sess.last_action.target == "Start"))
            _tariff_card("Optimal", "€68.14 / mo",
                         "Outpatient + therapies + medications. Fully online.",
                         online=True, badge="Popular",
                         selected=(sess.last_action and sess.last_action.target == "Optimal"))
            _tariff_card("Opt. Plus", "Advisory",
                         "Adds private hospital. Requires a short call.", online=False)
            _tariff_card("Premium", "Advisory",
                         "Top-tier coverage. Requires a short call.", online=False)

    def _tariff_card(name, price, body, online: bool, badge: str = "",
                     selected: bool = False, on_click=None, elem_id: str = ""):
        ring = "border-sky-600 bg-sky-50 shadow-md" if selected else (
            "border-amber-300 bg-amber-50" if not online else
            "border-gray-200 bg-white"
        )
        extra = " cursor-pointer hover:shadow-lg hover:border-sky-400" if on_click else ""
        card = ui.element("div").classes(
            f"p-4 rounded-lg border-2 flex-1 min-w-44 max-w-60 {ring}{extra}"
        )
        if elem_id:
            card.props(f'id="{elem_id}"')
        if on_click is not None:
            card.on("click", lambda _=None, h=on_click: h())
        with card:
            with ui.row().classes("items-center gap-2"):
                ui.label(name).classes("text-lg font-semibold")
                if badge:
                    ui.label(badge).classes(
                        "text-xs bg-amber-200 text-amber-900 px-2 py-0.5 rounded-full"
                    )
            ui.label(price).classes("text-xl font-bold text-sky-700 mt-1")
            ui.label(body).classes("text-sm text-gray-600 mt-2 leading-snug")
            ui.label("✓ Buy online" if online else "📞 Advisor only").classes(
                f"text-xs mt-3 {'text-emerald-700' if online else 'text-amber-800'} font-semibold"
            )

    def _render_s6_auto():
        _h1("A few health questions")
        _subtitle("Honest answers keep your cover valid. This stays private.")
        for q in [
            "Have you had any major surgery in the last 5 years?",
            "Are you currently on prescription medication?",
            "Do you have any chronic conditions?",
            "Have you smoked in the last 12 months?",
        ]:
            with ui.row().classes("items-center gap-4 my-2"):
                ui.label(q).classes("flex-1 text-sm")
                ui.radio(["Yes", "No"], value="No").props("disable inline").classes("text-sm")

    def _render_s7_auto():
        provisional = sess.provisional or 68.14
        final = round(provisional * (1 + sess.surcharge), 2)
        gap = round(final - provisional, 2)
        _h1("Your personalised price")
        _subtitle("Based on your health profile.")
        with ui.element("div").classes(
            "p-6 rounded-lg bg-gradient-to-br from-sky-50 to-white border border-sky-200"
        ):
            ui.label(_selected_tariff_name()).classes(
                "text-sm uppercase tracking-wide text-sky-700 font-semibold"
            )
            ui.label(f"€{final:.2f} / month").classes(
                "text-4xl font-bold text-gray-900 mt-1"
            )
            if gap > 0.01:
                ui.label(
                    f"€{gap:.2f} above the estimated €{provisional:.2f}, "
                    "based on the health questions you answered."
                ).classes("text-sm text-gray-600 mt-2 max-w-md")
        with ui.row().classes("mt-6 gap-3"):
            ui.button("Continue to checkout").props("disable").classes(
                f"{BRAND_PRIMARY} text-white px-6 py-2 font-semibold"
            )
            ui.button("Cancel").props("disable flat").classes("text-gray-500 px-3")

    def _render_s12_auto():
        provisional = sess.provisional or 68.14
        final = round(provisional * (1 + sess.surcharge), 2)
        _h1("Review and confirm")
        _subtitle("Almost done.")
        for k, v in [("Plan", _selected_tariff_name()), ("Monthly", f"€{final:.2f}"),
                     ("Billing", "Monthly, paperless"), ("Coverage starts", "Next month")]:
            with ui.row().classes("py-2 border-b border-gray-100"):
                ui.label(k).classes("w-40 text-gray-600")
                ui.label(v).classes("font-semibold text-gray-900")
        ui.checkbox("I agree to the terms and the privacy notice").props("disable").classes("mt-4")
        ui.button("Confirm and purchase").props("disable").classes(
            f"{BRAND_PRIMARY} text-white px-6 py-2 font-semibold mt-4"
        )

    # ============================================================================
    # INTERACTIVE-mode renderers (clickable; build Actions from user clicks)
    # ============================================================================
    def _render_start_interactive():
        _h1("Health insurance, online in minutes")
        _subtitle("A personalised quote in under five minutes. No paperwork. "
                  "No phone calls unless you want them.")
        with ui.row().classes("mt-8"):
            ui.button("Get a quote",
                      on_click=lambda: emit_action("continue")).props(
                'id="journey-continue"'
            ).classes(f"{BRAND_PRIMARY} text-white px-8 py-3 text-base font-semibold")

    def _render_s1_interactive():
        _h1("What kind of coverage are you looking for?")
        _subtitle("Pick one to continue.")
        with ui.row().classes("gap-4 mt-6 flex-wrap"):
            _option_card("Private doctor visits",
                         "Outpatient care, specialists, diagnostics, therapies.",
                         on_click=lambda: (emit_action("select", "doctor"),
                                           emit_action("continue")),
                         elem_id="journey-card-doctor")
            _option_card("Hospital stay", "Inpatient care, surgery. Advisory.",
                         advisory=True,
                         on_click=lambda: emit_action("select", "hospital"),
                         elem_id="journey-card-hospital")
            _option_card("Both", "Comprehensive. Advisory.", advisory=True,
                         on_click=lambda: emit_action("select", "both"),
                         elem_id="journey-card-both")

    def _render_s2_interactive():
        _h1("Who would you like to insure?")
        _subtitle("Pick one to continue.")
        with ui.row().classes("gap-4 mt-6"):
            _option_card("Just me", "Personal coverage.",
                         on_click=lambda: (emit_action("select", "myself"),
                                           emit_action("continue")),
                         elem_id="journey-card-myself")
            _option_card("Family or other persons",
                         "Coverage for multiple people. Advisory.", advisory=True,
                         on_click=lambda: emit_action("select", "others"),
                         elem_id="journey-card-others")

    def _render_s3_interactive():
        _h1("Tell us a bit about yourself")
        _subtitle("Click an Edit button to re-check a field (each click counts as a re-edit).")
        with ui.column().classes("gap-3 mt-4 max-w-md"):
            with ui.row().classes("gap-2 items-end"):
                ui.input(label="Date of birth", value="15.07.1985").props("disable outlined").classes("flex-grow")
                ui.button("Edit",
                          on_click=lambda: emit_action("change_field", "dob")).props(
                    'id="journey-edit-dob" flat'
                ).classes("text-sky-700")
            with ui.row().classes("gap-2 items-end"):
                ui.input(label="Social insurance number",
                         value="1234 150785").props("disable outlined").classes("flex-grow")
                ui.button("Edit",
                          on_click=lambda: emit_action("change_field", "ssn")).props(
                    "flat"
                ).classes("text-sky-700")
        ui.button("Continue", on_click=lambda: emit_action("continue")).props(
            'id="journey-continue"'
        ).classes(f"{BRAND_PRIMARY} text-white px-6 py-2 font-semibold mt-6")

    def _render_s4_interactive():
        _h1("Choose your tariff")
        _subtitle("Click a card to pick it. Hover the advisory ones if you want to "
                  "compare — that hover counts as a signal.")
        with ui.row().classes("gap-3 mt-6 flex-wrap"):
            _tariff_card("Start", "€38.74 / mo",
                         "Outpatient essentials. Fully online.", online=True,
                         on_click=lambda: (emit_action("select", "Start"),
                                           emit_action("continue")),
                         elem_id="journey-tariff-Start")
            _tariff_card("Optimal", "€68.14 / mo",
                         "Outpatient + therapies + medications. Fully online.",
                         online=True, badge="Popular",
                         on_click=lambda: (emit_action("select", "Optimal"),
                                           emit_action("continue")),
                         elem_id="journey-tariff-Optimal")
            _tariff_card("Opt. Plus", "Advisory",
                         "Adds private hospital. Requires a short call.", online=False,
                         on_click=lambda: emit_action("hover", "OptPlus"),
                         elem_id="journey-tariff-OptPlus")
            _tariff_card("Premium", "Advisory",
                         "Top-tier coverage. Requires a short call.", online=False,
                         on_click=lambda: emit_action("hover", "Premium"),
                         elem_id="journey-tariff-Premium")

    def _render_s6_interactive():
        _h1("A few health questions")
        _subtitle("Click any 'No' answer and then Continue.")
        for q in [
            "Have you had any major surgery in the last 5 years?",
            "Are you currently on prescription medication?",
            "Do you have any chronic conditions?",
            "Have you smoked in the last 12 months?",
        ]:
            with ui.row().classes("items-center gap-4 my-2"):
                ui.label(q).classes("flex-1 text-sm")
                ui.radio(["Yes", "No"], value="No").props("inline").classes("text-sm")
        ui.button("Continue", on_click=lambda: emit_action("continue")).props(
            'id="journey-continue"'
        ).classes(f"{BRAND_PRIMARY} text-white px-6 py-2 font-semibold mt-6")

    def _render_s7_interactive():
        provisional = sess.provisional or 68.14
        final = round(provisional * (1 + sess.surcharge), 2)
        gap = round(final - provisional, 2)
        _h1("Your personalised price")
        _subtitle("Based on your health profile.")
        with ui.element("div").classes(
            "p-6 rounded-lg bg-gradient-to-br from-sky-50 to-white border border-sky-200"
        ):
            ui.label(_selected_tariff_name()).classes(
                "text-sm uppercase tracking-wide text-sky-700 font-semibold"
            )
            ui.label(f"€{final:.2f} / month").classes(
                "text-4xl font-bold text-gray-900 mt-1"
            )
            if gap > 0.01:
                ui.label(
                    f"€{gap:.2f} above the estimated €{provisional:.2f}, "
                    "based on the health questions you answered."
                ).classes("text-sm text-gray-600 mt-2 max-w-md")
        with ui.row().classes("mt-6 gap-3 items-center"):
            ui.button("Continue to checkout",
                      on_click=lambda: emit_action("continue")).props(
                'id="journey-continue"'
            ).classes(f"{BRAND_PRIMARY} text-white px-6 py-2 font-semibold")
            ui.button("Cancel",
                      on_click=lambda: emit_action("hover", "cancel")).props(
                'id="journey-cancel-link" flat'
            ).classes("text-gray-500 px-3 underline")
            ui.label("(clicking Cancel registers a 'hovered cancel' signal "
                     "— it doesn't actually cancel)").classes(
                "text-xs text-gray-400 ml-2"
            )

    def _render_s12_interactive():
        provisional = sess.provisional or 68.14
        final = round(provisional * (1 + sess.surcharge), 2)
        _h1("Review and confirm")
        _subtitle("Almost done.")
        for k, v in [("Plan", _selected_tariff_name()), ("Monthly", f"€{final:.2f}"),
                     ("Billing", "Monthly, paperless"), ("Coverage starts", "Next month")]:
            with ui.row().classes("py-2 border-b border-gray-100"):
                ui.label(k).classes("w-40 text-gray-600")
                ui.label(v).classes("font-semibold text-gray-900")
        ui.checkbox("I agree to the terms and the privacy notice").classes("mt-4")
        ui.button("Confirm and purchase",
                  on_click=lambda: emit_action("continue")).props(
            'id="journey-continue"'
        ).classes(f"{BRAND_PRIMARY} text-white px-6 py-2 font-semibold mt-4")

    def _render_terminal():
        cur = int(sess.state)
        if cur == 90:
            ui.icon("check_circle").classes("text-emerald-500 text-6xl")
            _h1("You're covered.")
            _subtitle("Welcome to HealthCover. We've emailed your policy.")
        elif cur == 91:
            ui.icon("close").classes("text-gray-400 text-6xl")
            _h1("Session ended")
            _subtitle("You can come back anytime — your progress is saved.")
        elif cur == 92:
            ui.icon("support_agent").classes("text-amber-500 text-6xl")
            _h1("An advisor will be in touch")
            _subtitle("We'll call you within the next business day "
                      "to discuss the advisory tariffs.")
        elif cur == 93:
            ui.icon("phone_callback").classes("text-sky-500 text-6xl")
            _h1("We'll call you back")
            _subtitle("Expect a call within the next business day — "
                      "no fuss, no obligations.")

    # ---- live detection-rules panel ----------------------------------------
    # Mirrors the conditions in coach/detection.py:_detect_threshold so the
    # presenter can see exactly which signals are at / over their thresholds
    # at any given moment. The panel re-paints on every user action AND on
    # every watchdog tick, so dwell-based rules show their counter ticking up
    # in real time.
    def _threshold_rule_specs():
        """Return the four threshold rules with their (condition_label,
        is_met, current_value_str) tuples. Reads sess.last_signal AND the
        live wall-clock dwell so the panel matches what the watchdog sees."""
        d = sess.cfg["detection"]
        sig = sess._compute_signals()
        # what the watchdog would see right now (dwell incl. wall-clock)
        elapsed = sess.wall_clock_dwell()
        eff_dwell = sig.dwell_current_s + elapsed
        return [
            ("s4_dwell", "Judith at the price table", [
                ("step == 4",
                 sig.step == 4, f"{sig.step}", "= 4"),
                (f"dwell_current_s > {d['dwell_threshold_s']}",
                 eff_dwell > d['dwell_threshold_s'], f"{eff_dwell:.1f}s", f"> {d['dwell_threshold_s']}s"),
            ]),
            ("s7_price_gap+cancel_hover", "Franz at the final price", [
                ("step == 7",
                 sig.step == 7, f"{sig.step}", "= 7"),
                (f"price_gap_eur > {d['price_gap_threshold']}",
                 sig.price_gap_eur > d['price_gap_threshold'],
                 f"€{sig.price_gap_eur:.2f}", f"> €{d['price_gap_threshold']:.2f}"),
                ("hover_cancel_count >= 1",
                 sig.hover_cancel_count >= 1, str(sig.hover_cancel_count), ">= 1"),
            ]),
            ("early_overwhelm", "Peter, struggling early", [
                (f"field_change_count >= {d['overwhelm_changes']}",
                 sig.field_change_count >= d['overwhelm_changes'],
                 str(sig.field_change_count), f">= {d['overwhelm_changes']}"),
                (f"steps_completed < {d['early_overwhelm_max_steps']}",
                 sig.steps_completed < d['early_overwhelm_max_steps'],
                 str(sig.steps_completed), f"< {d['early_overwhelm_max_steps']}"),
            ]),
            ("repeated_back_nav", "generic friction", [
                (f"back_nav_count >= {d['back_nav_threshold']}",
                 sig.back_nav_count >= d['back_nav_threshold'],
                 str(sig.back_nav_count), f">= {d['back_nav_threshold']}"),
            ]),
        ]

    def refresh_rules_panel():
        rules_panel.clear()
        method = sess.cfg["detection"].get("method", "threshold")
        with rules_panel:
            with ui.row().classes("items-center gap-2 mb-1"):
                ui.label("Detection rules (live)").classes(
                    "text-sm font-semibold text-gray-700"
                )
                ui.label(f"method: {method}").classes(
                    "text-xs font-mono bg-gray-100 px-2 py-0.5 rounded text-gray-600"
                )
                if interactive:
                    ui.label("dwell counts wall-clock time").classes(
                        "text-xs italic text-gray-400 ml-auto"
                    )
            if method != "threshold":
                ui.label(
                    "GBM detector: rules not inspectable; this panel only "
                    "lists thresholds. Switch detector to 'threshold' to see them."
                ).classes("text-xs italic text-gray-500 mt-1")
                return
            for name, narrative, conditions in _threshold_rule_specs():
                all_met = all(c[1] for c in conditions)
                outer_cls = "p-2 rounded border-l-4 "
                outer_cls += ("border-emerald-500 bg-emerald-50"
                              if all_met else "border-gray-200 bg-gray-50")
                with ui.element("div").classes(outer_cls):
                    with ui.row().classes("items-center gap-2"):
                        ui.label(name).classes("font-mono font-bold text-sm")
                        ui.label(f"— {narrative}").classes("text-xs text-gray-500")
                        ui.element("div").classes("flex-grow")
                        if all_met:
                            ui.label("FIRES").classes(
                                "text-xs font-bold bg-emerald-200 text-emerald-800 "
                                "px-2 py-0.5 rounded"
                            )
                    for label, met, current, _threshold in conditions:
                        with ui.row().classes("items-center gap-2 ml-2 text-xs font-mono"):
                            color = "text-emerald-600" if met else "text-gray-400"
                            ui.label("✓" if met else "·").classes(f"w-4 {color}")
                            ui.label(label).classes("flex-1 text-gray-600")
                            ui.label(current).classes(
                                f"w-16 text-right font-semibold "
                                f"{'text-emerald-700' if met else 'text-gray-700'}"
                            )

    AUTO_RENDERERS = {
        0: _render_start_auto, 1: _render_s1_auto, 2: _render_s2_auto,
        3: _render_s3_auto, 4: _render_s4_auto, 6: _render_s6_auto,
        7: _render_s7_auto, 12: _render_s12_auto,
    }
    INTERACTIVE_RENDERERS = {
        0: _render_start_interactive, 1: _render_s1_interactive,
        2: _render_s2_interactive, 3: _render_s3_interactive,
        4: _render_s4_interactive, 6: _render_s6_interactive,
        7: _render_s7_interactive, 12: _render_s12_interactive,
    }

    # ---- driver: auto-play timer or watchdog -------------------------------
    autoplay_timer = {"t": None}
    watchdog_timer = {"t": None}

    def _step_position(cur: int) -> int:
        try:
            return FUNNEL_STEPS.index(cur) + 1
        except ValueError:
            return 0

    def paint_progress(cur: int):
        pos = _step_position(cur)
        for i, dot in enumerate(progress_dots):
            if i < pos:
                dot.classes(replace=f"h-2 flex-1 rounded-full {BRAND_PRIMARY}")
            else:
                dot.classes(replace="h-2 flex-1 rounded-full bg-gray-200")
        if cur in TERMINALS:
            progress_label.set_text(PAGE_TITLES[cur])
        elif pos:
            progress_label.set_text(f"Step {pos} of {len(FUNNEL_STEPS)}")
        else:
            progress_label.set_text("Welcome")

    def paint_page(cur: int):
        page_container.clear()
        with page_container:
            if cur in TERMINALS:
                _render_terminal()
                return
            renderers = INTERACTIVE_RENDERERS if interactive else AUTO_RENDERERS
            renderer = renderers.get(cur)
            # interactive Back button: emits a `back` Action so back_nav_count
            # increments AND the state machine moves backward in the funnel.
            # Shown on S1..S12 (no-op on S1 because it has no PREV, but the
            # signal still records - useful for triggering repeated_back_nav).
            if interactive and cur in (1, 2, 3, 4, 6, 7, 12):
                ui.button("← Back", on_click=lambda: emit_action("back")).props(
                    'id="journey-back" flat dense'
                ).classes("text-sky-700 self-start mb-2")
            if renderer:
                renderer()

    def render_for_step(cur: int):
        paint_progress(cur)
        paint_page(cur)
        refresh_rules_panel()

    def stop_autoplay():
        if autoplay_timer["t"] is not None:
            autoplay_timer["t"].deactivate()
            autoplay_timer["t"] = None

    def stop_watchdog():
        if watchdog_timer["t"] is not None:
            watchdog_timer["t"].deactivate()
            watchdog_timer["t"] = None

    def auto_tick():
        if sess.is_done():
            stop_autoplay()
            return
        prev_state = int(sess.state)
        result = sess.step_once()
        if result and result["intervention"] is not None:
            iv = result["intervention"]
            render_for_step(iv.step)
            popup_type.set_text(f"{iv.type}  ·  {iv.mode}")
            popup_text.set_text(iv.text)
            stop_autoplay()
            popup.open()
            return
        if int(sess.state) != prev_state:
            render_for_step(int(sess.state))
        if sess.is_done():
            stop_autoplay()
            render_for_step(int(sess.state))

    def watchdog_tick():
        """Interactive-mode passive coach: if the human just sits on a page,
        synthesize dwell from wall-clock time and ask the coach. If a popup
        fires, show it once per state (gated by `shown_intervention_step`).
        Also re-paints the rules panel so dwell counters tick up live."""
        if sess.is_done():
            stop_watchdog()
            return
        sig, intervention = sess.consult_coach(
            virtual_dwell_s=sess.wall_clock_dwell()
        )
        refresh_rules_panel()
        if intervention is not None and sess.shown_intervention_step != int(sess.state):
            sess.shown_intervention_step = int(sess.state)
            popup_type.set_text(f"{intervention.type}  ·  {intervention.mode}")
            popup_text.set_text(intervention.text)
            popup.open()

    def resume_after_popup():
        popup.close()
        render_for_step(int(sess.state))
        if not interactive and not sess.is_done() and autoplay_switch.value:
            autoplay_timer["t"] = ui.timer(autoplay_ms / 1000.0, auto_tick)

    popup.on("hide", resume_after_popup)

    def toggle_autoplay(e):
        if e.value and not sess.is_done():
            autoplay_timer["t"] = ui.timer(autoplay_ms / 1000.0, auto_tick)
        else:
            stop_autoplay()

    def manual_step():
        """In auto mode: advance one tick (pauses auto-play). In interactive
        mode this button isn't shown (it'd be redundant - you click the actual
        page elements)."""
        if autoplay_switch.value:
            autoplay_switch.value = False
        stop_autoplay()
        auto_tick()

    # ---- footer controls ---------------------------------------------------
    def _scenario_url(p: str, ep: int) -> str:
        return (f"/journey?seed={seed}&episode={ep}"
                f"&persona={p}&method={method}&gbm_threshold={gbm_threshold}"
                f"&mode={mode}")

    with ui.row().classes("max-w-5xl mx-auto mt-6 px-6 gap-3 items-center "
                          "border-t border-gray-200 pt-4 w-full"):
        if not interactive:
            ui.button("Step", on_click=manual_step).props(
                'id="journey-step-button"'
            ).classes(f"{BRAND_PRIMARY} text-white px-4")
            autoplay_switch = ui.switch("Auto-play", value=True,
                                        on_change=toggle_autoplay).props(
                'id="journey-autoplay-toggle"'
            )
        else:
            # placeholder so subsequent code referring to autoplay_switch.value
            # doesn't blow up in interactive mode (it never starts auto-play)
            autoplay_switch = ui.switch("Auto-play", value=False).props(
                'id="journey-autoplay-toggle" disable'
            ).classes("hidden")
            ui.label("Click the actual page elements above. Coach watches "
                     "your dwell — sit on a page to test that.").classes(
                "text-sm text-gray-600"
            )
        ui.select(
            options=["judith", "franz", "peter", "global"], value=persona,
            on_change=lambda e: ui.navigate.to(_scenario_url(e.value, episode)),
        ).props('id="journey-persona-select"').classes("w-40")
        ui.select(
            options=["threshold", "gbm"], value=method,
            on_change=lambda e: ui.navigate.to(
                f"/journey?seed={seed}&episode={episode}"
                f"&persona={persona}&method={e.value}&gbm_threshold={gbm_threshold}&mode={mode}"
            ),
        ).props('id="journey-method-select"').classes("w-40")
        ui.element("div").classes("flex-grow")
        ui.link("→ debug view", f"/?seed={seed}&episode={episode}"
                f"&persona={persona}&method={method}").classes(
            "text-sm text-sky-700 underline"
        )

    # quick-load scenario pills + mode toggle (always visible, low key)
    with ui.row().classes("max-w-5xl mx-auto px-6 gap-2 items-center "
                          "text-xs text-gray-500 mt-2 mb-6 flex-wrap"):
        ui.label("Quick scenarios:").classes("font-semibold")
        ui.link("Judith S4", "/journey?seed=0&episode=0&persona=judith&method=threshold"
                + (f"&mode={mode}" if interactive else "")).props(
            'id="journey-quick-judith"'
        ).classes("text-sky-700 underline")
        ui.link("Franz S7", "/journey?seed=0&episode=16&persona=franz&method=threshold"
                + (f"&mode={mode}" if interactive else "")).props(
            'id="journey-quick-franz"'
        ).classes("text-sky-700 underline")
        ui.link("Peter early", "/journey?seed=0&episode=0&persona=peter&method=threshold"
                + (f"&mode={mode}" if interactive else "")).props(
            'id="journey-quick-peter"'
        ).classes("text-sky-700 underline")
        ui.element("div").classes("flex-grow")
        target_mode = "auto" if interactive else "interactive"
        toggle_label = "↷ Switch to auto" if interactive else "✋ Drive it yourself"
        ui.link(toggle_label,
                f"/journey?seed={seed}&episode={episode}&persona={persona}"
                f"&method={method}&gbm_threshold={gbm_threshold}&mode={target_mode}").props(
            'id="journey-mode-toggle"'
        ).classes("text-sky-700 underline font-semibold")
        ui.label(
            f"seed={seed}  ep={episode}  detector={method}  mode={mode}"
        ).classes("font-mono")

    # initial paint
    render_for_step(int(sess.state))

    # kick off driver
    if interactive:
        # watchdog: 1s tick, only fires once per state (gated by shown_intervention_step)
        watchdog_timer["t"] = ui.timer(1.0, watchdog_tick)
    else:
        if autoplay_switch.value:
            autoplay_timer["t"] = ui.timer(autoplay_ms / 1000.0, auto_tick)
