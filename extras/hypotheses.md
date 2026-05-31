# Validated Logics — Conversion Coach (UNIQA)

This is the hypotheses deliverable referenced from [REPORT.md](../REPORT.md). It
records the **decision logics** the Conversion Coach is built on, the evidence that
validates each one, and — honestly — the boundary of what "validated" means in this
harness.

## What "validated" means here

The coach is a three-stage pipeline of **inspectable code**: `detect` (when) →
`policy.lookup` (which) → `realize` (how). Every claim below is checked against that
code and against the seeded simulator, not against a vibe.

One caveat up front, repeated from the REPORT so nobody over-reads the numbers: in
the scripted harness (Phases 1–4) a *stay*-intervention reduces drop-off by an
**assumed effectiveness parameter** (`intervention_effectiveness.default = 0.45` in
[config.yaml](../config.yaml#L67)). So the uplift magnitudes validate that the
**measurement plumbing and the decision logic are correct** — paired seeds,
per-persona conversion definitions, fired/wasted/saved accounting — **not** that the
wording itself persuades. Persuasiveness becomes a *measured* quantity only when the
LLM persona bots ([simulation/](../simulation/)) read and react to the wording, which
we wired but did not run at scale. The three logics below are validated to the first
standard; H3 is additionally validated on held-out detection data.

All numbers reproduce from a clean checkout: `python runner.py` (H1, H2) and
`python -m training.train_gbm --no-wandb` (H3).

---

## Hypothesis 1 — One unified nudge fails; each segment must be coached at its own drop step

**Claim.** The three in-scope segments abandon for *different reasons* at *different
steps*, so a single global nudge strategy cannot lift all three. The coach must hold
an explicit **per-persona × step** policy.

**Where it comes from.** The persona briefings place each segment's primary exit at a
distinct point in the 15-step funnel:

- **Judith** (Rising Hybrid, ~30% of funnel) hesitates at the **initial price (S4)** —
  she slows down, reads every tariff, and stalls on the "advisory-required" wall.
- **Franz** (Online Affine, ~50%) blasts through the early steps and **bolts at the
  final price (S7)** when it differs from the displayed estimate.
- **Peter** (Service Affine, ~20%) is overwhelmed **early (S1–S3), before price** — too
  many numbers, no "recommended for you", and he reaches for the phone.

This is encoded directly, not as one knob, in [coach/policy.py](../coach/policy.py#L22):
Judith gets a €/day price reframe at S4 and a transparency nudge at S7; Franz gets an
advisory-alternative explainer at S4 and a price-justification at S7; Peter gets an
early callback handoff at S1–S4. The per-persona drop-off priors live in
[config.yaml](../config.yaml#L27) (`judith.p_dropoff.S4 = 0.78`, `franz.p_dropoff.S7
= 0.82`, `peter.p_dropoff.S3 = 0.55`).

**Evidence (Phase 2, paired control vs. coach on identical seeds, `n=10000`).**

| Persona | drop step | without | with Coach | uplift |
|---|---|---|---|---|
| Judith | S4 | 15.4% | 39.8% | **+24.4 pp** |
| Franz  | S7 | 13.0% | 28.7% | **+15.8 pp** |
| Peter  | S1–S3 | 39.2% | 91.9% | **+52.7 pp** |

Because episode *i* is the *same* simulated user with and without the coach (the
per-episode RNG is seeded by `(master_seed, episode_index)` only, never by coach
presence — see [runner.py](../runner.py#L62)), the uplift is a clean counterfactual,
not two unrelated populations.

**Verdict: validated.** Targeting each segment at its documented drop step produces a
positive, persona-specific uplift across all three. A single global policy cell is
empty by construction, so an unsegmented coach would have fired nothing for these
users.

---

## Hypothesis 2 — A handoff is a *win* for Peter and Judith, but a *failure* for Franz

**Claim.** "Route to a human" is not a universally good outcome. The same action
(advisor callback / service contact) must count as **success** for service-affine and
hybrid users and as **failure** for the digital-first user — and the policy must
therefore *never* offer Franz a handoff.

**Where it comes from.** Peter's honest motivation is a *warm handoff to a person*, not
an online purchase ("about 60% of customer-journey activities in his segment happen via
customer service"). Judith will accept an advisor call *if it feels helpful, not
desperate*. Franz, by contrast, "will close the tab immediately" at the words "advisory
consultation required" — pushing him to a human is the abandonment, not the cure.

This polarity is encoded in two places that must agree:

1. **Conversion definitions** in [runner.py](../runner.py#L29): `SERVICE_CONTACT`
   counts as success for `judith` and `peter`, but `franz`'s success set is
   `{"CONVERTED"}` only — a handoff is scored as a loss for him.
2. **Policy table** in [coach/policy.py](../coach/policy.py#L27): Franz has **no
   `handoff` entries at all** — only `stay` nudges (explain the advisory alternative
   at S4, justify the price at S7). The code comment is explicit: *"NO handoff
   entries: pushing Franz to an advisor is a failure for his goal."*

**Sub-finding — advisory-tariff engagement is a *signal*, not a *trigger*.** An earlier
version over-fired on Franz by treating his glance at the advisory-only Opt.Plus/Premium
tariffs as a reason to intervene. The fix ([coach/detection.py](../coach/detection.py#L23)
and [signals.py](../signals.py#L59)): `advisory_tariff_clicked` is *recorded* as a
feature but never itself triggers a nudge. A hover never routes.

**Evidence.** Peter's massive +52.7 pp uplift (H1 table) is *entirely* a handoff effect —
his policy cells are all `("callback", "handoff")` and his win condition is the service
contact. Conversely, the Franz fix holds in the fired/wasted accounting: his
interventions are **not** dominated by unnecessary S4 nudges — wasted-rate **14.2%**,
well under the 40% annoyance gate ([tests/test_phase2_uplift.py](../tests/test_phase2_uplift.py)),
because advisory engagement is a signal, not a trigger. If a handoff were (wrongly)
scored as success for Franz, his "uplift" would be inflated by exactly the routes that
represent him leaving.

**Verdict: validated.** The same routing action carries opposite sign across segments,
and the coach respects it in both the *decision* (no Franz handoff) and the
*measurement* (per-persona success sets).

---

## Hypothesis 3 — A learned detector beats hand-written thresholds, mostly on recall

**Claim.** The hand-tuned threshold rules (S7 price-gap + cancel-hover; S4 long dwell;
early form re-edits; repeated back-nav) catch the *obvious* abandoners but miss most of
them. A GBM trained on `(Signals → abandoned?)` pairs from the same simulator recovers
nearly all of them, at a small precision cost.

**Where it comes from.** The two backends sit behind one frozen
`detect(signals, cfg)` interface ([coach/detection.py](../coach/detection.py#L40)):
`threshold` (Phase 2 baseline) and `gbm` (Phase 3, an xgboost classifier). Swapping
them is a one-line config change (`detection.method`), so the ablation is honest — same
features, same call site.

**Evidence (Phase 3 ablation, held-out seed: train seed 0 / test seed 1).**

| Method | scope | precision | recall | F1 |
|---|---|---|---|---|
| threshold | overall | 0.798 | 0.252 | 0.383 |
| threshold | franz | 0.820 | 0.121 | 0.210 |
| **GBM** | overall | 0.784 | **0.992** | **0.876** |
| GBM | judith | 0.856 | 0.980 | 0.914 |
| GBM | franz | 0.840 | 1.000 | 0.913 |
| GBM | peter | 0.632 | 0.997 | 0.774 |

The GBM trades a sliver of overall precision (0.80 → 0.78) for an enormous recall gain
(0.25 → 0.99). The thresholds are worst exactly where it matters most — Franz, recall
**0.12**: hand rules barely catch the silent digital-first abandoner. The GBM catches
essentially all of them (recall 1.00).

**Inspectability (the rubric's "traceable decision rules").** The model is not a black
box — its feature importances are dumped on every train run:

```
external_tab_opens        0.772
tariff_selected           0.118
tariff_hover_count        0.060
step                      0.032
field_change_count        0.009
```

That top feature is itself a finding: opening a comparison tab (`external_tab_opens`)
is the single strongest abandonment predictor in this population — consistent with
Franz's "comparison-mindset is constant, even mid-conversion" briefing.

**Verdict: validated, with one honest caveat.** The GBM is trained and evaluated on the
*same* synthetic generator (different seeds), so its 0.99 recall partly reflects
learning the generator rather than real users. The decisive test — re-running this
ablation on non-scripted, bot-driven signals — is the top item in *What you'd do with
another 36 hours*.

---

## Summary

| # | Logic | Validated by | Verdict |
|---|---|---|---|
| H1 | Coach each segment at its own drop step; one global nudge fails | Per-persona uplift (+24.4 / +15.8 / +52.7 pp), paired seeds | ✅ |
| H2 | Handoff = win for Peter/Judith, failure for Franz; advisory engagement is a signal, not a trigger | Per-persona success sets + no-handoff policy for Franz; Franz wasted-rate 14.2% < 40% | ✅ |
| H3 | Learned GBM detector beats thresholds, mainly on recall | Held-out ablation: recall 0.25 → 0.99 (Franz 0.12 → 1.00) | ✅ (same-generator caveat) |

## How to reproduce

```bash
python runner.py                          # H1 + H2: baseline + per-persona uplift / fired / wasted
pytest tests/test_phase2_uplift.py        # H2 gate: Franz wasted-rate under 40%
python -m training.train_gbm --no-wandb   # H3: threshold-vs-GBM metrics + feature importances
```

## Not yet validated (the honest boundary)

- **Wording persuasiveness.** Uplift magnitudes in H1/H2 are driven by the assumed
  `intervention_effectiveness = 0.45`, not by measured bot reactions. Real efficacy
  needs N≥2,000 seeded **bot-driven** episodes per persona (LLM wording on vs.
  templates), which the harness supports ([simulation/engine.py](../simulation/engine.py))
  but we did not run at scale.
- **Detector generalisation.** H3 is validated on the synthetic generator only; the
  real test is the same ablation on bot-driven, non-scripted behaviour.
- **The S7 price gap is synthetic.** `final = provisional × (1 + Uniform(0, 0.15))`
  ([config.yaml](../config.yaml#L7)); the real surcharge distribution is a documented
  unknown that would sharpen Franz's S7 trigger.
