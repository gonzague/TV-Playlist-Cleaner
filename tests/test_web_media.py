"""Logo identity/cache and browser playback integration."""

import json
import time
from unittest.mock import patch

import pytest
import requests

pytest.importorskip("flask")
from playlist_utils import parse_m3u  # noqa: E402
from playlist_web.media import LogoCatalog, http_url, playback_metadata  # noqa: E402
from tests.test_web import app, client, finished, upload, working  # noqa: E402,F401


def test_logo_exact_feed_fallback_and_existing_priority(tmp_path):
    catalog = LogoCatalog(tmp_path)
    catalog.updated = time.time()
    catalog.data = [
        {
            "channel": "News.fr",
            "feed": "French",
            "url": "https://example.org/fr.png",
            "in_use": True,
        },
        {
            "channel": "News.fr",
            "feed": "English",
            "url": "https://example.org/en.png",
            "in_use": True,
        },
        {
            "channel": "Other.fr",
            "feed": None,
            "url": "https://example.org/generic.png",
            "in_use": True,
        },
    ]
    entries = parse_m3u(
        """#EXTM3U
#EXTINF:-1 tvg-id="News.fr@French",News
https://example.org/live.m3u8
#EXTINF:-1 tvg-id="News.fr@English" tvg-logo="https://example.org/custom.png",News English
https://example.org/english.m3u8
#EXTINF:-1 tvg-id="News.fr@Missing",News Missing
https://example.org/missing.m3u8
#EXTINF:-1 tvg-id="Other.fr@HD",Other
https://example.org/other.m3u8
#EXTINF:-1,News
https://example.org/unknown.m3u8
"""
    )
    catalog.enrich(entries)
    assert [e["logo"] for e in entries] == [
        "https://example.org/fr.png",
        "https://example.org/custom.png",
        "",
        "https://example.org/generic.png",
        "",
    ]
    assert 'tvg-logo="https://example.org/fr.png",News' in entries[0]["info"]
    assert (
        parse_m3u("#EXTM3U\n" + entries[0]["info"] + "\n" + entries[0]["url"])[0][
            "name"
        ]
        == "News"
    )


def test_no_network_without_missing_identified_logo(tmp_path):
    catalog = LogoCatalog(tmp_path)
    with patch.object(catalog, "load") as load:
        catalog.enrich(
            parse_m3u("#EXTM3U\n#EXTINF:-1,News\nhttps://example.org/live\n")
        )
    load.assert_not_called()


def test_catalog_disk_cache_stale_fallback_and_cooldown(tmp_path):
    data = [
        {"channel": "News.fr", "url": "https://example.org/logo.png", "in_use": True}
    ]
    cache = tmp_path / "logos.json"
    cache.write_text(json.dumps({"updated": time.time(), "logos": data}))
    catalog = LogoCatalog(tmp_path)
    with patch("playlist_web.media.requests.get") as get:
        assert catalog.load() == data
        get.assert_not_called()
    catalog.updated = 0
    with patch("playlist_web.media.requests.get", side_effect=requests.Timeout) as get:
        assert catalog.load() == data
        assert catalog.load() == data
        assert get.call_count == 1


def test_catalog_fetch_persists_once(tmp_path):
    data = [
        {"channel": "News.fr", "url": "https://example.org/logo.png", "in_use": True}
    ]
    with patch("playlist_web.media.requests.get") as get:
        response = get.return_value.__enter__.return_value
        response.iter_content.return_value = [json.dumps(data).encode()]
        catalog = LogoCatalog(tmp_path)
        assert catalog.load() == data
        assert LogoCatalog(tmp_path).load() == data
        assert get.call_count == 1


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "data:image/svg+xml,evil",
        "file:///etc/passwd",
        "https://user:pass@example.org/a",
        "//example.org/a",
        "https://[broken",
        "https://example.org/a\n",
    ],
)
def test_unsafe_media_urls_rejected(url):
    assert http_url(url) == ""


def test_browser_metadata_preserves_header_requirements():
    entry = {
        "info": "#EXTINF:-1,Test",
        "url": "https://example.org/a.m3u8|User-Agent=Player",
        "directives": "#EXTVLCOPT:http-referrer=https://example.org/",
    }
    meta = playback_metadata(entry)
    assert meta["playback_url"] == "https://example.org/a.m3u8"
    assert meta["needs_headers"] is True
    assert meta["directives"] == entry["directives"]


def test_results_and_individual_m3u_include_logo_and_headers(client):
    playlist = '#EXTM3U\n#EXTINF:-1 tvg-id="News.fr@French",News\n#EXTVLCOPT:http-referrer=https://example.org/\nhttps://example.org/live.m3u8|User-Agent=Player\n'
    logos = [
        {
            "channel": "News.fr",
            "feed": "French",
            "in_use": True,
            "url": "https://example.org/logo.png",
        }
    ]
    with patch("playlist_web.check_stream_with_curl", side_effect=working), patch(
        "playlist_web.media.LogoCatalog.load", return_value=logos
    ):
        job = finished(client, upload(client, playlist).json["id"])
    assert job["state"] == "completed"
    row = client.get(f"/api/jobs/{job['id']}/results").json["streams"][0]
    assert row["logo"] == "https://example.org/logo.png"
    assert row["needs_headers"] and row["channel_id"] == "News.fr@French"
    path = f"/api/jobs/{job['id']}/streams/1/playlist"
    response = client.get(path)
    assert response.status_code == 200
    assert "attachment" in response.headers["Content-Disposition"]
    assert 'tvg-logo="https://example.org/logo.png"' in response.text
    assert "#EXTVLCOPT:http-referrer=https://example.org/" in response.text
    assert "|User-Agent=Player" in response.text
    assert "tvg-logo=" in client.get(job["downloads"]["playlist"]).text
    assert client.get(path.replace("/1/", "/0/")).status_code == 404
    assert client.get(path.replace("/1/", "/2/")).status_code == 404


def test_player_assets_and_csp(client):
    page = client.get("/")
    assert 'id="channel-video"' in page.text
    assert "hls-1.7.4.min.js" in page.text
    assert client.get("/static/vendor/hls-1.7.4.min.js").status_code == 200
    csp = page.headers["Content-Security-Policy"]
    assert "media-src 'self' blob: http: https:" in csp
    assert "script-src 'self';" in csp
