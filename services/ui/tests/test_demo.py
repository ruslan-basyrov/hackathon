"""Phase 3.5 demo walkthrough — the on-stage path (BUILD_SPEC §Phase 3.5).

Drives the customer-facing `/journey` route under auto-play. Audience sees a
real-looking insurance signup; the page transitions through the funnel; the
coach popup appears overlaid on the actual product page when detection fires.

  uv run pytest services/ui/tests/test_demo.py --headed --slowmo=400 \\
      --video=on --output=demo_videos

Each scenario screenshots with the popup open. The video covers the whole
walkthrough as the stage-day fallback.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import Page, expect

from services.ui.tests.scenarios import SCENARIOS


DEMO_DIR = Path("demo_videos")
DEMO_DIR.mkdir(exist_ok=True)


# In the demo we want a watchable pace, NOT the fast one the headless test uses.
DEMO_AUTOPLAY_MS = 750
POPUP_WAIT_MS = 60_000


def test_demo_walkthrough(page: Page, app_url: str):
    page.set_viewport_size({"width": 1400, "height": 900})

    for sc in SCENARIOS:
        url = (
            f"{app_url}/journey?seed={sc.seed}&episode={sc.episode}"
            f"&persona={sc.persona}&method={sc.method}"
            f"&narration={quote(sc.narration)}"
            f"&autoplay_ms={DEMO_AUTOPLAY_MS}"
        )
        page.goto(url)
        page.wait_for_timeout(1200)   # let the audience read the narration

        popup = page.locator("#journey-popup")
        expect(popup).to_be_visible(timeout=POPUP_WAIT_MS)

        page.wait_for_timeout(3000)   # audience reads the intervention text
        page.screenshot(path=str(DEMO_DIR / f"{sc.name}.png"))
        page.locator("#journey-popup-close").click()
        page.wait_for_timeout(800)
