---
theme: default
title: Conversion Coach — AI-Guided Conversion Flow
info: |
  Conversion Coach — Insurance AI track (UNIQA), Zero One Hack_01.
  A funnel-simulation substrate with a staged, inspectable coach.
  Decision logic lives in code; the LLM only produces behavior and words.
colorSchema: light
aspectRatio: 16/9
canvasWidth: 980
fonts:
  sans: Hanken Grotesk
  serif: Source Serif 4
  mono: IBM Plex Mono
  weights: '400,500,600,700,800'
  italic: false
layout: cover
drawings:
  persist: false
transition: fade
---

<div class="hc-eyebrow">Insurance AI · UNIQA — AI-Guided Conversion Flow</div>

# Conversion&nbsp;Coach

<p class="hc-sub">A coach that watches a signup funnel, detects who is about to drop off, and nudges them — in <em style="color:var(--hc-blue);font-style:normal">their</em> language — at the right moment.</p>

<div class="mt-8 flex items-center gap-3 text-[.82rem]" style="color:var(--hc-ink-3);font-family:var(--hc-font-mono)">
  <span>Zero One Hack_01</span><span>·</span><span>AI Factory Austria, Vienna</span><span>·</span><span>compute: Leonardo (A100)</span>
</div>

---

<div class="hc-eyebrow">The problem</div>

# A static calculator leaks customers at every step

<div class="grid grid-cols-[1.4fr_1fr] gap-10 items-center mt-2">

<div>

The current signup is a one-size form. People hesitate at the price, get
overwhelmed by questions, or balk at the final number — and quietly leave.

- The same nudge for everyone **annoys** as many as it saves
- No signal for **when** someone is about to go
- "Conversion" doesn't even mean the same thing for every customer

<div class="hc-note mt-4">Calibrated baseline conversion on the in-scope path: <strong>~5.6%</strong> — three documented drop-offs at the price (S4), the health questions (S6), and the final price (S7).</div>

</div>

<div class="hc-card text-center">
  <div class="hc-kicker">In-scope funnel</div>
  <div class="hc-prog my-3">
    <span class="seg done" /><span class="seg done" /><span class="seg done" /><span class="seg now" /><span class="seg" /><span class="seg" /><span class="seg" />
  </div>
  <div class="hc-stat t-amber">5.6%</div>
  <div class="text-[.78rem] mt-1 t-ink3">reach “Converted”</div>
  <div class="flex justify-around mt-4 text-[.7rem] t-ink2 font-mono">
    <span>S4 −66%</span><span>S6 −24%</span><span>S7 −78%</span>
  </div>
</div>

</div>

---
layout: statement
---

<div class="hc-eyebrow">The one idea this is built on</div>

# Decision logic lives in <em>inspectable code.</em><br>The LLM produces behavior and words — <span class="amber">never decisions.</span>

<p>The state machine, the detection layer, and the per-persona policy are all readable code. The model only drives synthetic users and phrases an intervention <em>after</em> the policy has decided to fire it.</p>

---

<div class="hc-eyebrow">Why the split</div>

# This track is explicitly not an LLM-wrapper case

The jury grades **traceable decision rules**, **trigger precision/recall**, and
**annoyance rate**. A coach whose when/how policy is fused into model weights has
nothing inspectable to show.

<div class="grid grid-cols-2 gap-6 mt-5">
  <div class="hc-card">
    <div class="hc-chip blue mb-3">In code · inspectable</div>
    <ul class="tight text-[.86rem]">
      <li>The funnel <strong>state machine</strong> (pure mechanics)</li>
      <li>The <strong>detection</strong> layer — threshold &amp; GBM</li>
      <li>The per-persona <strong>policy</strong> table (when / what)</li>
    </ul>
  </div>
  <div class="hc-card">
    <div class="hc-chip amber mb-3">From the model · behavior + words</div>
    <ul class="tight text-[.86rem]">
      <li>The <strong>persona bots</strong> that act out each customer</li>
      <li>The intervention <strong>wording</strong>, per persona register</li>
      <li>…produced only <em>after</em> the policy fires — and it falls back to templates if the model is gone</li>
    </ul>
  </div>
</div>

---

<div class="hc-eyebrow">The central challenge — one strategy fails</div>

# Three customers. Three reasons to leave.

<div class="grid grid-cols-3 gap-4 mt-3">
  <Persona pkey="judith" name="Judith" segment="Rising Hybrid"
    drop="Initial price (S4)"
    conversion="Online purchase or a smooth advisor handoff"
    signal="dwell_s4 ↑ · tariff_hover ↑"
    never="aggressive online-only push" />
  <Persona pkey="franz" name="Franz" segment="Online Affine"
    drop="Final price (S7)"
    conversion="Online purchase only — handoff = failure"
    signal="external_tab ≥ 1 · hover_cancel ≥ 1"
    never="suggest an advisor / add friction" />
  <Persona pkey="peter" name="Peter" segment="Service Affine"
    drop="Early, pre-price (S1–S3)"
    conversion="Qualified service contact — online is not the target"
    signal="field_change ↑ · dwell_total ↑"
    never="push self-service / add options" />
</div>

<div class="hc-note mt-4">A single unified strategy fails by construction: the right move for Franz (never an advisor) is exactly the wrong move for Peter (a callback is his win).</div>

---

<div class="hc-eyebrow">Scope</div>

# Only the in-scope path is coached

<div class="grid grid-cols-[1.5fr_1fr] gap-10 items-center mt-2">

<div>

The coached journey is **private-doctor → "just me" → Start or Optimal**.
Everything else routes to a human advisor on purpose and is left alone.

```text
S0 → S1 → S2 → S3 → S4 → ⟍S5⟍ → S6 → S7 → S12 → ✓ Converted
                                  └ S5 skipped: out-of-scope add-on step
```

- Hospital / "Both" coverage → **advisor**
- "Me and others" → **advisor**
- Opt.Plus / Premium tariffs → **advisor** (advisory-only wall)

</div>

<div class="hc-card">
  <div class="hc-kicker mb-2">Routes out of scope</div>
  <div class="flex flex-col gap-2 text-[.82rem]">
    <div class="flex items-center justify-between"><span>Private doctor · just me</span><span class="hc-chip blue">coached</span></div>
    <div class="flex items-center justify-between t-ink3"><span>Hospital / Both</span><span class="hc-chip amber">advisor</span></div>
    <div class="flex items-center justify-between t-ink3"><span>Me &amp; others</span><span class="hc-chip amber">advisor</span></div>
    <div class="flex items-center justify-between t-ink3"><span>Opt.Plus / Premium</span><span class="hc-chip amber">advisor</span></div>
  </div>
</div>

</div>

---

<div class="hc-eyebrow">Architecture</div>

# One seeded loop. Swappable parts.

<div class="flex items-stretch gap-2 mt-4 text-center">
  <div class="hc-flow sub">signals.extract<br><span>(state, history)→Signals</span></div>
  <div class="hc-arrow">→</div>
  <div class="hc-flow coach">coach(...)<br><span>→ Intervention?</span></div>
  <div class="hc-arrow">→</div>
  <div class="hc-flow drv">Agent.act<br><span>→ Action</span></div>
  <div class="hc-arrow">→</div>
  <div class="hc-flow sub">state_machine.step<br><span>→ next state</span></div>
</div>
<div class="text-center text-[.72rem] t-ink3 mt-2 font-mono">… loop until terminal · seeded by (master_seed, episode_idx) — same seed runs with &amp; without coach</div>

<div class="grid grid-cols-3 gap-4 mt-5 text-[.8rem]">
  <div class="hc-card"><span class="legend sub" /> <strong>Substrate</strong> — the unchanging measurement loop</div>
  <div class="hc-card"><span class="legend coach" /> <strong>Decision logic</strong> — plain, inspectable code</div>
  <div class="hc-card"><span class="legend drv" /> <strong>Behind a swap boundary</strong> — driver &amp; model</div>
</div>

<style>
.hc-flow { flex:1; border-radius:14px; padding:14px 10px; font:800 .82rem var(--hc-font-mono); display:flex; flex-direction:column; justify-content:center; border:1px solid; }
.hc-flow span { font-weight:500; font-size:.66rem; opacity:.85; margin-top:4px; }
.hc-flow.sub { background:#e9f1fd; border-color:#bcd3f6; color:var(--hc-blue-900); }
.hc-flow.coach { background:var(--hc-amber-soft); border-color:#e9c98c; color:#6b4710; }
.hc-flow.drv { background:#efeafc; border-color:#cfc2f3; color:#3c2a78; }
.hc-arrow { display:flex; align-items:center; color:var(--hc-ink-3); font-weight:800; }
.legend { display:inline-block; width:11px; height:11px; border-radius:3px; vertical-align:middle; margin-right:4px; }
.legend.sub { background:#bcd3f6; } .legend.coach { background:#e9c98c; } .legend.drv { background:#cfc2f3; }
</style>

---

<div class="hc-eyebrow">Inside the coach</div>

# Detect → decide → realize

<div class="grid grid-cols-3 gap-4 mt-4">
  <div class="hc-card">
    <div class="hc-kicker t-blue">1 · detect()</div>
    <div class="font-800 mt-1 mb-2" style="color:var(--hc-ink)">Is this person at risk?</div>
    <ul class="tight text-[.8rem]">
      <li>P2 — hand-written <strong>thresholds</strong></li>
      <li>P3 — <strong>GBM</strong> classifier, same signature</li>
    </ul>
  </div>
  <div class="hc-card">
    <div class="hc-kicker t-blue">2 · policy.lookup()</div>
    <div class="font-800 mt-1 mb-2" style="color:var(--hc-ink)">What, for this persona?</div>
    <ul class="tight text-[.8rem]">
      <li>Per-persona <strong>decision table</strong></li>
      <li>Encodes each "never do"</li>
    </ul>
  </div>
  <div class="hc-card">
    <div class="hc-kicker t-blue">3 · realize()</div>
    <div class="font-800 mt-1 mb-2" style="color:var(--hc-ink)">In what words?</div>
    <ul class="tight text-[.8rem]">
      <li>P2 — <strong>templates</strong></li>
      <li>P4 — <strong>LLM</strong>, same signature</li>
    </ul>
  </div>
</div>

<div class="hc-note mt-4">Detection and decision are <strong>1</strong> and <strong>2</strong> — both code. The model only ever touches <strong>3</strong>, the words.</div>

---

<div class="hc-eyebrow">Traceable decision rules</div>

# Every fire is explainable

<div class="grid grid-cols-[1.15fr_1fr] gap-8 items-center mt-2">

<div>

The threshold backend reads like a checklist — you can point at exactly which
signals crossed which line, for which persona.

```python
# Judith — hesitates on the price table (S4)
fire = signals.step == 4 and signals.dwell_current_s > 25.0
# Franz — sticker shock at the final price (S7)
fire = signals.price_gap_eur > 4.0 and signals.hover_cancel_count >= 1
# Peter — overwhelmed early, before the price
fire = signals.field_change_count >= 2 and signals.max_steps_completed < 4
```

</div>

<div class="hc-card font-mono text-[.74rem]" style="background:#fcfaf5">
  <div class="flex items-center justify-between mb-2">
    <span class="font-700" style="color:var(--hc-ink)">Detection rules (live)</span>
    <span class="hc-chip">method: threshold</span>
  </div>
  <div style="border-left:3px solid #2faa6a;background:#eef9f1;padding:8px 10px;border-radius:6px">
    <div class="flex items-center justify-between"><span class="font-700" style="color:var(--hc-ink)">s4_dwell</span><span style="color:#2faa6a;font-weight:800">FIRES</span></div>
    <div class="t-ink3">✓ step == 4 &nbsp;·&nbsp; ✓ dwell_current_s &gt; 25.0 → 77.9s</div>
  </div>
  <div class="mt-2 t-ink3">s7_price_gap+cancel_hover · idle</div>
</div>

</div>

<div class="hc-note mt-3">The GBM swaps in behind the same <code>detect()</code> signature; its <strong>feature importances</strong> are the inspectability exhibit — logged to W&amp;B, not buried in weights.</div>

---

<div class="hc-eyebrow">The moment</div>

# A nudge from HealthCover

<div class="grid grid-cols-[1fr_430px] gap-8 items-center -mt-2">

<div>

Judith lingers on the price table. The coach fires `price_reframe` and reframes
**Optimal** as a daily cost — then offers the soft handoff that counts as a win
for her. It looks like part of the product, not a debug overlay.

- The popup is **conversational** — she can reply, the coach answers
- The wording comes from the model; the **decision to fire came from code**
- For Franz the same surface justifies the jump (never an advisor); for Peter, a callback

<div class="flex items-center gap-2 mt-4 text-[.78rem] t-ink3 font-mono">
  <span class="pd judith" /> persona: Judith &nbsp;·&nbsp; trigger: dwell &gt; 25s @ S4
</div>

</div>

<Nudge persona="judith" personaName="Judith" type="price_reframe · nudge"
  :compact="true" primary="Continue with Optimal" ghost="Book a call">
  Optimal works out to about <strong>€2.27 a day</strong> — less than a coffee — for unlimited outpatient care.
  <div class="rich">
    <div class="hc-perday">
      <span class="big">€2.27</span>
      <span class="cap">per day for <b>Optimal</b> — <b>€68.14</b>/mo, cancel anytime.</span>
    </div>
    <div class="hc-cmp">
      <div class="row you"><span class="rl">HealthCover</span><span class="track"><span class="fill" style="width:70%" /></span><span class="rv">€68</span></div>
      <div class="row mkt"><span class="rl">Market avg.</span><span class="track"><span class="fill" style="width:86%" /></span><span class="rv">€81</span></div>
    </div>
  </div>
</Nudge>

</div>

---

<div class="hc-eyebrow">How we measure</div>

# Identical seeds. The coach is the only variable.

<div class="grid grid-cols-[1.3fr_1fr] gap-8 items-start mt-2">

<div>

`runner` plays thousands of seeded episodes. Each seed runs **twice** — once with
the coach, once without — so nothing but the intervention differs.

- Reports **uplift** and **annoyance rate** (fires with no genuine risk)
- Per-persona conversion definitions applied in the scorer
- The eval harness is the **scaffold**, built first, re-run every phase

</div>

<div class="hc-card" style="border-left:4px solid var(--hc-amber)">
  <div class="hc-kicker t-amber mb-2">Honest framing</div>
  <p class="text-[.82rem] t-ink2 m-0">In Phases 1–4 the bots are <strong>scripted</strong>, so uplift is a <strong>parameter</strong> — these numbers validate the <strong>measurement</strong>, not efficacy. Efficacy becomes real only in Phase 5, when LLM bots actually read the wording.</p>
</div>

</div>

<div class="flex gap-3 mt-5 text-center">
  <div class="hc-card flex-1"><div class="hc-stat t-ink2">2×</div><div class="text-[.72rem] t-ink3 mt-1">runs per seed</div></div>
  <div class="hc-card flex-1"><div class="hc-stat t-ink2">N=10k+</div><div class="text-[.72rem] t-ink3 mt-1">episodes</div></div>
  <div class="hc-card flex-1"><div class="hc-stat t-ink2">3</div><div class="text-[.72rem] t-ink3 mt-1">persona scorers</div></div>
  <div class="hc-card flex-1"><div class="hc-stat t-ink2">P / R</div><div class="text-[.72rem] t-ink3 mt-1">trigger precision / recall</div></div>
</div>

---

<div class="hc-eyebrow">One swap boundary</div>

# `INFERENCE_BASE_URL` + `MODEL_NAME` — the only knobs

<div class="grid grid-cols-[1.2fr_1fr] gap-8 items-center mt-2">

<div>

Both the wording (`realize`) and the bots (`agent_llm`) speak OpenAI-compatible
chat. Swapping models touches **two values and the inference container** — never
the coach.

- Local small model for fast wiring (`qwen2.5-1.5b-instruct`)
- Fine-tuned **7B at FP8** for persona realism — LoRA trained on **Leonardo**
- A remote endpoint, if ever — nothing downstream knows the difference

<div class="hc-note mt-4">Endpoint down? <code>realize()</code> degrades to templates and <strong>every decision is unchanged</strong> — proof the logic never depended on the model.</div>

</div>

```yaml
# config.yaml — the swap point
inference_base_url: http://localhost:8003/v1
model_name: qwen2.5-1.5b-instruct

realize:
  method: llm
  graceful_fallback: true   # → templates
  timeout_s: 3.0
```

</div>

---

<div class="hc-eyebrow">How it was built</div>

# One swap at a time — each gated by a test

<div class="hc-timeline mt-4">
  <div class="hc-step"><b>P1</b><span>Skeleton + baseline</span><em>conversion ≈ 5.6%</em></div>
  <div class="hc-step"><b>P2</b><span>Threshold + per-persona policy</span><em>uplift &amp; annoyance</em></div>
  <div class="hc-step"><b>P3</b><span>GBM detection</span><em>ablation vs threshold</em></div>
  <div class="hc-step hl"><b>P3.5</b><span>NiceGUI viewer</span><em>the demo route</em></div>
  <div class="hc-step"><b>P4</b><span>LLM wording</span><em>graceful degradation</em></div>
  <div class="hc-step hl"><b>P5</b><span>LLM persona bots</span><em>efficacy becomes real</em></div>
  <div class="hc-step"><b>P6</b><span>Results consolidation</span><em>REPORT.md</em></div>
</div>

<div class="hc-note mt-5">Every phase swaps one stub for a real component and <strong>re-runs the same harness</strong>. A phase is done only when its acceptance test passes — the test, not judgement, defines "correct."</div>

<style>
.hc-timeline { display:flex; gap:8px; }
.hc-step { flex:1; background:var(--hc-surface); border:1px solid var(--hc-cream-line); border-radius:12px; padding:12px 10px; box-shadow:var(--hc-sh-card); display:flex; flex-direction:column; gap:4px; }
.hc-step b { font:800 1rem var(--hc-font-mono); color:var(--hc-blue); }
.hc-step span { font-size:.74rem; font-weight:700; color:var(--hc-ink); line-height:1.2; }
.hc-step em { font-size:.66rem; font-style:normal; color:var(--hc-ink-3); }
.hc-step.hl { border-color:var(--hc-amber); border-width:2px; }
.hc-step.hl b { color:var(--hc-amber-700); }
</style>

---

<div class="hc-eyebrow">Stack &amp; reproducibility</div>

# Runs from a clean checkout

<div class="grid grid-cols-2 gap-6 mt-3">
  <div class="hc-card">
    <div class="hc-kicker mb-2 t-blue">Engine</div>
    <ul class="tight text-[.84rem]">
      <li>Pure-Python seeded simulator — no randomness outside the agent</li>
      <li><strong>xgboost</strong> GBM + <strong>Weights &amp; Biases</strong> (feature importances logged)</li>
      <li><strong>vLLM</strong> FP8 locally; LoRA fine-tune on <strong>Leonardo</strong> (W&amp;B offline → synced)</li>
    </ul>
  </div>
  <div class="hc-card">
    <div class="hc-kicker mb-2 t-blue">Demo &amp; hygiene</div>
    <ul class="tight text-[.84rem]">
      <li><strong>NiceGUI + Playwright</strong> — the same test code is the headless gate <em>and</em> the on-stage demo</li>
      <li><strong>docker-compose</strong> along the frozen seams: inference · coach · ui</li>
      <li>MIT license · pinned deps · <strong>no secrets in git</strong></li>
    </ul>
  </div>
</div>

<div class="hc-note mt-4">The presentation deliverable and the regression suite are <strong>one artefact</strong> — flip <code>--headed --slowmo</code> and the CI test becomes the rehearsed stage demo.</div>

---
layout: cover
---

<div class="hc-eyebrow">Conversion Coach · Insurance AI / UNIQA</div>

# Decisions in code.<br>Words from the model.

<p class="hc-sub">A measurement substrate first, an inspectable coach on top, and a branded journey where the nudge looks like part of the product.</p>

<div class="mt-8 flex items-center gap-3 text-[.82rem]" style="color:var(--hc-ink-3);font-family:var(--hc-font-mono)">
  <span>docs.zero-one.lumos-consulting.at</span><span>·</span><span>Thank you</span>
</div>
