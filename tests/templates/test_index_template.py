# tests/templates/test_index_template.py
from __future__ import annotations

from pathlib import Path


def test_index_template_stops_job_poller_when_fragment_is_missing():
    template = Path("app/templates/index.html").read_text(encoding="utf-8")

    assert "response.status === 404 || response.status === 410" in template
    assert "clearInterval(window.__jobCardPoller);" in template
    assert "Job No Longer Available" in template