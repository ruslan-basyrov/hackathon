"""Phase 3.5 demo walkthrough (BUILD_SPEC §Phase 3.5 demo path).

The on-stage script. Identical scenarios to `test_ui.py` but with audience-read
pauses around each popup and a screenshot per persona. Run headed and slowed:

  uv run pytest services/ui/tests/test_demo.py --headed --slowmo=400 --video=on

Videos and screenshots land in `demo_videos/` (gitignored). When the live demo
is at risk (network, USB, projector), use the recorded video as the fallback.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import Page, expect

from services.ui.tests.scenarios import SCENARIOS


DEMO_DIR = Path("demo_videos")
DEMO_DIR.mkdir(exist_ok=True)
MAX_STEPS = 30


def test_demo_walkthrough(page: Page, app_url: str):
    """One run, three scenarios, one screenshot each. Designed to be watchable
    at slow_mo=400 - takes ~30s end-to-end."""
    page.set_viewport_size({"width": 1400, "height": 900})

    for sc in SCENARIOS:
        url = (
            f"{app_url}/?seed={sc.seed}&episode={sc.episode}"
            f"&persona={sc.persona}&method={sc.method}"
            f"&narration={quote(sc.narration)}"
        )
        page.goto(url)
        page.wait_for_timeout(1200)  # narration read time

        modal = page.locator("#intervention-modal")
        for _ in range(MAX_STEPS):
            if modal.is_visible():
                break
            page.locator("#step-button").click()
            page.wait_for_timeout(60)
        expect(modal).to_be_visible()

        page.wait_for_timeout(3000)  # audience reads the popup
        page.screenshot(path=str(DEMO_DIR / f"{sc.name}.png"))
        page.locator("#intervention-close").click()
        page.wait_for_timeout(600)
