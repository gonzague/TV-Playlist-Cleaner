"""Regression coverage for real playlist formats, validation and safe output."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import Mock, patch

import pytest
import requests

import cleaner
from cleaner_multi_source import parse_m3u_with_source
from cleaner_tnt import parse_m3u_tnt_filter
from playlist_utils import (
    check_stream_with_curl,
    check_stream_with_ffprobe,
    download_playlist,
    filter_best_quality,
    get_tool_path,
    parse_m3u,
    write_playlist,
)


@pytest.fixture
def entry():
    return {"name": "TF1", "info": "#EXTINF:-1,TF1", "url": "http://example.com/tv"}


@pytest.mark.parametrize(
    "parser", [parse_m3u, parse_m3u_with_source, parse_m3u_tnt_filter]
)
def test_parser_preserves_player_options_and_skips_incomplete_entries(parser, tmp_path):
    content = (
        "\ufeff#EXTM3U\r\n#EXTINF:-1,Incomplete\r\n"
        '  #EXTINF:-1 group-title="France, TV",TF1\r\n\r\n'
        "#EXTVLCOPT:http-referrer=https://example.com/\r\n"
        "#KODIPROP:inputstream=inputstream.adaptive\r\n"
        " https://example.com/tv\r\n"
        "#EXTINF:-1,No URL\r\n"
    )
    entries = parser(content)
    assert len(entries) == 1
    assert entries[0]["name"] == "TF1"
    assert entries[0]["url"] == "https://example.com/tv"
    output = tmp_path / "out.m3u"
    write_playlist(entries, output)
    reread = parse_m3u(output.read_text(encoding="utf-8"))
    assert reread[0]["info"] == entries[0]["info"]
    assert reread[0]["directives"] == entries[0]["directives"]


@pytest.mark.parametrize("failure", ["http", "size", "stream", None])
def test_download_closes_response_on_every_path(failure):
    response = Mock(headers={}, status_code=503)
    response.iter_content.return_value = [b"\xef\xbb\xbf#EXTM3U\n"]
    if failure == "http":
        response.raise_for_status.side_effect = requests.HTTPError(response=response)
    elif failure == "size":
        response.headers = {"Content-Length": str(100 * 1024 * 1024)}
    elif failure == "stream":
        response.iter_content.side_effect = requests.ConnectionError("interrupted")
    with patch("playlist_utils.requests.get", return_value=response):
        result = download_playlist("https://example.com/tv.m3u")
    assert result == (None if failure else "#EXTM3U\n")
    response.close.assert_called_once()


@pytest.mark.parametrize(
    "output",
    [
        "not json",
        "{}",
        "[]",
        '{"streams": []}',
        '{"streams": [{"codec_type": "data"}]}',
    ],
)
def test_ffprobe_rejects_unusable_results(entry, output):
    with patch("playlist_utils.get_tool_path", return_value="/usr/bin/ffprobe"), patch(
        "playlist_utils.subprocess.run", return_value=Mock(returncode=0, stdout=output)
    ):
        result = check_stream_with_ffprobe(entry)
    assert not result["working"]
    assert result["error"]


def test_ffprobe_selects_highest_video_resolution(entry):
    output = {
        "streams": [
            {"codec_type": "video", "width": 1280, "height": 720},
            {"codec_type": "video", "width": 3840, "height": 2160},
        ]
    }
    with patch("playlist_utils.get_tool_path", return_value="/usr/bin/ffprobe"), patch(
        "playlist_utils.subprocess.run",
        return_value=Mock(returncode=0, stdout=json.dumps(output)),
    ):
        result = check_stream_with_ffprobe(entry)
    assert result["working"]
    assert result["quality"] == "2160p"


def test_write_failure_keeps_existing_playlist(entry, tmp_path):
    output = tmp_path / "out.m3u"
    output.write_text("original", encoding="utf-8")
    with patch("playlist_utils.os.replace", side_effect=OSError("disk error")):
        with pytest.raises(OSError):
            write_playlist([entry], output)
    assert output.read_text(encoding="utf-8") == "original"
    assert list(tmp_path.iterdir()) == [output]


def test_quality_selection_uses_normalized_name_and_stable_tie_break():
    entries = parse_m3u_with_source(
        "#EXTINF:-1,TF1 HD [FR]\nhttp://example.com/a\n"
        "#EXTINF:-1,tf1\nhttp://example.com/b\n"
    )
    for entry in entries:
        entry.update(working=True, height=1080, width=1920)
    result = filter_best_quality(entries)
    assert len(result) == 1
    assert result == filter_best_quality(list(reversed(entries)))


@pytest.fixture
def http_server():
    class Handler(BaseHTTPRequestHandler):
        def do_HEAD(self):
            if self.path in ("/redirect", "/missing-redirect"):
                self.send_response(302)
                target = "/ok" if self.path == "/redirect" else "/missing"
                self.send_header("Location", target)
            else:
                self.send_response(200 if self.path == "/ok" else 404)
                self.send_header("Content-Type", "video/mp4")
            self.end_headers()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


@pytest.mark.skipif(not get_tool_path("curl"), reason="curl unavailable")
@pytest.mark.parametrize(
    "path,working", [("/redirect", True), ("/missing-redirect", False)]
)
def test_real_curl_checks_redirect_destination(entry, http_server, path, working):
    entry["url"] = http_server + path
    result = check_stream_with_curl(entry, timeout=2)
    assert result["working"] is working
    if working:
        assert result["content_type"] == "video/mp4"
    else:
        assert "404" in result["error"]


@pytest.mark.parametrize(
    "args",
    [
        ["--workers", "0"],
        ["--timeout", "61"],
        ["--input", "a", "--url", "https://example.com"],
    ],
)
def test_cli_rejects_invalid_arguments(args):
    with pytest.raises(SystemExit) as exc:
        cleaner.parse_arguments(args)
    assert exc.value.code == 2


@pytest.mark.parametrize("working", [True, False])
def test_cli_local_input_and_exit_status(tmp_path, working):
    source = tmp_path / "input.m3u"
    source.write_text(
        "#EXTM3U\n#EXTINF:-1,TF1\nhttp://example.com/tv\n", encoding="utf-8"
    )
    output = tmp_path / "out.m3u"
    output.write_text("original", encoding="utf-8")
    with patch("cleaner.check_tool_availability", return_value=True), patch(
        "cleaner.check_stream_with_curl",
        side_effect=lambda entry, timeout: {
            **entry,
            "working": working,
            "quality": "unknown",
        },
    ), patch("cleaner.download_playlist") as download:
        status = cleaner.main(["--input", str(source), "--output", str(output)])
    download.assert_not_called()
    assert status == (0 if working else 1)
    if working:
        assert len(parse_m3u(output.read_text(encoding="utf-8"))) == 1
    else:
        assert output.read_text(encoding="utf-8") == "original"
