"""Browser playback metadata and optional, cached iptv-org logo lookup."""

import json
import logging
import re
import time
from pathlib import Path
from urllib.parse import urlsplit

import requests

from playlist_utils import stream_request
from validation_pipeline import atomic_text_file

LOGOS_URL = "https://iptv-org.github.io/api/logos.json"
logger = logging.getLogger(__name__)


def http_url(value):
    if not isinstance(value, str) or any(ord(c) < 33 for c in value):
        return ""
    try:
        parts = urlsplit(value)
        if (
            parts.scheme in ("http", "https")
            and parts.hostname
            and not parts.username
            and not parts.password
        ):
            return value
    except ValueError:
        pass
    return ""


def attribute(info, name):
    match = re.search(r"(?:^|\s)" + re.escape(name) + r'="([^"]*)"', info)
    return match.group(1) if match else ""


class LogoCatalog:
    """Single-job caller; 24h disk cache, stale fallback, 5min failure cooldown."""

    def __init__(self, directory):
        self.path = Path(directory) / "logos.json"
        self.retry_at = 0
        self.data = []
        self.updated = 0
        try:
            cached = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(cached.get("logos"), list):
                self.data = cached["logos"]
                self.updated = float(cached["updated"])
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            pass

    def load(self):
        now = time.time()
        if now - self.updated < 86400 or now < self.retry_at:
            return self.data
        self.retry_at = now + 300
        try:
            with requests.get(LOGOS_URL, timeout=(4, 8), stream=True) as response:
                response.raise_for_status()
                payload = bytearray()
                for chunk in response.iter_content(65536):
                    payload.extend(chunk)
                    if len(payload) > 20 * 1024 * 1024 or time.time() - now > 15:
                        raise ValueError("Logo catalog limit exceeded")
            data = json.loads(payload)
            if not isinstance(data, list) or not all(
                isinstance(item, dict) for item in data
            ):
                raise ValueError("Invalid logo catalog")
            self.data, self.updated = data, now
            with atomic_text_file(str(self.path)) as handle:
                json.dump({"updated": now, "logos": data}, handle)
        except (requests.RequestException, OSError, ValueError):
            logger.warning(
                "Catalogue des logos indisponible; conservation du cache existant."
            )
        return self.data

    def enrich(self, entries):
        missing = any(
            attribute(e["info"], "tvg-id")
            and not http_url(attribute(e["info"], "tvg-logo"))
            for e in entries
        )
        index = {}
        if missing:
            # Keep exact feed identities; never infer a logo from a similar name.
            for logo in self.load():
                if (
                    not isinstance(logo, dict)
                    or not logo.get("in_use")
                    or not http_url(logo.get("url"))
                ):
                    continue
                channel, feed = logo.get("channel"), logo.get("feed")
                if not isinstance(channel, str) or (
                    feed is not None and not isinstance(feed, str)
                ):
                    continue
                key = (channel, feed or "")
                tags = logo.get("tags") or []
                if not isinstance(tags, list):
                    tags = []
                rank = ("white" not in tags, logo.get("format") == "PNG")
                if key not in index or rank > index[key][0]:
                    index[key] = (rank, logo["url"])
        for entry in entries:
            channel_id = attribute(entry["info"], "tvg-id")
            logo = http_url(attribute(entry["info"], "tvg-logo"))
            channel, _, feed = channel_id.partition("@")
            if not logo:
                candidate = index.get((channel, feed)) or index.get((channel, ""))
                logo = candidate[1] if candidate else ""
                if logo and not any(c in logo for c in '"<>'):
                    entry["info"] = re.sub(r'\s+tvg-logo="[^"]*"', "", entry["info"])
                    # Insert before the comma outside quoted attributes.
                    fields = re.split(
                        r",(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)", entry["info"], maxsplit=1
                    )
                    entry["info"] = (
                        fields[0]
                        + f' tvg-logo="{logo}"'
                        + ("," + fields[1] if len(fields) > 1 else "")
                    )
            entry["channel_id"] = channel_id
            entry["logo"] = logo


def playback_metadata(entry):
    try:
        url, headers = stream_request(entry)
        url = http_url(url)
        needs_headers = bool(headers)
    except ValueError:
        url, needs_headers = "", True
    return {
        "channel_id": entry.get("channel_id", ""),
        "logo": entry.get("logo", ""),
        "playback_url": url,
        "needs_headers": needs_headers,
        "info": entry["info"],
        "directives": entry.get("directives", ""),
    }
