"""Receiver discovery and on-demand LAN access to a single media session."""

import ipaddress
import mimetypes
import socket
import threading
import time
from urllib.parse import urlsplit

from flask import Flask, abort, request
from pychromecast import get_listed_chromecasts
from pychromecast.discovery import CastBrowser, SimpleCastListener
from werkzeug.serving import WSGIRequestHandler, make_server
from zeroconf import Zeroconf

from .media import http_url
from .relay import Playback, media_response


class MediaRequestHandler(WSGIRequestHandler):
    def log_request(self, code="-", size="-"):
        # Session URLs grant temporary media access.
        pass


class Television:
    def __init__(self):
        self.lock = threading.RLock()
        self.devices = {}
        self.servers = {}
        self.sessions = {}

    def discover(self):
        browser = CastBrowser(SimpleCastListener(), Zeroconf())
        browser.start_discovery()
        try:
            time.sleep(4)
            devices = dict(browser.devices)
            with self.lock:
                self.devices = {
                    str(key): info
                    for key, info in devices.items()
                    if info.cast_type not in ("audio", "group")
                }
                return sorted(
                    (
                        {"id": key, "name": info.friendly_name or str(key)}
                        for key, info in self.devices.items()
                    ),
                    key=lambda item: item["name"],
                )
        finally:
            browser.stop_discovery()

    def address(self, peer=None):
        # UDP connect chooses the interface without sending data.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect((peer or "192.0.2.1", 8009))
            ip = ipaddress.ip_address(sock.getsockname()[0])
        if ip.is_loopback or not ip.is_private:
            raise ValueError("Aucune interface IPv4 de réseau local disponible.")
        return str(ip)

    def share(self, row, peer=None):
        if not row["needs_headers"]:
            url = http_url(row["playback_url"])
            if not url or urlsplit(url).hostname in ("127.0.0.1", "::1", "localhost"):
                raise ValueError("Le récepteur doit pouvoir accéder à cette adresse.")
            return url
        ip = self.address(peer)
        playback = Playback(row)
        with self.lock:
            if ip not in self.servers:
                app = Flask("media_receiver", static_folder=None)
                app.add_url_rule(
                    "/media/<session>/<resource>",
                    "relay_media",
                    self.serve,
                    methods=["GET", "OPTIONS"],
                )
                server = make_server(
                    ip, 0, app, threaded=True, request_handler=MediaRequestHandler
                )
                self.servers[ip] = server
                threading.Thread(target=server.serve_forever, daemon=True).start()
            self.expire()
            if len(self.sessions) >= 32:
                oldest = min(self.sessions, key=lambda key: self.sessions[key][1])
                self.sessions.pop(oldest)
            self.sessions[playback.key] = (playback, time.monotonic())
            port = self.servers[ip].server_port
        return f"http://{ip}:{port}/media/{playback.key}/main"

    def expire(self):
        now = time.monotonic()
        for key, (_, used) in list(self.sessions.items()):
            if now - used > 900:
                del self.sessions[key]

    def serve(self, session, resource):
        with self.lock:
            self.expire()
            if session not in self.sessions:
                abort(404)
            playback, _ = self.sessions[session]
            self.sessions[session] = (playback, time.monotonic())
        if request.method == "OPTIONS":
            return (
                "",
                204,
                {
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Range",
                    "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
                },
            )
        response = media_response(playback, resource)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Expose-Headers"] = (
            "Content-Range, Accept-Ranges"
        )
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = "sandbox; default-src 'none'"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    def cast(self, row, device_id):
        with self.lock:
            info = self.devices.get(device_id)
        if not info:
            raise ValueError("Recherchez à nouveau le Chromecast.")
        url = self.share(row, info.host)
        mime = mimetypes.guess_type(urlsplit(row["playback_url"]).path)[0]
        if not mime or "mpegurl" in mime.lower():
            mime = "application/x-mpegURL"
        receivers, browser = get_listed_chromecasts(
            uuids=[info.uuid], discovery_timeout=5, tries=1, timeout=5
        )
        try:
            if not receivers:
                raise ValueError("Le Chromecast ne répond plus.")
            receiver = receivers[0]
            receiver.wait(timeout=6)
            media = receiver.media_controller
            media.play_media(
                url,
                mime,
                title=row["name"],
                stream_type="LIVE" if mime == "application/x-mpegURL" else "BUFFERED",
            )
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if (
                    media.status.content_id == url
                    and media.status.player_state == "PLAYING"
                ):
                    return
                time.sleep(0.25)
            raise ValueError("Le Chromecast n’a pas confirmé la lecture.")
        finally:
            browser.stop_discovery()
            for receiver in receivers:
                receiver.disconnect(timeout=3)

    def close(self):
        for server in self.servers.values():
            server.shutdown()
            server.server_close()
