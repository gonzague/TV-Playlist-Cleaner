"""Receiver media transport, local-only controls and Cast acknowledgement."""

from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import urljoin, urlsplit
from uuid import uuid4

import pytest
import requests

pytest.importorskip("flask")
from playlist_web.relay import Playback  # noqa: E402
from playlist_web.television import Television  # noqa: E402
from tests.test_web import app, client, auth  # noqa: E402,F401
from tests.test_web_relay import origin_server  # noqa: E402,F401


def test_bfm_cdn_keeps_sensitive_headers_at_origin():
    root = "https://ncdn-live-bfm.pfd.sfr.net/playlist"
    edge = "https://edge.pfd.sfr.net/manifest"
    playback = Playback({"url": root + "|User-Agent=player"})
    assert playback.permits(edge)
    for target in (
        edge.replace("https:", "http:"),
        edge.replace(".net/", ".net.invalid/"),
        edge.replace(".net/", ".net:444/"),
    ):
        assert not playback.permits(target)
    assert not Playback({"url": root + "|User-Agent=player&Cookie=session"}).permits(
        edge
    )


def test_receiver_only_serves_generated_media(monkeypatch, origin_server):
    origin, seen = origin_server
    tv = Television()
    monkeypatch.setattr(tv, "address", lambda peer: "127.0.0.1")
    try:
        url = tv.share(
            {
                "url": origin + "/root|User-Agent=TestPlayer",
                "directives": "#EXTVLCOPT:http-referrer=https://provider.example/",
                "needs_headers": True,
            }
        )
        master = requests.get(url, timeout=2)
        master.raise_for_status()
        assert master.headers["Access-Control-Allow-Origin"] == "*"
        variant = urljoin(url, master.text.splitlines()[-1])
        part = urljoin(url, requests.get(variant, timeout=2).text.splitlines()[-1])
        assert requests.get(part, timeout=2).content == b"0123456789abcdef"
        assert requests.get(urljoin(url, "/api/config"), timeout=2).status_code == 404
        key = urlsplit(url).path.split("/")[2]
        tv.sessions[key] = (tv.sessions[key][0], float("-inf"))
        assert requests.get(url, timeout=2).status_code == 404
    finally:
        tv.close()


def test_cast_checks_receiver_state(monkeypatch):
    tv = Television()
    key = uuid4()
    tv.devices[str(key)] = SimpleNamespace(uuid=key, host="192.0.2.1")
    row = {
        "needs_headers": False,
        "playback_url": "https://example.org/live.m3u8",
        "name": "Live",
    }
    receiver, browser = Mock(), Mock()
    media = receiver.media_controller
    media.status.content_id = row["playback_url"]
    media.status.player_state = "PLAYING"
    lookup = Mock(return_value=([receiver], browser))
    monkeypatch.setattr("playlist_web.television.get_listed_chromecasts", lookup)
    tv.cast(row, str(key))
    media.play_media.assert_called_once_with(
        row["playback_url"], "application/x-mpegURL", title="Live", stream_type="LIVE"
    )
    receiver.disconnect.assert_called_once()
    browser.stop_discovery.assert_called_once()


def test_picker_and_control_access(client):
    page = client.get("/").text
    assert 'id="cast-picker"' in page and 'id="airplay-picker"' in page
    assert client.post("/api/television/devices").status_code == 403
    assert (
        client.post(
            "/api/jobs/none/streams/1/television/airplay", headers=auth(client)
        ).status_code
        == 404
    )
