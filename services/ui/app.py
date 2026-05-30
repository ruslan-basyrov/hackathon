"""NiceGUI viewer for the Conversion Coach (BUILD_SPEC §Phase 3.5).

A thin window over the existing `coach()`. Pops up a `ui.dialog` whenever the
coach fires for the current step. The URL contract `?seed=&episode=&persona=&method=`
is the same contract the headed demo and any future headless tests bind to -
the on-disk config is never mutated.

Stable element IDs (the test contract; renaming any of these is a spec change):
  * `step-button`          - advance one action
  * `autoplay-toggle`      - timed advance (off by default; MUST be off in tests)
  * `persona-select`       - persona switcher
  * `method-select`        - threshold | gbm switcher
  * `intervention-modal`   - the popup
  * `intervention-type`    - intervention type label inside the popup
  * `intervention-reason`  - detection reason inside the popup
  * `intervention-text`    - realize() output inside the popup
  * `intervention-close`   - dismiss the popup
  * `funnel-current-step`  - current step label, e.g. "S4 Initial Price"
  * `narration`            - on-screen narration for the demo path
  * `terminal-banner`      - shown when the episode reaches a terminal state
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# project root must be on sys.path when run as a module (NiceGUI reloads the file)
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from nicegui import ui  # noqa: E402

from services.ui.session import Session  # noqa: E402


STEP_LABEL = {
    0: "Start",
    1: "S1 Coverage Type",
    2: "S2 For Whom",
    3: "S3 Personal Data",
    4: "S4 Initial Price",
    6: "S6 Health Questions",
    7: "S7 Final Price",
    12: "S12 Closing",
    90: "Converted",
    91: "Abandoned",
    92: "Routed to Advisor",
    93: "Service Contact",
}
IN_SCOPE_PATH = [0, 1, 2, 3, 4, 6, 7, 12]
TERMINALS = {90, 91, 92, 93}


@ui.page("/")
def index(
    seed: int = 0,
    episode: int = 0,
    persona: str = "judith",
    method: str = "threshold",
    gbm_threshold: float = 0.85,
    narration: str = "",
):
    sess = Session(
        seed=seed, episode=episode, persona=persona,
        method=method, gbm_threshold=gbm_threshold,
    )

    # ---- header / narration ------------------------------------------------
    with ui.row().classes("w-full items-center gap-4"):
        ui.label("Conversion Coach").classes("text-2xl font-bold")
        ui.label(
            f"persona={persona}  method={method}  seed={seed}  ep={episode}"
        ).classes("text-sm text-gray-600 font-mono")
    ui.label(narration).props('id="narration"').classes(
        "italic text-base text-blue-800 min-h-6"
    )

    # ---- funnel panel ------------------------------------------------------
    ui.label("Journey").classes("text-lg font-semibold mt-4")
    funnel_chips = {}
    with ui.row().classes("gap-2 flex-wrap"):
        for st in IN_SCOPE_PATH:
            chip = ui.label(STEP_LABEL[st]).classes(
                "px-3 py-1 rounded border border-gray-300 text-sm"
            )
            funnel_chips[st] = chip

    current_step_label = ui.label(
        f"Current: {STEP_LABEL[int(sess.state)]}"
    ).props('id="funnel-current-step"').classes("mt-2 text-base font-semibold")

    terminal_banner = ui.label("").props('id="terminal-banner"').classes(
        "mt-1 text-base font-bold text-emerald-700"
    )

    # ---- signals panel -----------------------------------------------------
    ui.label("Live signals").classes("text-lg font-semibold mt-4")
    signals_panel = ui.column().classes("font-mono text-sm")

    # ---- intervention popup ------------------------------------------------
    def on_modal_close():
        modal.close()
        # funnel was frozen on the fire step while the popup was open;
        # now reflect whatever state the simulator actually advanced to
        refresh_funnel()
        refresh_signals()

    with ui.dialog().props('id="intervention-modal"') as modal, ui.card().classes("min-w-96"):
        ui.label("Coach intervention").classes("text-xl font-bold")
        ui.separator()
        type_label = ui.label("").props('id="intervention-type"').classes("text-sm font-mono text-gray-600")
        reason_label = ui.label("").props('id="intervention-reason"').classes("text-sm font-mono text-gray-600")
        text_label = ui.label("").props('id="intervention-text"').classes("text-base mt-3")
        ui.button("Close", on_click=on_modal_close).props('id="intervention-close"').classes("mt-3")

    # ---- step / autoplay controls ------------------------------------------
    autoplay_timer = {"t": None}

    def _show_funnel_step(cur: int):
        """Paint the funnel for an arbitrary step (not necessarily sess.state).
        Used to freeze the funnel on the fire step while a popup is open."""
        for st, chip in funnel_chips.items():
            if st == cur:
                chip.classes(replace="px-3 py-1 rounded text-sm bg-blue-500 text-white font-semibold")
            else:
                chip.classes(replace="px-3 py-1 rounded border border-gray-300 text-sm")
        current_step_label.set_text(f"Current: {STEP_LABEL.get(cur, str(cur))}")
        if cur in TERMINALS:
            terminal_banner.set_text(f"Episode ended: {STEP_LABEL[cur]}")
        else:
            terminal_banner.set_text("")

    def refresh_funnel():
        _show_funnel_step(int(sess.state))

    def refresh_signals():
        signals_panel.clear()
        sig = sess.last_signal
        with signals_panel:
            if sig is None:
                ui.label("(no actions yet)").classes("text-gray-500")
                return
            for k, v in [
                ("step", sig.step),
                ("steps_completed", sig.steps_completed),
                ("dwell_current_s", f"{sig.dwell_current_s:.1f}"),
                ("dwell_total_s", f"{sig.dwell_total_s:.1f}"),
                ("back_nav_count", sig.back_nav_count),
                ("field_change_count", sig.field_change_count),
                ("tariff_hover_count", sig.tariff_hover_count),
                ("advisory_tariff_clicked", sig.advisory_tariff_clicked),
                ("tariff_selected", sig.tariff_selected),
                ("external_tab_opens", sig.external_tab_opens),
                ("price_gap_eur", f"{sig.price_gap_eur:.2f}"),
                ("hover_cancel_count", sig.hover_cancel_count),
            ]:
                ui.label(f"{k:25s} {v}")

    def stop_autoplay():
        if autoplay_timer["t"] is not None:
            autoplay_timer["t"].deactivate()
            autoplay_timer["t"] = None

    def do_step():
        if sess.is_done():
            stop_autoplay()
            return
        result = sess.step_once()
        if result and result["intervention"] is not None:
            iv = result["intervention"]
            # Freeze the funnel on the fire step. The simulator has already
            # advanced (and may even be terminal, e.g. Franz S7 abandonment),
            # but the popup is the artifact of THIS step - we restore the
            # post-state when the user dismisses the modal.
            _show_funnel_step(iv.step)
            refresh_signals()  # last_signal is the pre-action signal
            type_label.set_text(f"type: {iv.type}   step: {iv.step}   mode: {iv.mode}")
            reason_label.set_text(f"detector: {sess.cfg['detection']['method']}")
            text_label.set_text(iv.text)
            stop_autoplay()
            modal.open()
        else:
            refresh_funnel()
            refresh_signals()
        if sess.is_done():
            stop_autoplay()

    def toggle_autoplay(e):
        if e.value:
            autoplay_timer["t"] = ui.timer(0.6, do_step)
        else:
            stop_autoplay()

    with ui.row().classes("mt-4 gap-2 items-center"):
        ui.button("Step", on_click=do_step).props('id="step-button"').classes("bg-blue-600 text-white")
        ui.switch("Auto-play", on_change=toggle_autoplay).props('id="autoplay-toggle"')
        ui.select(
            options=["judith", "franz", "peter", "global"],
            value=persona,
            on_change=lambda e: ui.navigate.to(
                f"?seed={seed}&episode={episode}&persona={e.value}&method={method}&gbm_threshold={gbm_threshold}"
            ),
        ).props('id="persona-select"').classes("w-40")
        ui.select(
            options=["threshold", "gbm"],
            value=method,
            on_change=lambda e: ui.navigate.to(
                f"?seed={seed}&episode={episode}&persona={persona}&method={e.value}&gbm_threshold={gbm_threshold}"
            ),
        ).props('id="method-select"').classes("w-40")

    # initial paint
    refresh_funnel()
    refresh_signals()


def main():
    port = int(os.environ.get("NICEGUI_PORT", "8080"))
    ui.run(
        port=port,
        show=False,
        reload=False,
        title="Conversion Coach",
        favicon=None,
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()
