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
