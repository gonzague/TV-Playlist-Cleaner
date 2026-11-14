"""Web API integration, local access boundaries and background-job lifecycle."""

import io
import json
import threading
import time
from concurrent.futures import CancelledError
from unittest.mock import Mock, patch

import pytest

pytest.importorskip("flask")
from playlist_web import create_app, parse_options  # noqa: E402
from playlist_utils import download_playlist, get_tool_path  # noqa: E402
from validation_pipeline import (
    ValidationCache,
    validate_entries,
    validate_with_retries,
)  # noqa: E402
from tests.test_pipeline_http import media_server  # noqa: E402,F401
from tests.test_validation_pipeline import options  # noqa: E402


@pytest.fixture
def app(tmp_path):
    app = create_app(tmp_path / "web")
    app.config["TESTING"] = True
    yield app
    app.extensions["jobs"].close()


@pytest.fixture
def client(app):
    return app.test_client()


def auth(client):
    return {"X-Playlist-Token": client.get("/api/config").json["token"]}


def upload(client, text=None, options=None, filename="test.m3u"):
    text = (
        text
        if text is not None
        else "#EXTM3U\n#EXTINF:-1,Test\nhttp://example.com/stream\n"
    )
    return client.post(
        "/api/jobs",
        headers=auth(client),
        data={
            "mode": "file",
            "file": (io.BytesIO(text.encode()), filename),
            "options": json.dumps(options or {"validator": "curl", "retries": 0}),
        },
    )


def finished(client, job_id):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json
        if job["state"] in ("completed", "failed", "cancelled"):
            return job
        time.sleep(0.01)
    pytest.fail("Web job did not finish")


def working(entry, timeout):
    return {
        **entry,
        "working": True,
        "quality": "720p",
        "height": 720,
        "width": 1280,
        "method": "curl",
    }


def test_home_and_assets_are_packaged(client):
    page = client.get("/")
    assert page.status_code == 200 and "Vos chaînes" in page.text
    for path in ("/static/app.js", "/static/app.css"):
        assert client.get(path).status_code == 200
    assert "frame-ancestors 'none'" in page.headers["Content-Security-Policy"]
    assert client.get("/api/config").headers["Cache-Control"] == "no-store"


def test_cross_origin_and_dns_rebinding_requests_are_rejected(client):
    assert (
        client.get("/api/config", headers={"Host": "attacker.example"}).status_code
        == 403
    )
    assert (
        client.get(
            "/api/config", headers={"Origin": "https://attacker.example"}
        ).status_code
        == 403
    )
    assert client.post("/api/jobs", data={"mode": "url"}).status_code == 403
    assert (
        client.post(
            "/api/jobs",
            headers=auth(client),
            data={"mode": "url", "url": "file:///etc/passwd"},
        ).status_code
        == 400
    )


@pytest.mark.parametrize(
    "raw",
    [
        {"workers": 0},
        {"timeout": True},
        {"retries": 20},
        {"retry_delay": float("nan")},
        {"cache_ttl": -1},
        {"use_cache": "yes"},
        {"validator": "shell"},
        [],
    ],
)
def test_invalid_settings_are_rejected(raw):
    with pytest.raises(ValueError):
        parse_options(raw)


def test_upload_validation_and_limits(client, app):
    assert upload(client, filename="bad.html").status_code == 400
    assert upload(client, text="").status_code == 400
    app.config["MAX_CONTENT_LENGTH"] = 100
    assert upload(client).status_code == 413


def test_missing_tool_is_reported(client):
    with patch("playlist_web.check_tool_availability", return_value=False):
        response = upload(client)
    assert response.status_code == 400 and "introuvable" in response.json["error"]


def test_uploaded_playlist_has_reports_and_downloads(client, app):
    with patch("playlist_web.check_stream_with_curl", side_effect=working):
        response = upload(client, filename="../../sample.m3u")
        assert response.status_code == 202
        job = finished(client, response.json["id"])
    assert job["state"] == "completed" and job["summary"]["selected"] == 1
    assert job["completed"] == job["total"] == 1
    for kind in ("playlist", "json", "csv"):
        download = client.get(job["downloads"][kind])
        assert download.status_code == 200
        assert "attachment" in download.headers["Content-Disposition"]
    assert (
        client.get(f"/api/jobs/{job['id']}/download/../../cache.json").status_code
        == 404
    )
    assert client.get(f"/api/jobs/{job['id']}/download/cache").status_code == 404
    report = client.get(f"/api/jobs/{job['id']}/results").json
    assert report["streams"][0]["name"] == "Test"
    assert job["source"] == "sample.m3u"


def test_all_invalid_returns_reports_without_empty_playlist(client):
    with patch(
        "playlist_web.check_stream_with_curl",
        side_effect=lambda entry, timeout: {
            **entry,
            "working": False,
            "quality": "failed",
            "error": "404",
            "method": "curl",
        },
    ):
        job = finished(client, upload(client).json["id"])
    assert job["state"] == "completed" and job["summary"]["invalid"] == 1
    assert set(job["downloads"]) == {"json", "csv"}


def test_invalid_m3u_finishes_with_actionable_error(client):
    job = finished(client, upload(client, text="not a playlist").json["id"])
    assert job["state"] == "failed" and "Aucun flux M3U" in job["error"]


def test_cancel_and_single_active_job(client):
    entered, release = threading.Event(), threading.Event()

    def delayed(entry, timeout):
        entered.set()
        release.wait(3)
        return working(entry, timeout)

    with patch("playlist_web.check_stream_with_curl", side_effect=delayed):
        job_id = upload(client).json["id"]
        assert entered.wait(2)
        assert upload(client).status_code == 409
        assert (
            client.post(f"/api/jobs/{job_id}/cancel", headers=auth(client)).status_code
            == 202
        )
        assert client.get(f"/api/jobs/{job_id}").json["state"] == "cancelling"
        release.set()
        job = finished(client, job_id)
    assert job["state"] == "cancelled" and job["downloads"] == {}


@pytest.mark.parametrize("method", ["curl", "ffprobe"])
def test_web_real_download_validation_and_cache(client, media_server, method):
    if not get_tool_path(method):
        pytest.skip(f"{method} unavailable")
    base, counts, _ = media_server

    def run():
        response = client.post(
            "/api/jobs",
            headers=auth(client),
            data={
                "mode": "url",
                "url": base + "/playlist.m3u",
                "options": json.dumps(
                    {"validator": method, "retries": 1, "retry_delay": 0, "timeout": 3}
                ),
            },
        )
        assert response.status_code == 202
        return finished(client, response.json["id"])

    first = run()
    assert first["state"] == "completed"
    assert first["summary"]["selected"] == 2
    assert first["summary"]["invalid"] == first["summary"]["discarded"] == 1
    before = counts["/auth"]
    second = run()
    assert second["summary"]["cached"] == 3
    assert counts["/auth"] == before


def test_preset_uses_configured_sources(client):
    with patch(
        "playlist_web.download_playlist",
        return_value="#EXTINF:-1,Test\nhttp://example.com/tv",
    ) as download, patch("playlist_web.check_stream_with_curl", side_effect=working):
        response = client.post(
            "/api/jobs",
            headers=auth(client),
            data={
                "mode": "preset",
                "preset": "france",
                "options": '{"validator":"curl"}',
            },
        )
        job = finished(client, response.json["id"])
    assert job["state"] == "completed"
    assert (
        download.call_args.args[0] == "https://iptv-org.github.io/iptv/countries/fr.m3u"
    )


def test_progress_callback_preserves_cli_results(tmp_path):
    entries = [
        {"name": "Test", "info": "#EXTINF:-1,Test", "url": "http://example.com/tv"}
    ]
    progress = Mock()
    results = validate_entries(entries, working, "curl", options(tmp_path), progress)
    assert results[0]["working"]
    assert progress.call_args_list[0].args == (0, 1, 0)
    assert progress.call_args_list[-1].args == (1, 1, 1)


def test_cancel_stops_probes_and_downloads_before_start():
    event = threading.Event()
    event.set()
    validate = Mock()
    with pytest.raises(CancelledError):
        validate_with_retries({}, validate, "curl", 5, 2, 10, ValidationCache(), event)
    validate.assert_not_called()
    with patch("playlist_utils.requests.get") as get:
        with pytest.raises(CancelledError):
            download_playlist("http://example.com", cancel_event=event)
    get.assert_not_called()


def test_history_survives_restart_and_new_clients(app, tmp_path):
    first = app.test_client()
    with patch("playlist_web.check_stream_with_curl", side_effect=working) as probe:
        older = finished(first, upload(first, filename="ancienne.m3u").json["id"])
        newest = finished(first, upload(first, filename="recente.m3u").json["id"])
        before = probe.call_count
        # Simulate a report from a release without persisted job metadata.
        directory = tmp_path / "web"
        legacy = directory / older["id"] / "browser.json"
        report = json.loads(legacy.read_text())
        del report["analysis"]
        legacy.write_text(json.dumps(report))
        import os

        os.utime(legacy, (1, 1))
        restarted = create_app(directory)
        try:
            other = restarted.test_client()
            jobs = other.get("/api/jobs").json["jobs"]
            assert [j["id"] for j in jobs] == [newest["id"], older["id"]]
            assert [j["source"] for j in jobs] == ["recente.m3u", "ancienne.m3u"]
            assert other.get(newest["downloads"]["playlist"]).status_code == 200
            assert (
                other.get(f"/api/jobs/{older['id']}/results").json["streams"][0]["name"]
                == "Test"
            )
            assert probe.call_count == before
        finally:
            restarted.extensions["jobs"].close()


def test_history_retains_ten_completed_results(client):
    ids = []
    with patch("playlist_web.check_stream_with_curl", side_effect=working):
        for i in range(11):
            ids.append(
                finished(client, upload(client, filename=f"{i}.m3u").json["id"])["id"]
            )
        failed = finished(client, upload(client, text="not a playlist").json["id"])
    assert failed["state"] == "failed"
    assert [j["id"] for j in client.get("/api/jobs").json["jobs"]] == ids[:0:-1]
    assert client.get(f"/api/jobs/{ids[0]}").status_code == 404
