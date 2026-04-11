from pathlib import Path


def test_index_template_stops_job_poller_when_fragment_is_missing():
    project_root = Path(__file__).resolve().parents[2]
    template = (project_root / "app" / "templates" / "index.html").read_text(
        encoding="utf-8"
    )

    assert "response.status === 404 || response.status === 410" in template
    assert "clearInterval(window.__jobCardPoller);" in template
    assert "Job No Longer Available" in template
    assert "live polling has stopped" in template