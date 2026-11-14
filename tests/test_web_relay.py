"""Exercise header-bearing playback against an actual HTTP origin."""

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import pytest

pytest.importorskip("flask")
from tests.test_web import app, auth, client, finished, upload  # noqa: E402,F401


@pytest.fixture
def origin_server():
    seen = []

    class Media(BaseHTTPRequestHandler):
        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            path = urlsplit(self.path).path
            seen.append((self.path, self.headers.get("Range")))
            if (
                self.headers.get("User-Agent") != "TestPlayer"
                or self.headers.get("Referer") != "https://provider.example/"
            ):
                self.send_error(403)
                return
            resources = {
                "/root": b"#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=40000\nvideo/list.m3u8\n",
                "/video/list.m3u8": b'#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI="key?k=a,b"\n#EXTINF:2,\npart.ts\n',
                "/video/key": b"0" * 16,
                "/video/part.ts": b"0123456789abcdef",
                "/foreign": b"#EXTM3U\nhttps://another.example/segment.ts\n",
            }
            if path in ("/jump", "/escape"):
                self.send_response(302)
                self.send_header(
                    "Location",
                    "/root" if path == "/jump" else "https://another.example/target",
                )
                self.end_headers()
                return
            body = resources[path]
            partial = self.headers.get("Range") == "bytes=4-7"
            self.send_response(206 if partial else 200)
            if partial:
                self.send_header("Content-Range", "bytes 4-7/16")
                body = body[4:8]
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Media)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:" + str(server.server_port), seen
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def create_relay(client, url):
    playlist = f"#EXTM3U\n#EXTINF:-1,Test\n#EXTVLCOPT:http-referrer=https://provider.example/\n{url}|User-Agent=TestPlayer\n"
    job = finished(client, upload(client, playlist).json["id"])
    path = f"/api/jobs/{job['id']}/streams/1/playback"
    assert client.post(path).status_code == 403
    start = client.post(path, headers=auth(client))
    assert start.status_code == 200
    return start.json["url"]


def test_nested_hls_and_ranges(client, origin_server):
    origin, seen = origin_server
    root_path = create_relay(client, origin + "/jump")
    master = client.get(root_path)
    assert master.mimetype == "application/vnd.apple.mpegurl"
    media = client.get(master.text.splitlines()[-1]).text.splitlines()
    key = media[1].split('URI="')[1].rstrip('"')
    assert client.get(key).data == b"0" * 16
    assert ("/video/key?k=a,b", None) in seen
    segment = client.get(media[-1], headers={"Range": "bytes=4-7"})
    assert segment.status_code == 206
    assert segment.headers["Content-Range"] == "bytes 4-7/16"
    assert segment.data == b"4567"
    assert client.get(media[-1], headers={"Range": "invalid"}).status_code == 416
    assert client.get(root_path.replace("/main", "/arbitrary")).status_code == 404


@pytest.mark.parametrize("path", ["/foreign", "/escape"])
def test_foreign_resource_never_receives_headers(client, origin_server, path):
    from unittest.mock import patch
    from tests.test_web import working

    origin, seen = origin_server
    with patch("playlist_web.check_stream_with_curl", side_effect=working):
        root_path = create_relay(client, origin + path)
    assert client.get(root_path).status_code == 502
    assert seen == [(path, None)]
