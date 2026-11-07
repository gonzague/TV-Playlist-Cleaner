"""Real CLI/curl/ffprobe checks against a controlled HTTP media server."""

import csv
import io
import json
import subprocess
import sys
import threading
import wave
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from playlist_utils import get_tool_path, parse_m3u

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def media_server():
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\0\0" * 8000)
    media = buffer.getvalue()
    counts = Counter()
    lock = threading.Lock()
    directives = (
        "#EXTVLCOPT:http-user-agent=Playlist-Test/1\n"
        "#EXTVLCOPT:http-referrer=https://player.example/\n"
        "#KODIPROP:inputstream.adaptive.common_headers=Origin=https%3A%2F%2Fplayer.example\n"
        "#KODIPROP:inputstream.adaptive.manifest_headers=X-Key=fixture-key\n"
        "#KODIPROP:inputstream.adaptive.stream_headers=Cookie=session%3Dfixture\n"
    )

    class Handler(BaseHTTPRequestHandler):
        def serve(self, body):
            with lock:
                counts[self.path] += 1
                count = counts[self.path]
            code, payload, content_type = 200, media, "audio/wav"
            if self.path in ("/playlist.m3u", "/retry") and count == 1:
                code, payload = 503, b"temporary failure"
            elif self.path == "/playlist.m3u":
                payload, content_type = playlist.encode(), "audio/x-mpegurl"
            elif self.path == "/auth":
                expected = {
                    "User-Agent": "Playlist-Test/1",
                    "Referer": "https://player.example/",
                    "Origin": "https://player.example",
                    "X-Key": "fixture-key",
                    "Cookie": "session=fixture",
                }
                if any(
                    self.headers.get(name) != value for name, value in expected.items()
                ):
                    code, payload = 403, b"missing headers"
            elif self.path == "/dead":
                code, payload = 404, b"missing"
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            if body:
                self.wfile.write(payload)

        def do_HEAD(self):
            self.serve(False)

        def do_GET(self):
            self.serve(True)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    base = f"http://127.0.0.1:{server.server_port}"
    playlist = (
        f"#EXTM3U\n#EXTINF:-1,TF1\n{directives}{base}/auth\n"
        f"#EXTINF:-1,TF1\n{directives}{base}/auth\n"
        f"#EXTINF:-1,France 2\n{base}/retry\n"
        f"#EXTINF:-1,Missing\n{base}/dead\n"
    )
    # Use a TNT-recognized label for the intentionally invalid stream too.
    playlist = playlist.replace(
        f"#EXTINF:-1,Missing\n{base}/dead", f"#EXTINF:-1,M6\n{base}/dead"
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield base, counts, directives
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


@pytest.mark.parametrize(
    "script,method",
    [
        ("cleaner.py", "curl"),
        ("cleaner.py", "ffprobe"),
        ("cleaner_advanced.py", "ffprobe"),
        ("cleaner_multi_source.py", "ffprobe"),
        ("cleaner_tnt.py", "ffprobe"),
    ],
)
def test_real_headers_retries_reports_and_cache(script, method, media_server, tmp_path):
    if not get_tool_path(method):
        pytest.skip(f"{method} unavailable")
    base, counts, directives = media_server
    output, cache = tmp_path / "out.m3u", tmp_path / "cache.json"
    report_json, report_csv = tmp_path / "report.json", tmp_path / "report.csv"
    source_flag = (
        "--url" if script in ("cleaner.py", "cleaner_advanced.py") else "--sources"
    )
    command = [
        sys.executable,
        str(ROOT / script),
        source_flag,
        base + "/playlist.m3u",
        "--output",
        str(output),
        "--cache",
        str(cache),
        "--report-json",
        str(report_json),
        "--report-csv",
        str(report_csv),
        "--timeout",
        "3",
        "--retries",
        "1",
        "--retry-delay",
        "0",
    ]
    if script == "cleaner.py":
        command += ["--validator", method]

    def run(extra=()):
        process = subprocess.run(
            command + list(extra),
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert process.returncode == 0, process.stderr
        return json.loads(report_json.read_text())

    first = run()
    assert first["output_written"]
    assert first["summary"]["total"] == 4
    assert first["summary"]["selected"] == 2
    assert first["summary"]["discarded"] == first["summary"]["invalid"] == 1
    assert first["streams"][2]["attempts"] == 2
    assert counts["/dead"] == 1  # Permanent 404 must not be retried.
    assert counts["/playlist.m3u"] == 2  # Download recovered from 503 too.
    with report_csv.open(newline="") as handle:
        assert len(list(csv.DictReader(handle))) == 4
    saved = parse_m3u(output.read_text())
    assert len(saved) == 2
    assert (
        next(row for row in saved if row["name"] == "TF1")["directives"]
        == directives.strip()
    )
    assert "fixture-key" not in cache.read_text()
    assert base not in cache.read_text()

    before = counts.copy()
    second = run()
    assert second["summary"]["cached"] == 3
    assert second["summary"]["attempts"] == 1
    assert counts["/auth"] == before["/auth"]
    assert counts["/retry"] == before["/retry"]
    assert counts["/dead"] == before["/dead"] + 1

    third = run(["--cache-ttl", "0"])
    assert third["summary"]["cached"] == 0
    assert counts["/auth"] > before["/auth"]
    assert counts["/retry"] > before["/retry"]
