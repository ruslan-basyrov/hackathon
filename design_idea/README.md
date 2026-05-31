# Handoff: HealthCover `/journey` — "Warm" visual design

## Overview
This package is the visual design for the **customer-facing `/journey` route** described in `BUILD_SPEC.md` Phase 3.5 — the branded "HealthCover" insurance signup that the coach popup is overlaid on (the on-stage demo route). It covers the brand, the per-step screens, and the "A nudge from HealthCover" intervention popup.

The chosen direction is **"Warm"**: a UNIQA-style **deep blue** primary with a **warm cream** background and an **amber** accent — trustworthy but human. (HealthCover is the fictional brand the spec uses; this is an original identity in UNIQA-adjacent colors, not UNIQA's actual logo/identity.)

## About the design files
The files in this bundle are **design references**, not production code to paste in:
- `healthcover-warm.css` — the design system as a real stylesheet (tokens + component classes). This one you *can* use directly as a NiceGUI static asset.
- `journey-reference.html` — a static, dependency-free render of the key screens (Welcome, Coverage type, Tariff + nudge, Converted end-page). Open it in a browser; it is the **visual source of truth**.

The task is to **recreate these screens inside the NiceGUI app** (`services/ui/journey_view.py`) using NiceGUI's own elements + this stylesheet — not to ship the HTML. The `/debug` route (`debug_view.py`) keeps its plain functional styling; only `/journey` gets this skin.

## Fidelity
**High-fidelity.** Colors, type, spacing, radii and copy are final. Recreate pixel-for-pixel using the classes in `healthcover-warm.css`. Where the design shows a striped `lifestyle photo` / `product shot` placeholder, drop in real photography later — keep the box size.

---

## How it maps to the NiceGUI route (read this first)

The BUILD_SPEC **freezes a set of element ids** for `/journey` that the Playwright demo + tests bind to. They are a contract — keep them exactly, on the nodes indicated:

| Frozen id | Goes on | In this design |
|---|---|---|
| `journey-page` | the per-step page root | the `.hc-scr` surface (or its `.hc-main`) |
| `journey-step-label` | the step indicator | the `.hc-prog .lbl` ("Step 4 of 7") |
| `journey-narration` | narration line | optional caption under the funnel (your call) |
| `journey-popup` | the nudge/chat overlay root | the `.hc-scrim` wrapper |
| `journey-popup-type` | intervention type · mode | the `.hc-nudge-type` mono label |
| `journey-popup-text` | the intervention wording | the **first assistant chat bubble** (`.hc-msg.bot` — `realize()` output) |
| `journey-popup-close` | dismiss (X) | the `.hc-close` button in the header |
| `journey-popup-continue` | "Continue journey" action | the `.hc-actions .primary` button |
| `journey-chat-log` | the message thread | the `.hc-chat` scroll column |
| `journey-chat-input` | reply field | the `.hc-reply input` (placeholder "Reply…") |
| `journey-chat-send` | send button | the `.hc-reply .send` button |

The persona switcher (Judith / Franz / Peter) and the `threshold ↔ gbm` method switcher are already in the spec's URL contract — wire the `.hc-personas` buttons to flip `cfg["detection"]["method"]` / persona at runtime as the spec describes. The UI stays **read-only over the simulator** (no new logic in `coach/`, `signals.py`, etc.).

### Loading the stylesheet
```python
from pathlib import Path
from nicegui import ui

CSS = Path(__file__).parent / "static" / "healthcover-warm.css"

@ui.page("/journey")
def journey():
    ui.add_css(CSS.read_text())          # once per page
    # ...build the current step...
```
Also load the three Google fonts once in the page head:
```python
ui.add_head_html(
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?'
    'family=Hanken+Grotesk:wght@400;500;600;700;800&'
    'family=Source+Serif+4:opsz,wght@8..60,400;8..60,600;8..60,700&'
    'family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">'
)
```

### Two ways to build each screen
1. **`ui.html(...)`** with the exact markup from `journey-reference.html` — fastest path to pixel fidelity; bind the frozen ids and swap the dynamic text in Python. Best for the static parts of a step.
2. **Native NiceGUI elements** (`ui.row`, `ui.card`, `ui.button`) with `.classes('hc-card is-rec')` applied — better when you need NiceGUI event handlers on the element. Use `.props('id=journey-popup')` (or `ui.element` + `_props`) to stamp the frozen ids.

Mix freely. The popup is cleanest as a `ui.dialog` styled to `.hc-modal`, OR an absolutely-positioned `.hc-scrim` overlay inside the page (the reference uses the latter so it sits *on* the product page, matching the "product feature, not debug overlay" requirement). Pausing auto-play while `#journey-popup` is open and resuming on close is already in the spec.

---

## Screens / Views

All screens share: a 64px **top bar** (`.hc-top`: logo left, persona switcher + "Coach active" right) and, on funnel steps, a 7-segment **progress bar** (`.hc-prog`). Funnel steps end in a **footer** (`.hc-foot`: Back / Continue). Page background is cream `#fbf7f0`.

In-scope funnel order (note the deliberate **S5 gap** — out of scope): **S0 → S1 → S2 → S3 → S4 → S6 → S7 → S12**.

1. **S0 · Welcome** — serif H1 (`--hc-font-serif`, ~46px) "Health cover, made clear.", supporting line, single `Get my quote →` primary button. No progress bar.
2. **S1 · Coverage type** — three `.hc-opt` cards (image + title + desc + select): **Private doctor** (selected/in-scope), **Hospital**, **Both**. (Hospital/Both → routes to advisor per spec logic.)
3. **S2 · For whom** — same `.hc-opts` pattern, two cards: **Just me** (in-scope), **Me and others** (→ advisor).
4. **S3 · Personal data** — a simple form step (name / DOB / postcode). Use `.hc-card`-styled fields; keep all required fields (spec forbids removing data-collection steps). This is where **Peter** may get an "overwhelm" simplify/callback nudge.
5. **S4 · Initial price** — the four-card `.hc-cards` price table: **Start €54.20**, **Optimal €68.14** (`.is-rec`, "Recommended" ribbon), **Opt.Plus €89.50** + **Premium €112.00** (`.is-adv`, "Advisor only" lock chip). **This is the hero step** where **Judith**'s nudge fires.
6. **S6 · Health questions** — short questionnaire (out-of-scope S5 skipped; this carries the intermediate drop-off). Yes/No rows in a `.hc-card`.
7. **S7 · Final price** — the personalised premium with the provisional → final `price_gap_eur`. **Franz**'s nudge fires here (justify the jump / cheaper alternative / save-progress).
8. **S12 · Confirm** — summary + confirm button → Converted.
9. **Terminal end-pages** (`.hc-end`): **Converted** (`.ok`, blue badge), **Abandoned** (`.off`, grey), **Routed-to-advisor** (`.adv`, amber), **Service-contact** (`.adv`). Each: badge + H2 + one supporting paragraph.

### The coach nudge popup — a conversational coach (per persona)
**The popup is a chat, not a one-way nudge** (this mirrors `coach/llm_realize.py::chat_followup` + `journey_view.py`). Structure: header (kicker + persona chip + `×` close) → `journey-popup-type` (`"price_reframe · nudge"`) → `journey-chat-log` thread → "thinking…" spinner → reply input + Send → action row.

- The **first assistant bubble** is the intervention text from `realize()` and keeps `journey-popup-text`. In this design it may carry a rich attachment (the `.hc-perday` / `.hc-cmp` blocks) for Judith/Franz.
- The user can **reply**: append a `.hc-msg.user` bubble, show the spinner, call `chat_followup(messages, cfg)`, then append the assistant reply. The seed history (system + structured prompt) is hidden — only bubbles from `visible_start` render.
- **Mode-gated input:** show `journey-chat-input` + `journey-chat-send` only when `cfg.realize.method == "llm"`. In template mode there's no backend to answer follow-ups — hide the input and show just the first bubble + action buttons.
- **Actions:** `journey-popup-continue` advances the journey; the secondary ghost button is the persona branch. The `×` (`journey-popup-close`) dismisses without choosing.

Per-persona first bubble (the opening intervention):
- **Judith (fires S4)** — price reframe + `.hc-perday` (**€2.27/day** = €68.14/mo) + `.hc-cmp` bars (HealthCover €68 vs Market €81). Actions: **Continue with Optimal** + **Book a 10-min call** (soft handoff — a valid win for Judith).
- **Franz (fires S7)** — justify the €4.20 jump with a breakdown; **never** offer an advisor. Actions: **Keep my Optimal plan** + **Show a cheaper tariff**.
- **Peter (fires S1–S3)** — calm callback offer, no stats. Actions: **Yes, call me back** (his success path) + **Continue online**.

Keep the `journey-*` ids on the matching nodes regardless of persona.

---

## Interactions & behavior
- **Auto-play** advances the journey at `autoplay_ms` (default 900ms) — page transitions only, no cursor/typing animation.
- A popup **pauses** auto-play; dismissing (`journey-popup-close` ×) or **Continue journey** (`journey-popup-continue`) **resumes**. Sending a chat reply does **not** resume — the user is mid-conversation.
- **Coach chat:** replies call `chat_followup`; disable the input + show the spinner while awaiting; re-enable on response. Network/timeout errors surface as an assistant bubble, never a crash (LLM mode only).
- **Persona switcher** + **method switcher** (`threshold`/`gbm`) flip session state and re-run; flipping method visibly changes how often the popup fires.
- Buttons: primary `.hc-cont` / `.primary` darken to `--hc-blue-700` on hover. All controls ≥40px tall.
- Transitions: a 180–220ms cross-fade between steps is enough; keep it subtle.

## State (UI only — owned by the simulator, surfaced here)
- `seed`, `episode`, `persona`, `method`, `gbm_threshold`, `narration`, `autoplay_ms` — from the URL contract into session state on first load.
- Current `Step`, current `Signals` (for `/debug`), and whether `coach()` returned an `Intervention` for this step (drives popup visibility).
- The UI never computes conversion or effectiveness — it reads `coach()` / `extract()`.

---

## Design tokens

**Color**
| Token | Hex | Use |
|---|---|---|
| `--hc-blue` | `#0a51d0` | primary buttons, links, selected, comparison "you" bar |
| `--hc-blue-700` | `#0844b0` | hover/pressed |
| `--hc-blue-900` | `#062a6e` | deep brand, logo plus, scrim |
| `--hc-amber` | `#e0962f` | recommended tier, ribbon, progress, eyebrows, €/day stat |
| `--hc-amber-700` | `#c47f1d` | amber text on soft amber |
| `--hc-amber-soft` | `#f6e6cd` | check-bullet bg, lock chip, spark icon bg |
| `--hc-cream` | `#fbf7f0` | page background |
| `--hc-cream-line` | `#ece3d4` | borders/dividers on cream |
| `--hc-surface` | `#ffffff` | cards, modal |
| `--hc-tint-50` | `#eef3fd` | pale blue fills |
| `--hc-tint-100` | `#dde7fb` | comparison track bg |
| `--hc-ink` | `#16203a` | primary text |
| `--hc-ink-2` | `#46506a` | secondary text |
| `--hc-ink-3` | `#7e879b` | tertiary / captions |
| persona dots | `#6b4ee0` / `#0a51d0` / `#e0962f` | Judith / Franz / Peter |

**Type** — Hanken Grotesk (UI/body), Source Serif 4 (welcome & end-page headlines only), IBM Plex Mono (eyebrow/kicker labels). Scale: H1 30–31px/800 (welcome 46px serif), nudge headline 20px/800, body 14–15px, card price 26px/800, €/day 34px/800, eyebrow 12px/700 uppercase tracked .12em, labels 11–12px.

**Radius** — cards/options 20px · modal 24px · buttons & chips pill (999px) · small blocks 10–12px.

**Shadow** — card `0 12px 30px -22px rgba(120,90,30,.40)` · recommended `0 18px 40px -18px rgba(224,150,47,.50)` · modal `0 40px 80px -24px rgba(6,42,110,.50)`.

**Spacing** — page gutter 40px, top bar 32px, card grid gap 14px, option grid gap 16px. Base unit 4px.

## Assets
No raster assets ship here. Image placeholders (`.hc-img`, the striped "lifestyle photo" / "product shot" boxes) mark where real photography goes — keep the box dimensions. The HealthCover logo is an inline SVG (rounded square + plus) defined in `journey-reference.html`; lift it as-is.

## Files
- `healthcover-warm.css` — design system; copy to `services/ui/static/healthcover-warm.css`.
- `journey-reference.html` — static visual reference for all key screens + the conversational coach-chat popup.
- `README.md` — this document.

---

## Paste-ready prompt for your coding agent
> Re-skin the existing `/journey` route (`services/ui/journey_view.py`) with the design in `design_handoff_healthcover_journey/`. Copy `healthcover-warm.css` into `services/ui/static/` and load it (plus the three Google fonts) on the `/journey` page only. Recreate each in-scope funnel step (S0,S1,S2,S3,S4,S6,S7,S12) and the four terminal pages using the component classes in that CSS, matching `journey-reference.html` pixel-for-pixel. The coach popup is a **conversational chat**, not a one-way nudge: header + `×` close, a `journey-chat-log` thread whose first assistant bubble (`journey-popup-text`) is the `realize()` output, a reply input (`journey-chat-input`) + Send (`journey-chat-send`) shown only in LLM mode and driving `chat_followup`, a "thinking…" spinner, and an actions row (`journey-popup-continue` + persona branch). Vary the first bubble by persona (Judith=€/day reframe + market bars at S4; Franz=justify jump / cheaper option at S7, no advisor; Peter=callback at S1–S3). Keep ALL frozen ids exactly: `journey-page`, `journey-step-label`, `journey-narration`, `journey-popup`, `journey-popup-type`, `journey-popup-text`, `journey-popup-close`, `journey-popup-continue`, `journey-chat-log`, `journey-chat-input`, `journey-chat-send`. This is presentation only — do NOT change `coach/`, `signals.py`, `agent_stub.py`, `state_machine.py`, or the chat/session logic in `journey_view.py`. Leave `/debug` untouched.
