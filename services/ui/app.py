"""NiceGUI entry point for the Conversion Coach viewer (BUILD_SPEC §Phase 3.5).

Two routes share the same Session + URL contract:
  * `/`         — debug viewer: funnel strip, signals panel, popup
                  (`services/ui/debug_view.py`)
  * `/journey`  — customer-facing stylized website with auto-play
                  (`services/ui/journey_view.py`) — the on-stage demo route

URL params (read by both routes):
  ?seed=N&episode=N&persona=judith|franz|peter|global
   &method=threshold|gbm&gbm_threshold=0.5..1.0&narration=...
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# project root must be on sys.path when run as a module
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from nicegui import ui  # noqa: E402

from services.ui import debug_view, journey_view  # noqa: E402


@ui.page("/")
def index(
    seed: int = 0, episode: int = 0,
    persona: str = "judith", method: str = "threshold",
    gbm_threshold: float = 0.85, narration: str = "",
):
    debug_view.render(seed=seed, episode=episode, persona=persona,
                      method=method, gbm_threshold=gbm_threshold,
                      narration=narration)


@ui.page("/journey")
def journey(
    seed: int = 0, episode: int = 0,
    persona: str = "judith", method: str = "threshold",
    gbm_threshold: float = 0.85, narration: str = "",
    autoplay_ms: int = 900, mode: str = "auto",
):
    journey_view.render(seed=seed, episode=episode, persona=persona,
                        method=method, gbm_threshold=gbm_threshold,
                        narration=narration, autoplay_ms=autoplay_ms,
                        mode=mode)


def main():
    port = int(os.environ.get("NICEGUI_PORT", "8080"))
    ui.run(port=port, show=False, reload=False,
           title="Conversion Coach", favicon=None)


if __name__ in {"__main__", "__mp_main__"}:
    main()
