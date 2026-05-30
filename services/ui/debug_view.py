"""Debug viewer at `/` - the original Phase 3.5 view (BUILD_SPEC §Phase 3.5).

Renders a funnel strip + live `Signals` panel + popup-on-coach-fire. Useful for
development, debugging detection thresholds, and for the regression test suite.
The customer-facing rebuild lives at `/journey` (see `journey_view.py`).

Stable element IDs (test contract; renaming any is a spec change):
  step-button, autoplay-toggle, persona-select, method-select,
  intervention-modal, intervention-type, intervention-reason, intervention-text,
  intervention-close, funnel-current-step, narration, terminal-banner
"""
from __future__ import annotations

from nicegui import run, ui

from services.ui.session import Session


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


def render(
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

    with ui.row().classes("w-full items-center gap-4"):
        ui.label("Conversion Coach — debug").classes("text-2xl font-bold")
        ui.label(
            f"persona={persona}  method={method}  seed={seed}  ep={episode}"
        ).classes("text-sm text-gray-600 font-mono")
        ui.link("→ customer view", f"/journey?seed={seed}&episode={episode}"
                f"&persona={persona}&method={method}").classes("text-sm text-blue-600 underline ml-auto")
    ui.label(narration).props('id="narration"').classes(
        "italic text-base text-blue-800 min-h-6"
    )

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

    ui.label("Live signals").classes("text-lg font-semibold mt-4")
    signals_panel = ui.column().classes("font-mono text-sm")

    def on_modal_close():
        modal.close()
        refresh_funnel()
        refresh_signals()

    with ui.dialog().props('id="intervention-modal"') as modal, ui.card().classes("min-w-96"):
        ui.label("Coach intervention").classes("text-xl font-bold")
        ui.separator()
        type_label = ui.label("").props('id="intervention-type"').classes("text-sm font-mono text-gray-600")
        reason_label = ui.label("").props('id="intervention-reason"').classes("text-sm font-mono text-gray-600")
        text_label = ui.label("").props('id="intervention-text"').classes("text-base mt-3")
        ui.button("Close", on_click=on_modal_close).props('id="intervention-close"').classes("mt-3")

    autoplay_timer = {"t": None}

    def _show_funnel_step(cur: int):
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

    async def do_step():
        if sess.is_done():
            stop_autoplay()
            return
        # step_once internally consults the coach which in LLM mode hits the
        # inference endpoint. Wrap in run.io_bound so the WebSocket heartbeat
        # stays alive even if the inference call takes a second or two.
        result = await run.io_bound(sess.step_once)
        if result and result["intervention"] is not None:
            iv = result["intervention"]
            _show_funnel_step(iv.step)
            refresh_signals()
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

    refresh_funnel()
    refresh_signals()
