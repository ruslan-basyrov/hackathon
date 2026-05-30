"""Phase 3.5 customer-facing route (`/journey`).

The journey view auto-plays through an episode and pops a branded modal when
the coach fires. Tests verify:
  * the page renders the funnel progress + per-step content
  * each scenario reaches its expected intervention popup, with the expected
    intervention type, with auto-play OFF in the URL contract (autoplay_ms is
    larger so a test still has time to assert, but determinism is by seed).

The on-stage demo (`test_demo.py`) drives this same route headed + slowmo.
"""
from __future__ import annotations

from urllib.parse import quote

import pytest
from playwright.sync_api import Page, expect

from services.ui.tests.scenarios import SCENARIOS


# how long we'll wait for a popup to appear under auto-play (ms)
POPUP_WAIT_MS = 30_000


def _scenario_url(base: str, sc) -> str:
    # use a fast auto-play so the test finishes quickly; the on-stage path
    # overrides this via --slowmo, not via this URL param
    return (
        f"{base}/journey?seed={sc.seed}&episode={sc.episode}"
        f"&persona={sc.persona}&method={sc.method}"
        f"&narration={quote(sc.narration)}"
        f"&autoplay_ms=120"
    )


def test_journey_loads(page: Page, app_url: str):
    page.goto(f"{app_url}/journey?persona=judith&method=threshold&autoplay_ms=120")
    expect(page.locator("#journey-page")).to_be_visible()
    expect(page.locator("#journey-step-label")).to_be_visible()


@pytest.mark.parametrize("sc", SCENARIOS, ids=lambda s: s.name)
def test_scenario_fires_popup_on_journey(page: Page, app_url: str, sc):
    page.goto(_scenario_url(app_url, sc))
    if sc.narration:
        expect(page.locator("#journey-narration")).to_contain_text(sc.narration[:30])
    popup = page.locator("#journey-popup")
    expect(popup).to_be_visible(timeout=POPUP_WAIT_MS)
    expect(page.locator("#journey-popup-type")).to_contain_text(sc.expected_intervention_type)
    # Closing the popup resumes auto-play; a later step in the same journey may
    # legitimately fire a second intervention (e.g. Judith S4 price_reframe ->
    # S7 explain_price). The contract here is "popup appeared with right type",
    # not "popup never reopens".
    page.locator("#journey-popup-close").click()


def test_journey_persona_switcher(page: Page, app_url: str):
    page.goto(f"{app_url}/journey?persona=judith&method=threshold&autoplay_ms=99999")
    page.locator("#journey-persona-select").click()
    page.locator('div[role="option"]:has-text("franz")').first.click()
    page.wait_for_url("**/journey**persona=franz**")


def test_interactive_mode_user_drives(page: Page, app_url: str):
    """In interactive mode the human is the driver. We simulate a Peter-style
    user: click Get-a-quote, click Doctor, click Just-me, then re-edit the
    DOB twice on S3 - the second click should push field_change_count to 2
    while max_steps_completed is still < 4, firing the `early_overwhelm` rule
    and opening the popup."""
    page.goto(
        f"{app_url}/journey?persona=peter&method=threshold&mode=interactive"
    )
    # walk forward into the funnel
    page.locator("#journey-continue").click()                # S0 -> S1
    page.locator("#journey-card-doctor").click()             # S1 -> S2 (select + continue)
    page.locator("#journey-card-myself").click()             # S2 -> S3 (select + continue)
    page.wait_for_timeout(150)
    # now on S3 - two field re-edits should trip early_overwhelm
    page.locator("#journey-edit-dob").click()
    page.wait_for_timeout(150)
    page.locator("#journey-edit-dob").click()
    expect(page.locator("#journey-popup")).to_be_visible(timeout=5000)
    expect(page.locator("#journey-popup-type")).to_contain_text("callback")


def test_interactive_back_button_navigates_and_increments_count(page: Page, app_url: str):
    """The in-page Back button emits a `back` Action: it moves backward in the
    funnel via the state machine's PREV table AND increments back_nav_count.
    Two clicks should trip the `repeated_back_nav` rule (>= 2) and fire a
    popup (whichever the persona's policy hooks - for judith on S4, the
    s4_dwell wins precedence; for global on S2, back_nav is the trigger).
    Here we just assert the funnel actually moves back and the rules panel
    reflects the incremented count."""
    page.goto(
        f"{app_url}/journey?persona=judith&method=threshold&mode=interactive"
    )
    page.locator("#journey-continue").click()        # S0 -> S1
    page.locator("#journey-card-doctor").click()     # S1 -> S2
    page.locator("#journey-card-myself").click()     # S2 -> S3
    page.wait_for_timeout(200)
    # currently on S3 - press Back twice
    expect(page.locator("#journey-step-label")).to_contain_text("Step 3 of 7")
    page.locator("#journey-back").click()            # S3 -> S2
    page.wait_for_timeout(200)
    expect(page.locator("#journey-step-label")).to_contain_text("Step 2 of 7")
    # the rules panel should now show back_nav_count = 1
    expect(page.locator("#journey-rules")).to_contain_text("back_nav_count >= 2")
    expect(page.locator("#journey-rules")).to_contain_text("1")


def test_interactive_repeated_back_nav_fires_popup_anywhere(page: Page, app_url: str):
    """Two `back` clicks should fire a popup REGARDLESS of persona / current
    step. The persona policy (e.g. Judith) has no entry for S1, but the coach
    falls back to a generic `back_nav_help` intervention when detection's
    reason is `repeated_back_nav`. This is the "simple, fires anywhere" rule
    the user explicitly asked for."""
    page.goto(
        f"{app_url}/journey?persona=judith&method=threshold&mode=interactive"
    )
    page.locator("#journey-continue").click()       # S0 -> S1
    page.locator("#journey-card-doctor").click()    # S1 -> S2
    # press Back twice. After the 2nd, back_nav_count = 2, rule trips.
    page.locator("#journey-back").click()           # S2 -> S1
    page.wait_for_timeout(150)
    page.locator("#journey-back").click()           # S1 -> S1 (state no-op, signal recorded)
    expect(page.locator("#journey-popup")).to_be_visible(timeout=5000)
    expect(page.locator("#journey-popup-type")).to_contain_text("back_nav_help")


def test_interactive_mode_watchdog_fires_on_dwell(page: Page, app_url: str):
    """Sit on the S4 tariff page long enough for `dwell_current_s` to exceed
    the threshold (25s in config.yaml). The 1s watchdog should detect dwell
    and open the popup with `price_reframe` (Judith's S4 intervention)."""
    page.goto(
        f"{app_url}/journey?persona=judith&method=threshold&mode=interactive"
    )
    page.locator("#journey-continue").click()                # S0 -> S1
    page.locator("#journey-card-doctor").click()             # S1 -> S2
    page.locator("#journey-card-myself").click()             # S2 -> S3
    page.locator("#journey-continue").click()                # S3 -> S4
    # we're now on S4 - the watchdog should fire within ~26s
    expect(page.locator("#journey-popup")).to_be_visible(timeout=35_000)
    expect(page.locator("#journey-popup-type")).to_contain_text("price_reframe")
