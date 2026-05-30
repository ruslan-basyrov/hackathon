"""Customer-facing journey at `/journey` (BUILD_SPEC §Phase 3.5).

A stylized "HealthCover" insurance signup. Renders one page per simulator step.
The agent's actions drive page transitions; intervention popups overlay the
page when the coach fires. Auto-play is ON by default - this is the on-stage
demo route. The original debug viewer lives at `/`.

Stable element IDs (test contract):
  journey-page             - the page content container (changes per step)
  journey-step-label       - "Step N of 7" indicator
  journey-progress         - the dotted progress bar
  journey-popup            - the intervention overlay
  journey-popup-type       - intervention type inside the popup
  journey-popup-text       - realize() output inside the popup
  journey-popup-close      - dismiss the popup
  journey-narration        - on-screen narration for the demo path
  journey-autoplay-toggle, journey-persona-select, journey-method-select
"""
from __future__ import annotations

from nicegui import ui

from services.ui.session import Session


# Step int -> (page title, position-in-funnel) — only in-scope steps render here.
PAGE_TITLES = {
    0: "Welcome",
    1: "What kind of coverage?",
    2: "Who is this for?",
    3: "Your details",
    4: "Choose your tariff",
    6: "A few health questions",
    7: "Your personalised price",
    12: "Confirm and finish",
    90: "You're covered",
    91: "Session ended",
    92: "An advisor will be in touch",
    93: "We'll call you back",
}
FUNNEL_STEPS = [1, 2, 3, 4, 6, 7, 12]   # the user-visible progress positions
TERMINALS = {90, 91, 92, 93}

# Brand colours (Tailwind class fragments)
BRAND_PRIMARY = "bg-sky-600"
BRAND_PRIMARY_HOVER = "hover:bg-sky-700"
BRAND_PRIMARY_TEXT = "text-sky-600"
BRAND_ACCENT = "bg-amber-100"


def render(
    seed: int = 0,
    episode: int = 0,
    persona: str = "judith",
    method: str = "threshold",
    gbm_threshold: float = 0.85,
    narration: str = "",
    autoplay_ms: int = 900,
):
    sess = Session(
        seed=seed, episode=episode, persona=persona,
        method=method, gbm_threshold=gbm_threshold,
    )

    # ---- top branding bar --------------------------------------------------
    with ui.element("div").classes("w-full bg-sky-600 text-white px-6 py-3 shadow"):
        with ui.row().classes("w-full items-center max-w-5xl mx-auto"):
            ui.label("HealthCover").classes("text-2xl font-bold tracking-tight")
            ui.label("private medical insurance").classes("text-sky-100 text-sm ml-2")
            ui.element("div").classes("flex-grow")
            ui.label("Need help? 0800 123 456").classes("text-sm")

    # ---- demo / narration strip (above the page area) ----------------------
    if narration:
        ui.label(narration).props('id="journey-narration"').classes(
            "max-w-5xl mx-auto mt-2 px-6 italic text-sky-900 text-sm"
        )
    else:
        # always render the element so tests can target it even when empty
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

    # ---- page content area -------------------------------------------------
    page_container = ui.column().props('id="journey-page"').classes(
        "max-w-3xl mx-auto mt-6 px-6 pb-12 w-full"
    )

    # ---- popup overlay -----------------------------------------------------
    def close_popup():
        popup.close()

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
            ui.button("Got it", on_click=close_popup).props(
                'id="journey-popup-close" flat'
            ).classes("bg-sky-600 text-white px-4")

    # ---- per-step page renderers -------------------------------------------
    def _h1(text: str):
        ui.label(text).classes("text-3xl font-bold text-gray-900 mb-2")

    def _subtitle(text: str):
        ui.label(text).classes("text-base text-gray-600 mb-6")

    def _option_card(title: str, sub: str, selected: bool = False, advisory: bool = False):
        cls = "p-5 rounded-lg border-2 transition-all flex-1 min-w-48 max-w-72 "
        if selected:
            cls += "border-sky-600 bg-sky-50 shadow-md "
        elif advisory:
            cls += "border-amber-300 bg-amber-50 "
        else:
            cls += "border-gray-200 bg-white "
        with ui.element("div").classes(cls):
            ui.label(title).classes("text-lg font-semibold mb-1")
            ui.label(sub).classes("text-sm text-gray-600")

    def _render_start():
        _h1("Health insurance, online in minutes")
        _subtitle("A personalised quote in under five minutes. No paperwork. "
                  "No phone calls unless you want them.")
        with ui.row().classes("mt-8"):
            ui.button("Get a quote").props("disable").classes(
                f"{BRAND_PRIMARY} text-white px-8 py-3 text-base font-semibold"
            )

    def _render_s1_coverage():
        _h1("What kind of coverage are you looking for?")
        _subtitle("You can change this later. We'll tailor the rest of the journey.")
        with ui.row().classes("gap-4 mt-6 flex-wrap"):
            _option_card("Private doctor visits",
                         "Outpatient care, specialists, diagnostics, therapies.",
                         selected=True)
            _option_card("Hospital stay",
                         "Inpatient care, surgery, private room. Advisory.",
                         advisory=True)
            _option_card("Both",
                         "Comprehensive coverage. Advisory.",
                         advisory=True)

    def _render_s2_for_whom():
        _h1("Who would you like to insure?")
        _subtitle("")
        with ui.row().classes("gap-4 mt-6"):
            _option_card("Just me", "Personal coverage.", selected=True)
            _option_card("Family or other persons",
                         "Coverage for multiple people. Advisory.",
                         advisory=True)

    def _render_s3_personal():
        _h1("Tell us a bit about yourself")
        _subtitle("We need a couple of basics before we can show you a price.")
        with ui.column().classes("gap-4 mt-4 max-w-md"):
            ui.input(label="Date of birth", value="15.07.1985").props("disable outlined").classes("w-full")
            ui.input(label="Social insurance number",
                     value="1234 150785").props("disable outlined").classes("w-full")

    def _render_s4_tariff():
        _h1("Choose your tariff")
        _subtitle("Two tariffs you can buy online; two require a short advisory call.")
        with ui.row().classes("gap-3 mt-6 flex-wrap"):
            _tariff_card("Start", "€38.74 / mo",
                         "Outpatient essentials. Fully online.",
                         online=True, selected=(sess.last_action and
                                                sess.last_action.target == "Start"))
            _tariff_card("Optimal", "€68.14 / mo",
                         "Outpatient + therapies + medications. Fully online.",
                         online=True, badge="Popular",
                         selected=(sess.last_action and
                                   sess.last_action.target == "Optimal"))
            _tariff_card("Opt. Plus", "Advisory",
                         "Adds private hospital. Requires a short call.",
                         online=False)
            _tariff_card("Premium", "Advisory",
                         "Top-tier coverage. Requires a short call.",
                         online=False)

    def _tariff_card(name, price, body, online: bool, badge: str = "",
                     selected: bool = False):
        ring = "border-sky-600 bg-sky-50 shadow-md" if selected else (
            "border-amber-300 bg-amber-50" if not online else
            "border-gray-200 bg-white"
        )
        with ui.element("div").classes(
            f"p-4 rounded-lg border-2 flex-1 min-w-44 max-w-60 {ring}"
        ):
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

    def _render_s6_health():
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
                ui.radio(["Yes", "No"], value="No").props(
                    "disable inline"
                ).classes("text-sm")

    def _selected_tariff_name() -> str:
        # the selected tariff name is determined by which price the simulator
        # bound to `provisional` at S4 (sess.provisional). 38.74 -> Start,
        # 68.14 -> Optimal. Fallback to Optimal if no selection happened yet.
        p = sess.provisional
        if p is None:
            return "Optimal"
        if abs(p - 38.74) < 0.01:
            return "Start"
        if abs(p - 68.14) < 0.01:
            return "Optimal"
        return "Optimal"

    def _render_s7_final():
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

    def _render_s12_closing():
        provisional = sess.provisional or 68.14
        final = round(provisional * (1 + sess.surcharge), 2)
        _h1("Review and confirm")
        _subtitle("Almost done.")
        tariff = _selected_tariff_name()
        rows = [
            ("Plan", tariff),
            ("Monthly", f"€{final:.2f}"),
            ("Billing", "Monthly, paperless"),
            ("Coverage starts", "Next month"),
        ]
        for k, v in rows:
            with ui.row().classes("py-2 border-b border-gray-100"):
                ui.label(k).classes("w-40 text-gray-600")
                ui.label(v).classes("font-semibold text-gray-900")
        ui.checkbox("I agree to the terms and the privacy notice").props("disable").classes("mt-4")
        ui.button("Confirm and purchase").props("disable").classes(
            f"{BRAND_PRIMARY} text-white px-6 py-2 font-semibold mt-4"
        )

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

    STEP_RENDERERS = {
        0: _render_start, 1: _render_s1_coverage, 2: _render_s2_for_whom,
        3: _render_s3_personal, 4: _render_s4_tariff, 6: _render_s6_health,
        7: _render_s7_final, 12: _render_s12_closing,
    }

    # ---- driver loop -------------------------------------------------------
    autoplay_timer = {"t": None}

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
            else:
                renderer = STEP_RENDERERS.get(cur)
                if renderer:
                    renderer()

    def render_for_step(cur: int):
        paint_progress(cur)
        paint_page(cur)

    def stop_autoplay():
        if autoplay_timer["t"] is not None:
            autoplay_timer["t"].deactivate()
            autoplay_timer["t"] = None

    def tick():
        if sess.is_done():
            stop_autoplay()
            return
        prev_state = int(sess.state)
        result = sess.step_once()
        if result and result["intervention"] is not None:
            iv = result["intervention"]
            # show the page for the FIRE step (state already advanced underneath)
            render_for_step(iv.step)
            popup_type.set_text(f"{iv.type}  ·  {iv.mode}")
            popup_text.set_text(iv.text)
            stop_autoplay()   # pause for audience read; resume on close
            popup.open()
            return
        if int(sess.state) != prev_state:
            render_for_step(int(sess.state))
        if sess.is_done():
            stop_autoplay()
            render_for_step(int(sess.state))

    def resume_after_popup():
        popup.close()
        # paint the actual post-action state (may be terminal)
        render_for_step(int(sess.state))
        if not sess.is_done() and autoplay_switch.value:
            autoplay_timer["t"] = ui.timer(autoplay_ms / 1000.0, tick)

    # rewire popup close to resume auto-play
    popup.on("hide", resume_after_popup)

    def toggle_autoplay(e):
        if e.value and not sess.is_done():
            autoplay_timer["t"] = ui.timer(autoplay_ms / 1000.0, tick)
        else:
            stop_autoplay()

    # ---- footer controls ---------------------------------------------------
    with ui.row().classes("max-w-5xl mx-auto mt-6 px-6 gap-3 items-center "
                          "border-t border-gray-200 pt-4 w-full"):
        autoplay_switch = ui.switch("Auto-play", value=True,
                                    on_change=toggle_autoplay).props(
            'id="journey-autoplay-toggle"'
        )
        ui.select(
            options=["judith", "franz", "peter", "global"], value=persona,
            on_change=lambda e: ui.navigate.to(
                f"/journey?seed={seed}&episode={episode}"
                f"&persona={e.value}&method={method}&gbm_threshold={gbm_threshold}"
            ),
        ).props('id="journey-persona-select"').classes("w-40")
        ui.select(
            options=["threshold", "gbm"], value=method,
            on_change=lambda e: ui.navigate.to(
                f"/journey?seed={seed}&episode={episode}"
                f"&persona={persona}&method={e.value}&gbm_threshold={gbm_threshold}"
            ),
        ).props('id="journey-method-select"').classes("w-40")
        ui.element("div").classes("flex-grow")
        ui.link("→ debug view", f"/?seed={seed}&episode={episode}"
                f"&persona={persona}&method={method}").classes(
            "text-sm text-sky-700 underline"
        )
        ui.label(
            f"seed={seed}  ep={episode}  detector={method}"
        ).classes("text-xs text-gray-500 font-mono")

    # initial paint
    render_for_step(int(sess.state))

    # kick off auto-play
    if autoplay_switch.value:
        autoplay_timer["t"] = ui.timer(autoplay_ms / 1000.0, tick)
