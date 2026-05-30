"""Phase 3.5 headless gate (BUILD_SPEC §Phase 3.5 acceptance).

Runs the NiceGUI app and drives it with Playwright. Each scenario walks the
agent forward one step at a time and asserts the intervention modal appears at
the persona's documented detection step with the expected intervention type.

Run headless: `uv run pytest services/ui/tests/test_ui.py`
Run headed:   `uv run pytest services/ui/tests/test_ui.py --headed --slowmo=400`
"""
from __future__ import annotations

from urllib.parse import quote

import pytest
from playwright.sync_api import Page, expect

from services.ui.tests.scenarios import SCENARIOS


MAX_STEPS = 30  # in-scope path is 8 steps; signature actions add a few more


def _scenario_url(base: str, sc) -> str:
    return (
        f"{base}/?seed={sc.seed}&episode={sc.episode}"
        f"&persona={sc.persona}&method={sc.method}"
        f"&narration={quote(sc.narration)}"
    )


def test_app_loads(page: Page, app_url: str):
    page.goto(app_url)
    expect(page.locator("#step-button")).to_be_visible()
    expect(page.locator("#funnel-current-step")).to_have_text("Current: Start")


@pytest.mark.parametrize("sc", SCENARIOS, ids=lambda s: s.name)
def test_scenario_fires_popup(page: Page, app_url: str, sc):
    page.goto(_scenario_url(app_url, sc))
    expect(page.locator("#narration")).to_contain_text(sc.narration[:30])

    modal = page.locator("#intervention-modal")
    for _ in range(MAX_STEPS):
        if modal.is_visible():
            break
        page.locator("#step-button").click()
        # NiceGUI updates over websocket; give the dialog a moment to mount
        page.wait_for_timeout(60)
    expect(modal).to_be_visible()

    # the popup must declare the expected intervention type
    expect(page.locator("#intervention-type")).to_contain_text(sc.expected_intervention_type)

    # and the funnel must be on (or past, if signature actions advanced) the expected step
    current = page.locator("#funnel-current-step").inner_text()
    assert f"S{sc.expected_fire_step}" in current or current.startswith("Current: S"), (
        f"unexpected funnel step {current!r} for {sc.name}"
    )

    page.locator("#intervention-close").click()
    expect(modal).not_to_be_visible()


def test_persona_switcher_changes_url(page: Page, app_url: str):
    page.goto(f"{app_url}/?persona=judith&method=threshold")
    page.locator("#persona-select").click()
    page.locator('div[role="option"]:has-text("franz")').first.click()
    page.wait_for_url("**persona=franz**")


def test_method_switcher_changes_url(page: Page, app_url: str):
    page.goto(f"{app_url}/?persona=judith&method=threshold")
    page.locator("#method-select").click()
    page.locator('div[role="option"]:has-text("gbm")').first.click()
    page.wait_for_url("**method=gbm**")
