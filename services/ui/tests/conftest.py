"""Pytest fixtures for Phase 3.5 UI tests.

`app_url` starts the NiceGUI app on a free port in a subprocess (cwd = repo root)
and yields the base URL. The subprocess is torn down at session end.

`pytest-playwright` provides the `page` fixture. The headless gate runs
`pytest services/ui/tests/`; the headed demo runs the same code with
`--headed --slowmo=400 --video=on` (BUILD_SPEC §Phase 3.5 acceptance command).
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]


def _free_port() -> int:
    s = socket.socket()
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _wait_for_server(url: str, timeout: float = 30.0) -> None:
    start = time.time()
    last_err = None
    while time.time() - start < timeout:
        try:
            with urlopen(url, timeout=1) as r:
                if r.status < 500:
                    return
        except Exception as e:
            last_err = e
            time.sleep(0.3)
    raise RuntimeError(f"NiceGUI server did not start at {url}: {last_err}")


@pytest.fixture(scope="session")
def app_url():
    port = _free_port()
    # NiceGUI checks PYTEST_CURRENT_TEST and hijacks the port when "in pytest"
    # (for its own Screen fixture). Strip it so the subprocess behaves normally.
    env = {k: v for k, v in os.environ.items() if k != "PYTEST_CURRENT_TEST"}
    env.update({
        "NICEGUI_PORT": str(port),
        "PYTHONPATH": str(REPO_ROOT),
    })
    log_path = REPO_ROOT / "test-results" / "nicegui_server.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(log_path, "w")
    proc = subprocess.Popen(
        [sys.executable, "-m", "services.ui.app"],
        env=env,
        cwd=str(REPO_ROOT),
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    url = f"http://localhost:{port}"
    try:
        _wait_for_server(url)
        yield url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        log_file.close()
