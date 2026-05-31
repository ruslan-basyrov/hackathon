"""Customer-facing journey at `/journey` (BUILD_SPEC §Phase 3.5).

A stylized "HealthCover" insurance signup, skinned with the **"Warm"** design
system in `design_idea/healthcover-warm.css` (UNIQA-style deep blue + warm
cream + amber). Three driver modes share the same visual layout and `Session`:

  * **auto mode** (default, `?mode=auto`) - `StubAgent` drives via auto-play;
    the audience watches a persona traverse the funnel; popups overlay on
    coach fire. This is the on-stage demo path.

  * **interactive mode** (`?mode=interactive`) - the human is the user. Every
    interactive element is clickable and builds a real `Action`; wall-clock
    dwell feeds the signals; a watchdog timer consults the coach every second
    so dwell-based interventions fire while you sit on a page.

  * **live mode** (`?mode=live`) - `LLMBot` drives via auto-play in the
    `SimulationEngine`; similar to auto mode but uses the actual LLM bot
    and intervention logic from the engine.

Presentation only: this module reads the simulator (`coach()` / `extract()`),
it never computes conversion. The funnel screens + coach popup wear the warm
skin; the presenter chrome (rules panel, mode/persona/method switchers, quick
scenarios) lives below the cream surface as plain dev tooling.

Stable element IDs (test contract - keep on the matching nodes):
  journey-page, journey-step-label, journey-progress, journey-narration,
  journey-popup, journey-popup-type, journey-popup-text, journey-popup-close,
  journey-popup-continue, journey-chat-log, journey-chat-input, journey-chat-send,
  journey-autoplay-toggle, journey-step-button, journey-persona-select,
  journey-method-select, journey-mode-toggle, journey-live-toggle,
  journey-quick-judith, journey-quick-franz, journey-quick-peter, journey-rules,
  journey-back, journey-continue, journey-cancel-link, journey-edit-dob,
  journey-card-doctor, journey-card-hospital, journey-card-both,
  journey-card-myself, journey-card-others,
  journey-tariff-Start, journey-tariff-Optimal, journey-tariff-OptPlus,
  journey-tariff-Premium
"""
from __future__ import annotations

from pathlib import Path

from nicegui import run, ui

from services.ui.session import Session
from state_machine import Action


# Step int -> page title (used for the progress label on terminal pages).
PAGE_TITLES = {
    0: "Welcome", 1: "What kind of coverage?", 2: "Who is this for?",
    3: "Your details", 4: "Choose your tariff", 6: "A few health questions",
    7: "Your personalised price", 12: "Confirm and finish",
    90: "You’re covered", 91: "Session ended",
    92: "An advisor will be in touch", 93: "We’ll call you back",
}
FUNNEL_STEPS = [1, 2, 3, 4, 6, 7, 12]
TERMINALS = {90, 91, 92, 93}

# Presenter-chrome accent (the dev tooling below the cream surface only).
BRAND_PRIMARY = "bg-sky-600"

# --- warm design system assets ---------------------------------------------
_CSS_PATH = Path(__file__).parent / "static" / "healthcover-warm.css"

_FONTS_HEAD = (
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?'
    'family=Hanken+Grotesk:wght@400;500;600;700;800&'
    'family=Source+Serif+4:opsz,wght@8..60,400;8..60,600;8..60,700&'
    'family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">'
)

# Adapt the fixed-frame reference to a full-page NiceGUI route and tame Quasar
# defaults that fight the design. Kept here (not in healthcover-warm.css) so the
# design file stays the pristine source of truth.
_OVERRIDES = """
.nicegui-content{padding:0 !important;gap:0 !important;width:100%;max-width:100%}
body{background:var(--hc-cream)}
.hc-scr{height:auto;min-height:100vh}
.hc-main{overflow:visible}
.hc-cont:disabled,.hc-back:disabled,.hc-pick:disabled{opacity:.45;cursor:default}
.hc-narration{margin:10px 40px 0;font-style:italic;color:var(--hc-blue-900);font-size:13.5px}
.hc-mode-chip{font:600 11px var(--hc-font-mono);letter-spacing:.04em;background:var(--hc-amber-soft);color:var(--hc-amber-700);padding:4px 10px;border-radius:var(--hc-r-pill)}
.hc-mode-chip.live{background:var(--hc-amber);color:#3a2a08}
/* coach reply: make the NiceGUI/Quasar input read like .hc-reply input */
.hc-reply{align-items:center}
.hc-reply .q-field{flex:1;min-width:0}
.hc-reply .q-field__control{min-height:42px;height:42px;border-radius:var(--hc-r-pill);background:var(--hc-surface);border:1px solid var(--hc-cream-line);padding:0 14px}
.hc-reply .q-field__control:before,.hc-reply .q-field__control:after{display:none !important}
.hc-reply input{border:none !important;height:auto !important;padding:0 !important;background:transparent !important}
"""

_LOGO_SVG = (
    '<span class="hc-brand">'
    '<svg width="28" height="28" viewBox="0 0 28 28">'
    '<rect width="28" height="28" rx="8" fill="#0a51d0"/>'
    '<rect x="12.4" y="6.5" width="3.2" height="15" rx="1.6" fill="#fff"/>'
    '<rect x="6.5" y="12.4" width="15" height="3.2" rx="1.6" fill="#fff"/>'
    '</svg><b>Health<span>Cover</span></b></span>'
)

_SPARK_SVG = (
    '<span class="spark"><svg width="14" height="14" viewBox="0 0 14 14">'
    '<path d="M7 0l1.6 4.2L13 5.6 9 7.8 8.2 12 7 8.6 4 11l1-4L0 5.4l4.8-.5z" '
    'fill="currentColor"/></svg></span>'
)

# Per-persona popup action labels: (primary / continue, secondary / branch).
# The primary keeps id=journey-popup-continue and advances; the ghost is the
# persona-specific branch (Judith soft handoff, Franz cheaper option, Peter
# callback). Both close the popup (the UI stays read-only over the simulator).
_ACTION_LABELS = {
    "judith": ("Continue with Optimal", "Book a 10-min call"),
    "franz": ("Keep my Optimal plan", "Show a cheaper tariff"),
    "peter": ("Continue online", "Yes, call me back"),
}

# Judith's rich attachment on her first nudge bubble: the €/day reframe + a
# market-comparison. Illustrative marketing copy (€2.27/day = €68.14/mo for
# Optimal); the funnel's own prices stay bound to the simulator.
_JUDITH_RICH = (
    '<div class="rich">'
    '<div class="hc-perday"><span class="big">€2.27</span>'
    '<span class="cap">per day for <b>Optimal</b> — <b>€68.14</b>/mo, cancel anytime.</span></div>'
    '<div class="hc-cmp">'
    '<div class="row you"><span class="rl">HealthCover</span>'
    '<span class="track"><span class="fill" style="width:70%"></span></span><span class="rv">€68</span></div>'
    '<div class="row mkt"><span class="rl">Market avg.</span>'
    '<span class="track"><span class="fill" style="width:86%"></span></span><span class="rv">€81</span></div>'
    '</div></div>'
)


def render(
    seed: int = 0,
    episode: int = 0,
    persona: str = "judith",
    method: str = "llm",
    gbm_threshold: float = 0.85,
    narration: str = "",
    autoplay_ms: int = 900,
    mode: str = "auto",
):
    interactive = (mode == "interactive")
    live = (mode == "live")
    sess = Session(
        seed=seed, episode=episode, persona=persona,
        method=method, gbm_threshold=gbm_threshold, mode=mode,
    )

    def _scenario_url(p: str, ep: int) -> str:
        return (f"/journey?seed={seed}&episode={ep}"
                f"&persona={p}&method={method}&gbm_threshold={gbm_threshold}"
                f"&mode={mode}")

    # ---- load the warm design system (this page only) ----------------------
    ui.add_head_html(_FONTS_HEAD)
    ui.add_css(_CSS_PATH.read_text())
    ui.add_css(_OVERRIDES)

    # ========================================================================
    # CUSTOMER-FACING SURFACE (.hc-scr) — top bar, progress, page, footer
    # ========================================================================
    with ui.element("div").classes("hc-scr"):
        # ---- top bar -------------------------------------------------------
        with ui.element("div").classes("hc-top"):
            ui.html(_LOGO_SVG)
            with ui.element("div").classes("hc-top-right"):
                with ui.element("div").classes("hc-personas"):
                    for p in ("judith", "franz", "peter"):
                        pill = ui.element("button").classes(
                            "hc-pl on" if p == persona else "hc-pl"
                        )
                        with pill:
                            ui.element("span").classes(f"pd {p}")
                            ui.label(p.title())
                        pill.on("click", lambda _=None, pp=p:
                                ui.navigate.to(_scenario_url(pp, episode)))
                if interactive:
                    ui.label("manual mode").classes("hc-mode-chip")
                elif live:
                    ui.label("live · LLM driving").classes("hc-mode-chip live")
                ui.html('<span class="hc-help"><span class="dot"></span>Coach active</span>')

        # ---- narration -----------------------------------------------------
        if narration:
            ui.label(narration).props('id="journey-narration"').classes("hc-narration")
        else:
            ui.label("").props('id="journey-narration"').classes("hidden")

        # ---- progress (segments hidden on welcome/terminal; label always on
        #      so #journey-step-label stays visible for the load test) -------
        prog_row = ui.element("div").props('id="journey-progress"').classes("hc-prog")
        with prog_row:
            progress_segs = [ui.element("span").classes("seg") for _ in FUNNEL_STEPS]
            progress_label = ui.label("").props('id="journey-step-label"').classes("lbl")

        # ---- per-step page root (the .hc-main content area) ----------------
        page_container = ui.element("div").props('id="journey-page"').classes("hc-main")

        # ---- footer (Back / Continue; repainted per step) ------------------
        footer_container = ui.element("div").classes("hc-foot")

    # ========================================================================
    # COACH NUDGE POPUP — conversational chat (styled to .hc-modal)
    # ========================================================================
    # Kept as a ui.dialog (the README sanctions "ui.dialog styled to .hc-modal")
    # so the existing .open()/.close()/on("hide") resume machinery is preserved.
    with ui.dialog().props('id="journey-popup"') as popup:
        with ui.element("div").classes("hc-modal"):
            with ui.element("div").classes("hc-nudge-head"):
                ui.html(_SPARK_SVG)
                ui.html('<span><div class="hc-nudge-kicker">Smart assist</div>'
                        '<div class="hc-nudge-from">A nudge from HealthCover</div></span>')
                ui.html(f'<span class="hc-nudge-persona"><span class="pd {persona}"></span>'
                        f'{persona.title()}</span>')
                close_btn = ui.element("button").classes("hc-close").props(
                    'id="journey-popup-close"'
                )
                with close_btn:
                    ui.html("&times;")
                close_btn.on("click", lambda: popup.close())

            popup_type = ui.label("").props('id="journey-popup-type"').classes("hc-nudge-type")

            chat_log = ui.element("div").props('id="journey-chat-log"').classes("hc-chat")

            chat_busy = ui.element("div").classes("hc-think hidden")
            with chat_busy:
                ui.html('<span class="hc-spin"></span>')
                ui.label("thinking …")

            reply_row = ui.element("div").classes("hc-reply")
            with reply_row:
                chat_input = ui.input(placeholder="Reply to the coach…").props(
                    'id="journey-chat-input" borderless dense'
                ).classes("flex-grow")
                chat_send = ui.element("button").classes("send").props(
                    'id="journey-chat-send"'
                )
                with chat_send:
                    ui.label("Send")

            with ui.element("div").classes("hc-actions"):
                primary = ui.element("button").classes("primary").props(
                    'id="journey-popup-continue"'
                )
                with primary:
                    primary_label = ui.label("Continue journey")
                primary.on("click", lambda: popup.close())
                ghost_btn = ui.element("button").classes("ghost")
                with ghost_btn:
                    ghost_label = ui.label("")
                ghost_btn.on("click", lambda: popup.close())

    # ---- chat state + logic (unchanged behaviour) --------------------------
    # `messages` is the full OpenAI-style history we SEND to the model:
    # build_messages(itype, sig, persona) gives [system, prompt-scaffold-user];
    # we then append the first assistant nudge and each follow-up turn.
    # `visible_start` is the index where the chat UI begins rendering — the
    # system message + structured prompt user message are scaffolding the user
    # must NEVER see. The first rendered bubble is the assistant's nudge.
    chat_state = {"messages": [], "busy": False, "visible_start": 0, "itype": None}

    def _set_busy(busy: bool):
        chat_state["busy"] = busy
        if busy:
            chat_input.props("disable")        # Quasar input prop
            chat_send.props("disabled")        # native <button> attribute
            chat_busy.classes(remove="hidden")
        else:
            chat_input.props(remove="disable")
            chat_send.props(remove="disabled")
            chat_busy.classes(add="hidden")

    def _render_chat():
        chat_log.clear()
        first_assistant_seen = False
        with chat_log:
            for msg in chat_state["messages"][chat_state["visible_start"]:]:
                role = msg["role"]
                text = msg["content"]
                if role == "assistant":
                    is_first = not first_assistant_seen
                    if is_first:
                        first_assistant_seen = True
                    # Judith's first nudge carries the €/day + market-bar rich
                    # attachment, but only on her actual price reframe (not a
                    # generic nudge like back_nav_help); everyone else gets a
                    # plain bubble.
                    if (is_first and sess.persona == "judith"
                            and chat_state.get("itype") == "price_reframe"):
                        bubble = ui.element("div").classes("hc-msg bot").props(
                            'id="journey-popup-text"'
                        )
                        with bubble:
                            ui.label(text)
                            ui.html(_JUDITH_RICH)
                    else:
                        lbl = ui.label(text).classes("hc-msg bot")
                        if is_first:
                            lbl.props('id="journey-popup-text"')
                elif role == "user":
                    ui.label(text).classes("hc-msg user")

    def open_chat(intervention, sig):
        """Seed the chat with the persona/intervention prompt + the first
        assistant nudge that `realize()` just produced, then open the dialog."""
        from coach.llm_realize import build_messages
        if isinstance(sig, dict):
            from signals import Signals
            _sig = Signals(
                step=sig.get('step', 0),
                max_steps_completed=sig.get('max_steps_completed', 0),
                dwell_current_s=sig.get('dwell_current_s', 0.0),
                dwell_total_s=sig.get('dwell_total_s', 0.0),
                time_since_last_action_s=sig.get('time_since_last_action_s', 0.0),
                back_nav_count=sig.get('back_nav_count', 0),
                back_from_step=sig.get('back_from_step', None),
                field_change_count=sig.get('field_change_count', 0),
                tariff_hover_count=sig.get('tariff_hover_count', 0),
                advisory_tariff_clicked=sig.get('advisory_tariff_clicked', False),
                tariff_selected=sig.get('tariff_selected', None),
                external_tab_opens=sig.get('external_tab_opens', 0),
                price_gap_eur=sig.get('price_gap_eur', 0.0),
                hover_cancel_count=sig.get('hover_cancel_count', 0)
            )
            sig = _sig

        if live and hasattr(sess.last_intervention, 'chat_history') and sess.last_intervention.chat_history:
            chat_state["messages"] = sess.last_intervention.chat_history
            chat_state["visible_start"] = 0
        else:
            history = build_messages(intervention.type, sig, sess.persona)
            chat_state["visible_start"] = len(history)
            history.append({"role": "assistant", "content": intervention.text})
            chat_state["messages"] = history

        chat_state["itype"] = intervention.type
        chat_input.value = ""
        _set_busy(False)
        # only allow chat in LLM mode; in template mode there's no backend to
        # answer a follow-up, so hide the reply row entirely.
        is_llm = (sess.cfg.get("realize", {}) or {}).get("method") == "llm" or live
        reply_row.set_visibility(is_llm)
        # persona-specific action labels
        pri, gho = _ACTION_LABELS.get(sess.persona, ("Continue journey", ""))
        primary_label.set_text(pri)
        if gho:
            ghost_label.set_text(gho)
            ghost_btn.set_visibility(True)
        else:
            ghost_btn.set_visibility(False)
        popup_type.set_text(f"{intervention.type}  ·  {intervention.mode}")
        _render_chat()
        popup.open()

    async def send_chat(_=None):
        # `_` swallows the event object NiceGUI passes through `.on()`.
        text = (chat_input.value or "").strip()
        if not text or chat_state["busy"]:
            return
        chat_state["messages"].append({"role": "user", "content": text})
        chat_input.value = ""
        _render_chat()
        _set_busy(True)
        try:
            from coach.llm_realize import chat_followup
            reply = await run.io_bound(chat_followup, chat_state["messages"], sess.cfg)
            chat_state["messages"].append({"role": "assistant", "content": reply})
        except Exception as e:  # network/timeout/empty - surface, don't crash UI
            chat_state["messages"].append(
                {"role": "assistant", "content": f"[chat unavailable: {e}]"}
            )
        finally:
            _set_busy(False)
            _render_chat()

    chat_send.on("click", send_chat)
    chat_input.on("keydown.enter", send_chat)

    # ---- presentation helpers ----------------------------------------------
    def _intro(eyebrow: str, h1: str, sub: str, *, serif: bool = False):
        h1_style = (' style="font-family:var(--hc-font-serif);font-size:46px;max-width:640px"'
                    if serif else "")
        sub_style = ' style="font-size:17px"' if serif else ""
        ui.html(f'<div class="hc-eyebrow">{eyebrow}</div>'
                f'<h1 class="hc-h1"{h1_style}>{h1}</h1>'
                f'<p class="hc-sub"{sub_style}>{sub}</p>')

    def _selected_tariff_name() -> str:
        p = sess.provisional
        if p is None:
            return "Optimal"
        if abs(p - 38.74) < 0.01:
            return "Start"
        return "Optimal"

    def _option_card(title: str, sub: str, *, selected: bool = False,
                     on_click=None, elem_id: str = ""):
        card = ui.element("div").classes("hc-opt sel" if selected else "hc-opt")
        if elem_id:
            card.props(f'id="{elem_id}"')
        if on_click is not None:
            card.on("click", lambda _=None, h=on_click: h())
            card.style("cursor:pointer")
        ck = "✓ Selected" if selected else "Choose"
        with card:
            ui.html(f'<div class="pic hc-img">lifestyle photo</div>'
                    f'<div class="body"><div class="ot">{title}</div>'
                    f'<div class="od">{sub}</div></div>'
                    f'<div class="ck">{ck}</div>')

    def _tariff_card(name: str, tier: str, price: str, per: str, feats: list[str],
                     *, rec: bool = False, adv: bool = False, on_click=None,
                     elem_id: str = "", pick_label: str = "Select"):
        cls = "hc-card" + (" is-rec" if rec else "") + (" is-adv" if adv else "")
        card = ui.element("div").classes(cls)
        if elem_id:
            card.props(f'id="{elem_id}"')
        if on_click is not None:
            card.on("click", lambda _=None, h=on_click: h())
            card.style("cursor:pointer")
        feats_li = "".join(f"<li>{f}</li>" for f in feats)
        inner = ""
        if rec:
            inner += '<span class="hc-ribbon">Recommended</span>'
        inner += f'<span class="nm">{name}</span><span class="tier">{tier}</span>'
        inner += (f'<div class="hc-price"><span class="amt">{price}</span>'
                  f'<span class="per">{per}</span></div>')
        inner += f'<ul class="hc-feats">{feats_li}</ul>'
        if adv:
            inner += '<span class="hc-lock">Advisor only</span>'
        with card:
            ui.html(inner)
            pick = ui.element("button").classes("hc-pick")
            with pick:
                ui.label(pick_label)

    # ---- action emit (interactive mode) ------------------------------------
    # Both entry points consult the coach ONCE, AFTER all the user's actions
    # are applied. The consult is wrapped in run.io_bound because in LLM mode
    # it makes a blocking HTTP call; running it on the event loop would block
    # the WebSocket heartbeat and drop the connection.
    async def _apply_and_consult(action_specs):
        if sess.is_done():
            return
        for spec in action_specs:
            if sess.is_done():
                break
            type_ = spec[0]
            target = spec[1] if len(spec) > 1 else None
            dwell = sess.wall_clock_dwell()
            sess.apply_action(Action(type=type_, target=target, dwell_s=dwell))
        if not sess.is_done():
            sig, intervention = await run.io_bound(sess.consult_coach)
            if intervention is not None and sess.shown_intervention_step != int(sess.state):
                sess.shown_intervention_step = int(sess.state)
                open_chat(intervention, sig)
        render_for_step(int(sess.state))

    async def emit_action(type_: str, target: str = None):
        await _apply_and_consult([(type_, target)])

    async def emit_actions(*specs):
        """Apply multiple (type, target) tuples atomically; one coach check."""
        await _apply_and_consult(list(specs))

    # ========================================================================
    # PER-STEP RENDERERS — one set, branching on `interactive`. In auto/live
    # mode the controls are disabled (the agent drives); Back/Continue live in
    # the footer (see paint_footer), so the renderers paint content only.
    # ========================================================================
    def _r_s0():
        _intro("Private health cover", "Health cover, made clear.",
               "Get a personalised quote for private outpatient care in about "
               "two minutes. Free choice of doctor, adjust or cancel anytime.",
               serif=True)
        cta = ui.element("button").classes("hc-cont").style("margin-top:24px")
        with cta:
            ui.label("Get my quote →")
        if interactive:
            cta.props('id="journey-continue"')
            cta.on("click", lambda: emit_action("continue"))
        else:
            cta.props('id="journey-continue" disabled')

    def _r_s1():
        _intro("Getting started", "What kind of cover are you looking for?",
               "This tailors the plans we show you. You can change it later.")
        with ui.element("div").classes("hc-opts"):
            _option_card("Private doctor",
                         "Outpatient visits with your own choice of specialist.",
                         selected=not interactive,
                         on_click=(lambda: emit_actions(("select", "doctor"), ("continue",)))
                         if interactive else None,
                         elem_id="journey-card-doctor")
            _option_card("Hospital", "Inpatient stays, private or single rooms.",
                         on_click=(lambda: emit_action("select", "hospital"))
                         if interactive else None,
                         elem_id="journey-card-hospital")
            _option_card("Both", "Full outpatient and inpatient cover combined.",
                         on_click=(lambda: emit_action("select", "both"))
                         if interactive else None,
                         elem_id="journey-card-both")

    def _r_s2():
        _intro("Getting started", "Who is this cover for?",
               "We’ll keep the questions relevant to you.")
        with ui.element("div").classes("hc-opts").style("grid-template-columns:repeat(2,1fr)"):
            _option_card("Just me", "Personal cover for one person.",
                         selected=not interactive,
                         on_click=(lambda: emit_actions(("select", "myself"), ("continue",)))
                         if interactive else None,
                         elem_id="journey-card-myself")
            _option_card("Me and others", "Cover for family or additional people.",
                         on_click=(lambda: emit_action("select", "others"))
                         if interactive else None,
                         elem_id="journey-card-others")

    def _r_s3():
        _intro("About you", "Tell us a bit about yourself",
               "We need a couple of basics before we can show you a price.")
        with ui.element("div").classes("hc-card").style(
            "max-width:540px;margin-top:24px;padding:20px;gap:14px;"
            "display:flex;flex-direction:column"
        ):
            with ui.row().classes("items-end w-full").style("gap:10px"):
                ui.input(label="Date of birth", value="15.07.1985").props(
                    "outlined dense disable"
                ).classes("flex-grow")
                if interactive:
                    b = ui.element("button").classes("hc-pick").style(
                        "width:auto;padding:0 16px;margin-top:0"
                    ).props('id="journey-edit-dob"')
                    with b:
                        ui.label("Edit")
                    b.on("click", lambda: emit_action("change_field", "dob"))
            with ui.row().classes("items-end w-full").style("gap:10px"):
                ui.input(label="Social insurance number", value="1234 150785").props(
                    "outlined dense disable"
                ).classes("flex-grow")
                if interactive:
                    b2 = ui.element("button").classes("hc-pick").style(
                        "width:auto;padding:0 16px;margin-top:0"
                    )
                    with b2:
                        ui.label("Edit")
                    b2.on("click", lambda: emit_action("change_field", "ssn"))

    def _r_s4():
        _intro("Your cover", "Choose the cover that fits",
               "Private outpatient care with free choice of doctor. "
               "Adjust or cancel anytime.")
        with ui.element("div").classes("hc-cards"):
            _tariff_card("Start", "Essentials", "€38.74", "/mo",
                         ["Free choice of doctor", "€500 outpatient / yr",
                          "Online claims in-app"],
                         on_click=(lambda: emit_actions(("select", "Start"), ("continue",)))
                         if interactive else None,
                         elem_id="journey-tariff-Start")
            _tariff_card("Optimal", "Most chosen", "€68.14", "/mo",
                         ["Everything in Start", "Unlimited outpatient",
                          "Private specialist access", "48-hour claim payout"],
                         rec=True, pick_label="Select Optimal",
                         on_click=(lambda: emit_actions(("select", "Optimal"), ("continue",)))
                         if interactive else None,
                         elem_id="journey-tariff-Optimal")
            _tariff_card("Opt.Plus", "Extended", "€89.50", "/mo",
                         ["Everything in Optimal", "Single-room hospital"],
                         adv=True,
                         on_click=(lambda: emit_action("hover", "OptPlus"))
                         if interactive else None,
                         elem_id="journey-tariff-OptPlus")
            _tariff_card("Premium", "Comprehensive", "€112.00", "/mo",
                         ["Full private hospital", "Worldwide cover"],
                         adv=True,
                         on_click=(lambda: emit_action("hover", "Premium"))
                         if interactive else None,
                         elem_id="journey-tariff-Premium")

    def _r_s6():
        _intro("Health questions", "A few health questions",
               "Honest answers keep your cover valid. This stays private.")
        with ui.element("div").classes("hc-card").style("margin-top:24px;padding:6px 20px"):
            for q in [
                "Have you had any major surgery in the last 5 years?",
                "Are you currently on prescription medication?",
                "Do you have any chronic conditions?",
                "Have you smoked in the last 12 months?",
            ]:
                with ui.row().classes("items-center w-full").style(
                    "justify-content:space-between;padding:12px 0;"
                    "border-bottom:1px solid var(--hc-cream-line)"
                ):
                    ui.label(q).classes("hc-sub").style("margin:0;max-width:none")
                    ui.radio(["Yes", "No"], value="No").props(
                        "inline" if interactive else "inline disable"
                    )

    def _r_s7():
        provisional = sess.provisional or 68.14
        final = round(provisional * (1 + sess.surcharge), 2)
        gap = round(final - provisional, 2)
        _intro("Your price", "Your personalised price",
               "Based on your health profile.")
        cap = f"per month for <b>{_selected_tariff_name()}</b>"
        if gap > 0.01:
            cap += (f" · €{gap:.2f} above the €{provisional:.2f} estimate "
                    "from your health answers")
        cap += ", cancel anytime."
        ui.html(f'<div class="hc-perday" style="margin-top:24px">'
                f'<span class="big">€{final:.2f}</span>'
                f'<span class="cap">{cap}</span></div>')
        with ui.row().classes("items-center").style("gap:14px;margin-top:20px"):
            cancel = ui.element("button").classes("hc-back")
            with cancel:
                ui.label("Cancel")
            if interactive:
                cancel.props('id="journey-cancel-link"')
                cancel.on("click", lambda: emit_action("hover", "cancel"))
                ui.label("(Cancel registers a ‘hovered cancel’ signal — it doesn’t "
                         "actually cancel)").classes("hc-sub").style(
                    "margin:0;font-size:12px;color:var(--hc-ink-3)"
                )
            else:
                cancel.props('id="journey-cancel-link" disabled')

    def _r_s12():
        provisional = sess.provisional or 68.14
        final = round(provisional * (1 + sess.surcharge), 2)
        _intro("Almost done", "Review and confirm",
               "Check the details below, then confirm.")
        rows = [("Plan", _selected_tariff_name()), ("Monthly", f"€{final:.2f}"),
                ("Billing", "Monthly, paperless"), ("Coverage starts", "Next month")]
        rows_html = "".join(
            '<div style="display:flex;justify-content:space-between;padding:13px 0;'
            'border-bottom:1px solid var(--hc-cream-line)">'
            f'<span style="color:var(--hc-ink-2);font-size:14px">{k}</span>'
            f'<span style="font-weight:700;font-size:14px">{v}</span></div>'
            for k, v in rows
        )
        ui.html(f'<div class="hc-card" style="max-width:520px;margin-top:24px;'
                f'padding:4px 20px">{rows_html}</div>')
        ui.checkbox("I agree to the terms and the privacy notice").props(
            "" if interactive else "disable"
        ).classes("mt-4").style("color:var(--hc-ink-2)")

    def _render_terminal():
        cur = int(sess.state)
        name = sess.persona.title() if sess.persona in ("judith", "franz", "peter") else ""
        if cur == 90:
            who = f", {name}" if name else ""
            ui.html(f'<div class="hc-end ok"><div class="badge">✓</div>'
                    f'<h2>You’re covered{who}.</h2>'
                    '<p>Welcome to HealthCover. Your plan is active from next month — '
                    'we’ve emailed your policy documents and a welcome guide.</p></div>')
        elif cur == 91:
            ui.html('<div class="hc-end off"><div class="badge">–</div>'
                    '<h2>Session ended</h2>'
                    '<p>You can come back anytime — your progress is saved.</p></div>')
        elif cur == 92:
            ui.html('<div class="hc-end adv"><div class="badge">☎</div>'
                    '<h2>An advisor will be in touch</h2>'
                    '<p>We’ll call you within the next business day to walk through '
                    'the advisory tariffs.</p></div>')
        elif cur == 93:
            ui.html('<div class="hc-end adv"><div class="badge">☎</div>'
                    '<h2>We’ll call you back</h2>'
                    '<p>Expect a call within the next business day — no fuss, '
                    'no obligations.</p></div>')

    RENDERERS = {
        0: _r_s0, 1: _r_s1, 2: _r_s2, 3: _r_s3,
        4: _r_s4, 6: _r_s6, 7: _r_s7, 12: _r_s12,
    }

    # ---- live detection-rules panel (presenter chrome) ---------------------
    # Mirrors coach/detection.py:_detect_threshold so the presenter can see
    # which signals are at/over threshold. Re-paints on every action AND every
    # watchdog tick, so dwell-based rules tick up live.
    def _threshold_rule_specs():
        d = sess.cfg["detection"]
        sig = sess._compute_signals()
        elapsed = sess.wall_clock_dwell() if sess.interactive else 0
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
                (f"max_steps_completed < {d['early_overwhelm_max_steps']}",
                 sig.max_steps_completed < d['early_overwhelm_max_steps'],
                 str(sig.max_steps_completed), f"< {d['early_overwhelm_max_steps']}"),
            ]),
            ("repeated_back_nav", "generic friction", [
                (f"back_nav_count >= {d['back_nav_threshold']}",
                 sig.back_nav_count >= d['back_nav_threshold'],
                 str(sig.back_nav_count), f">= {d['back_nav_threshold']}"),
            ]),
        ]

    def refresh_rules_panel():
        rules_panel.clear()
        method_ = sess.cfg["detection"].get("method", "threshold")
        with rules_panel:
            with ui.row().classes("items-center gap-2 mb-1"):
                ui.label("Detection rules (live)").classes(
                    "text-sm font-semibold text-gray-700"
                )
                ui.label(f"method: {method_}").classes(
                    "text-xs font-mono bg-gray-100 px-2 py-0.5 rounded text-gray-600"
                )
                if interactive:
                    ui.label("dwell counts wall-clock time").classes(
                        "text-xs italic text-gray-400 ml-auto"
                    )
            if method_ != "threshold":
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
        on_funnel = pos > 0 and cur not in TERMINALS
        for i, seg in enumerate(progress_segs):
            seg.set_visibility(on_funnel)
            if not on_funnel:
                continue
            if i < pos - 1:
                seg.classes(replace="seg done")
            elif i == pos - 1:
                seg.classes(replace="seg now")
            else:
                seg.classes(replace="seg")
        if on_funnel:
            progress_label.set_text(f"Step {pos} of {len(FUNNEL_STEPS)}")
        elif cur in TERMINALS:
            progress_label.set_text(PAGE_TITLES.get(cur, "Done"))
        else:
            progress_label.set_text("Let’s get started")

    def paint_page(cur: int):
        page_container.clear()
        if cur in TERMINALS:
            page_container.style("justify-content:center;align-items:center;padding-bottom:0")
        elif cur == 0:
            page_container.style("justify-content:center;align-items:flex-start;padding-bottom:26px")
        else:
            page_container.style("justify-content:flex-start;align-items:stretch;padding-bottom:0")
        with page_container:
            if cur in TERMINALS:
                _render_terminal()
                return
            renderer = RENDERERS.get(cur)
            if renderer:
                renderer()

    def paint_footer(cur: int):
        footer_container.clear()
        show = cur in FUNNEL_STEPS
        footer_container.set_visibility(show)
        if not show:
            return
        with footer_container:
            back = ui.element("button").classes("hc-back")
            with back:
                ui.label("← Back")
            if interactive:
                back.props('id="journey-back"')
                back.on("click", lambda: emit_action("back"))
            else:
                back.props("disabled")

            cont = ui.element("button").classes("hc-cont")
            with cont:
                ui.label("Confirm →" if cur == 12 else "Continue →")
            if interactive:
                cont.props('id="journey-continue"')
                if cur == 1:
                    cont.on("click", lambda: emit_actions(("select", "doctor"), ("continue",)))
                elif cur == 2:
                    cont.on("click", lambda: emit_actions(("select", "myself"), ("continue",)))
                elif cur == 4:
                    cont.on("click", lambda: emit_actions(("select", "Optimal"), ("continue",)))
                else:
                    cont.on("click", lambda: emit_action("continue"))
            else:
                cont.props('id="journey-continue" disabled')

    def render_for_step(cur: int):
        paint_progress(cur)
        paint_page(cur)
        paint_footer(cur)
        refresh_rules_panel()

    def stop_autoplay():
        if autoplay_timer["t"] is not None:
            autoplay_timer["t"].deactivate()
            autoplay_timer["t"] = None

    def stop_watchdog():
        if watchdog_timer["t"] is not None:
            watchdog_timer["t"].deactivate()
            watchdog_timer["t"] = None

    async def auto_tick():
        if sess.is_done():
            stop_autoplay()
            return
        prev_state = int(sess.state)
        # step_once internally calls coach() which in LLM mode hits inference -
        # run it off the event loop so the WebSocket heartbeat stays alive.
        result = await run.io_bound(sess.step_once)
        if result and result["intervention"] is not None:
            iv = result["intervention"]
            render_for_step(iv.step)
            stop_autoplay()
            open_chat(iv, result["signals"])
            return
        if int(sess.state) != prev_state:
            render_for_step(int(sess.state))
        if sess.is_done():
            stop_autoplay()
            render_for_step(int(sess.state))

    async def watchdog_tick():
        """Interactive-mode passive coach: if the human sits on a page,
        synthesize dwell from wall-clock time and ask the coach. Fires once per
        state (gated by shown_intervention_step). Re-paints the rules panel so
        dwell counters tick up live. Wrapped in run.io_bound so a slow LLM call
        doesn't block the event loop."""
        if sess.is_done():
            stop_watchdog()
            return
        dwell = sess.wall_clock_dwell()
        sig, intervention = await run.io_bound(sess.consult_coach, virtual_dwell_s=dwell)
        refresh_rules_panel()
        if intervention is not None and sess.shown_intervention_step != int(sess.state):
            sess.shown_intervention_step = int(sess.state)
            open_chat(intervention, sig)

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

    async def manual_step():
        """In auto mode: advance one tick (pauses auto-play)."""
        if autoplay_switch.value:
            autoplay_switch.value = False
        stop_autoplay()
        await auto_tick()

    # ========================================================================
    # PRESENTER CHROME — below the cream surface; plain dev tooling (NOT part
    # of the customer brand). Keeps the rules panel + the URL-contract switches.
    # ========================================================================
    rules_panel = ui.column().props('id="journey-rules"').classes(
        "max-w-5xl mx-auto px-6 w-full mt-6 gap-2"
    )

    with ui.row().classes("max-w-5xl mx-auto mt-4 px-6 gap-3 items-center "
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
            # placeholder so code referring to autoplay_switch.value doesn't
            # blow up in interactive mode (it never starts auto-play)
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
            options=["threshold", "gbm", "llm"], value=method,
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
        ui.link("Judith S4", "/journey?seed=0&episode=0&persona=judith&method=llm"
                + (f"&mode={mode}" if interactive else "")).props(
            'id="journey-quick-judith"'
        ).classes("text-sky-700 underline")
        ui.link("Franz S7", "/journey?seed=0&episode=16&persona=franz&method=llm"
                + (f"&mode={mode}" if interactive else "")).props(
            'id="journey-quick-franz"'
        ).classes("text-sky-700 underline")
        ui.link("Peter early", "/journey?seed=0&episode=0&persona=peter&method=llm"
                + (f"&mode={mode}" if interactive else "")).props(
            'id="journey-quick-peter"'
        ).classes("text-sky-700 underline")
        ui.element("div").classes("flex-grow")

        if interactive:
            toggle_auto = "↷ Switch to auto"
            target_auto = "auto"
            toggle_live = "▶ Switch to live (LLM)"
            target_live = "live"
        elif live:
            toggle_auto = "↷ Switch to auto"
            target_auto = "auto"
            toggle_live = "✋ Drive it yourself"
            target_live = "interactive"
        else:
            toggle_auto = "✋ Drive it yourself"
            target_auto = "interactive"
            toggle_live = "▶ Switch to live (LLM)"
            target_live = "live"

        ui.link(toggle_auto,
                f"/journey?seed={seed}&episode={episode}&persona={persona}"
                f"&method={method}&gbm_threshold={gbm_threshold}&mode={target_auto}").props(
            'id="journey-mode-toggle"'
        ).classes("text-sky-700 underline font-semibold")

        ui.link(toggle_live,
                f"/journey?seed={seed}&episode={episode}&persona={persona}"
                f"&method={method}&gbm_threshold={gbm_threshold}&mode={target_live}").props(
            'id="journey-live-toggle"'
        ).classes("text-sky-700 underline font-semibold ml-4")

        ui.label(
            f"seed={seed}  ep={episode}  detector={method}  mode={mode}"
        ).classes("font-mono ml-4")

    # initial paint
    render_for_step(int(sess.state))

    # kick off driver
    if interactive:
        # watchdog: 1s tick, only fires once per state (gated by shown_intervention_step)
        watchdog_timer["t"] = ui.timer(1.0, watchdog_tick)
    else:
        if autoplay_switch.value:
            autoplay_timer["t"] = ui.timer(autoplay_ms / 1000.0, auto_tick)
