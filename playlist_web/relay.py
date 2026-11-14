"""Local media relay scoped to an analysed stream and its HLS references."""

import hashlib
import re
import secrets
import threading
from collections import OrderedDict
from itertools import chain
from urllib.parse import urljoin, urlsplit

import requests
from flask import Response, abort, request, url_for
from urllib3.exceptions import HTTPError as TransportError

from playlist_utils import stream_request
from .media import http_url

# The player supplies Range. Requests manages transport headers itself.
PLAYBACK_HEADERS = {
    "user-agent",
    "referer",
    "origin",
    "authorization",
    "cookie",
    "accept",
    "accept-language",
}
URI_ATTR = re.compile(r'(?:^|[:,])(?:[A-Z0-9-]+)=(?:"[^"]*"|[^,]*)')
MANIFEST_LIMIT = 2 * 1024 * 1024


def origin(url):
    parts = urlsplit(url)
    return (
        parts.scheme,
        parts.hostname,
        parts.port or (443 if parts.scheme == "https" else 80),
    )


class Playback:
    def __init__(self, row):
        url, self.headers = stream_request(row)
        if not http_url(url) or not self.headers:
            raise ValueError("Adresse ou en-têtes de lecture indisponibles.")
        if any(
            name not in PLAYBACK_HEADERS and not name.startswith("x-")
            for name in self.headers
        ):
            raise ValueError("Ce jeu d’en-têtes nécessite VLC.")
        self.origin = origin(url)
        self.root = url
        self.key = secrets.token_urlsafe(24)
        self.resources = OrderedDict()
        self.lock = threading.Lock()

    def path(self, url):
        if not http_url(url) or origin(url) != self.origin:
            raise ValueError(
                "Le flux utilise une autre origine. Ouvrez le M3U dans VLC."
            )
        key = hashlib.sha256(url.encode()).hexdigest()
        with self.lock:
            self.resources[key] = url
            self.resources.move_to_end(key)
            if len(self.resources) > 4096:
                self.resources.popitem(last=False)
        return url_for("relay_media", session=self.key, resource=key)

    def resolve(self, key):
        if key == "main":
            return self.root
        with self.lock:
            return self.resources.get(key)

    def manifest(self, data, base):
        def reference(uri):
            if "{$" in uri:
                raise ValueError("Variable HLS non prise en charge.")
            return self.path(urljoin(base, uri))

        def attribute(match):
            prefix, value = match.group().split("=", 1)
            if prefix.lstrip(":,") in ("URI", "SERVER-URI") and value.startswith('"'):
                return prefix + '="' + reference(value[1:-1]) + '"'
            return match.group()

        lines = []
        for line in data.decode("utf-8-sig").splitlines():
            line = line.strip()
            if line.startswith("#EXT"):
                line = URI_ATTR.sub(attribute, line)
            elif line and not line.startswith("#"):
                line = reference(line)
            lines.append(line)
        return "\n".join(lines) + "\n"


class PlaybackPool:
    def __init__(self):
        self.sessions = OrderedDict()
        self.lock = threading.Lock()

    def create(self, row):
        playback = Playback(row)
        with self.lock:
            self.sessions[playback.key] = playback
            if len(self.sessions) > 16:
                self.sessions.popitem(last=False)
        return url_for("relay_media", session=playback.key, resource="main")

    def get(self, key):
        with self.lock:
            if key not in self.sessions:
                abort(404)
            self.sessions.move_to_end(key)
            return self.sessions[key]


def media_response(playback, resource):
    url = playback.resolve(resource)
    if not url:
        abort(404)
    headers = {**playback.headers, "accept-encoding": "identity"}
    if "Range" in request.headers:
        value = request.headers["Range"]
        if not re.fullmatch(r"bytes=(?:\d+-\d*|-\d+)", value):
            abort(416)
        headers["range"] = value
    client = requests.Session()
    client.trust_env = False  # Never add workstation .netrc credentials.
    upstream = None

    def close():
        if upstream is not None:
            upstream.close()
        client.close()

    try:
        for _ in range(6):
            upstream = client.get(
                url,
                headers=headers,
                stream=True,
                timeout=(5, 15),
                allow_redirects=False,
            )
            if not upstream.is_redirect:
                break
            target = urljoin(url, upstream.headers["Location"])
            upstream.close()
            if not http_url(target) or origin(target) != playback.origin:
                raise ValueError("Redirection vers une autre origine.")
            url = target
        if upstream.status_code not in (200, 206):
            abort(416 if upstream.status_code == 416 else 502)
        kind = (
            upstream.headers.get("Content-Type", "").partition(";")[0].strip().lower()
        )
        # Inspect just the signature, even on extensionless manifests.
        first = upstream.raw.read(10, decode_content=True)
        chunks = chain([first], upstream.iter_content(64 * 1024))
        if first.startswith((b"#EXTM3U", b"\xef\xbb\xbf#EXTM3U")):
            data = bytearray()
            for chunk in chunks:
                data.extend(chunk)
                if len(data) > MANIFEST_LIMIT:
                    raise ValueError("Manifeste trop volumineux.")
            body = playback.manifest(data, url)
            close()
            return Response(body, mimetype="application/vnd.apple.mpegurl")

        def stream():
            try:
                yield from chunks
            finally:
                close()

        content_type = (
            kind
            if kind.startswith(("video/", "audio/")) or kind == "text/vtt"
            else "application/octet-stream"
        )
        response = Response(
            stream(), status=upstream.status_code, content_type=content_type
        )
        for name in ("Content-Range", "Accept-Ranges", "Content-Length"):
            if name in upstream.headers and not upstream.headers.get(
                "Content-Encoding"
            ):
                response.headers[name] = upstream.headers[name]
        response.call_on_close(close)
        return response
    except (requests.RequestException, TransportError, OSError, ValueError):
        close()
        abort(502, description="Lecture via le relais impossible. Essayez avec VLC.")
    except BaseException:
        close()
        raise
