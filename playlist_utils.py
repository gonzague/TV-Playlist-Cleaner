#!/usr/bin/env python3
"""
Shared utilities for M3U playlist processing.

This module provides common functions for downloading, parsing, validating,
and processing M3U playlists.
"""

import re
import subprocess  # nosec B404
import hashlib
import logging
import json
import shutil
import os
import ipaddress
import tempfile
import time
from typing import List, Dict, Optional, Tuple, Any
from collections import defaultdict
from concurrent.futures import CancelledError
from urllib.parse import urlparse, parse_qsl
import requests

# Configure module logger
logger = logging.getLogger(__name__)

# Constants
MAX_PLAYLIST_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_SCHEMES = ("http", "https")
INVALID_URL_CHARS = set(' \t\n\r\0<>"{}|\\^`')

# Quality thresholds
RESOLUTION_1080P = 1920
RESOLUTION_720P = 1280
RESOLUTION_480P = 854


def _is_valid_hostname(hostname: Optional[str]) -> bool:
    """Validate DNS names and IP literals accepted in playlist URLs."""
    if not hostname:
        return False

    if hostname == "localhost":
        return True

    try:
        ipaddress.ip_address(hostname)
        return True
    except ValueError:
        pass

    try:
        ascii_hostname = hostname.encode("idna").decode("ascii")
    except UnicodeError:
        return False

    if len(ascii_hostname) > 253:
        return False

    labels = ascii_hostname.rstrip(".").split(".")
    label_pattern = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
    return all(label_pattern.match(label) for label in labels)


def validate_url(url: str) -> bool:
    """
    Validate URL is safe for subprocess calls.

    Args:
        url: URL to validate

    Returns:
        True if URL is safe, False otherwise

    Example:
        >>> validate_url("http://example.com/stream.m3u8")
        True
        >>> validate_url("ftp://malicious.com")
        False
    """
    if not url or not isinstance(url, str):
        logger.warning("Invalid URL: empty or not a string")
        return False

    try:
        parsed = urlparse(url)

        # Only allow http/https
        if parsed.scheme not in ALLOWED_SCHEMES:
            logger.warning(f"Invalid URL scheme: {parsed.scheme}")
            return False

        # Reject raw characters that are not valid in URLs. Query separators such
        # as "&" remain allowed because URLs are passed to subprocess as argv.
        if any(char in INVALID_URL_CHARS for char in url):
            logger.warning(f"URL contains invalid characters: {url}")
            return False

        # Must have a valid network location.
        if not parsed.netloc or not _is_valid_hostname(parsed.hostname):
            logger.warning(f"URL missing domain: {url}")
            return False

        try:
            parsed.port
        except ValueError:
            logger.warning(f"URL contains invalid port: {url}")
            return False

        return True

    except Exception as e:
        logger.error(f"URL validation error: {e}", exc_info=True)
        return False


def download_playlist(
    url: str,
    timeout: int = 30,
    retries: int = 0,
    retry_delay: float = 0.5,
    cancel_event=None,
) -> Optional[str]:
    """Download a playlist, retrying only temporary HTTP/network failures."""
    for attempt in range(retries + 1):
        if cancel_event is not None and cancel_event.is_set():
            raise CancelledError()
        result, retryable = _download_playlist_once(url, timeout, cancel_event)
        if result is not None or not retryable or attempt == retries:
            return result
        delay = min(retry_delay * (2**attempt), 30)
        if cancel_event is not None:
            if cancel_event.wait(delay):
                raise CancelledError()
        else:
            time.sleep(delay)
    return None


def _download_playlist_once(
    url: str, timeout: int, cancel_event=None
) -> Tuple[Optional[str], bool]:
    """
    Download playlist with safety checks.

    Args:
        url: Playlist URL to download
        timeout: Request timeout in seconds

    Returns:
        Playlist content or None on error

    Responses are always closed, including on HTTP errors and oversized input.
    """
    if not validate_url(url):
        logger.error(f"Invalid URL rejected: {url}")
        return None, False

    response = None
    try:
        logger.info(f"Downloading playlist from: {url}")
        response = requests.get(
            url,
            timeout=timeout,
            stream=True,
            headers={"User-Agent": "TV-Playlist-Cleaner/1.0"},
        )
        response.raise_for_status()

        # Check content type
        content_type = response.headers.get("Content-Type", "")
        if (
            content_type
            and "audio/x-mpegurl" not in content_type
            and "text/plain" not in content_type
            and "application/vnd.apple.mpegurl" not in content_type
        ):
            logger.warning(f"Unexpected content type: {content_type}")

        # Check size
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > MAX_PLAYLIST_SIZE:
            raise ValueError(f"Playlist too large: {content_length} bytes")

        # Download with size limit
        content = bytearray()
        for chunk in response.iter_content(chunk_size=8192):
            if cancel_event is not None and cancel_event.is_set():
                raise CancelledError()
            if chunk:  # filter out keep-alive chunks
                if isinstance(chunk, str):
                    chunk = chunk.encode("utf-8")
                if len(content) + len(chunk) > MAX_PLAYLIST_SIZE:
                    raise ValueError("Playlist exceeds size limit")
                content.extend(chunk)

        # Decode to string
        result = bytes(content).decode("utf-8-sig", errors="replace")
        logger.info(f"Successfully downloaded {len(result)} bytes")
        return result, False

    except CancelledError:
        raise
    except requests.exceptions.Timeout:
        logger.error(f"Timeout downloading playlist: {url}")
        return None, True
    except requests.exceptions.SSLError:
        logger.error("SSL certificate error downloading playlist")
        return None, False
    except requests.exceptions.ChunkedEncodingError:
        logger.error("Interrupted playlist download")
        return None, True
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error downloading playlist: {e}")
        return None, True
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "unknown"
        logger.error(f"HTTP error {status}: {url}")
        return None, status in (408, 425, 429, 500, 502, 503, 504)
    except Exception as e:
        logger.error(f"Unexpected error downloading playlist", exc_info=True)
        return None, False
    finally:
        if response is not None:
            response.close()


def parse_m3u(m3u_text: str) -> List[Dict[str, str]]:
    """
    Parse M3U content and extract stream information.

    Args:
        m3u_text: Raw M3U playlist content as string

    Returns:
        List of dictionaries containing:
            - name: Channel name
            - info: Full EXTINF line
            - url: Stream URL

    Example:
        >>> m3u = "#EXTM3U\\n#EXTINF:-1,Channel\\nhttp://url"
        >>> entries = parse_m3u(m3u)
        >>> len(entries)
        1
    """
    logger.debug("Parsing M3U content")
    entries = []
    info = None
    directives = []
    for raw_line in m3u_text.lstrip("\ufeff").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#EXTINF:"):
            # A new entry discards any incomplete preceding entry.
            info = line
            directives = []
        elif info is not None and line.startswith("#"):
            directives.append(line)
        elif info is not None:
            match = re.search(r'\btvg-name="([^"]+)"', info)
            # Only commas outside quoted attributes delimit the display name.
            fields = re.split(r',(?=(?:[^"]*"[^"]*")*[^"]*$)', info, maxsplit=1)
            name = match.group(1) if match else fields[1] if len(fields) > 1 else ""
            entry = {"name": name.strip() or "Unknown", "info": info, "url": line}
            if directives:
                entry["directives"] = "\n".join(directives)
            entries.append(entry)
            info = None
            directives = []

    logger.info(f"Parsed {len(entries)} entries from M3U")
    return entries


def stream_request(entry: Dict[str, str]) -> Tuple[str, Dict[str, str]]:
    """Extract HTTP options without modifying the playback URL or directives.

    VLC literal values and Kodi URL-encoded header pairs are supported. Different
    manifest/segment values cannot be represented by a single ffprobe request.
    """
    url, separator, suffix = entry["url"].partition("|")
    headers = {}
    kodi = {}
    vlc_names = {
        "http-user-agent": "user-agent",
        "http-referrer": "referer",
        "http-referer": "referer",
        "http-origin": "origin",
        "http-cookie": "cookie",
    }

    def put(target, name, value):
        name = name.strip().lower()
        if not re.fullmatch(r"[!#$%&'*+.^_`|~0-9a-z-]+", name):
            raise ValueError("Invalid HTTP header name")
        if any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("Invalid control character in HTTP header")
        if name in {"host", "content-length", "transfer-encoding", "connection"}:
            raise ValueError("Unsupported transport HTTP header")
        target[name] = value

    for line in entry.get("directives", "").splitlines():
        if line.startswith("#EXTVLCOPT:"):
            name, _, value = line[len("#EXTVLCOPT:") :].partition("=")
            if name.lower() in vlc_names:
                put(headers, vlc_names[name.lower()], value)
        elif line.startswith("#KODIPROP:inputstream.adaptive."):
            key, _, value = line[len("#KODIPROP:inputstream.adaptive.") :].partition(
                "="
            )
            if key in ("common_headers", "stream_headers", "manifest_headers"):
                parsed = {}
                for name, content in parse_qsl(
                    value, keep_blank_values=True, strict_parsing=True
                ):
                    put(parsed, name, content)
                kodi[key] = parsed
    stream = kodi.get("stream_headers", {})
    manifest = kodi.get("manifest_headers", {})
    if any(stream[name] != manifest[name] for name in stream.keys() & manifest.keys()):
        raise ValueError("Distinct Kodi manifest/stream headers are not supported")
    for key in ("common_headers", "stream_headers", "manifest_headers"):
        headers.update(kodi.get(key, {}))
    if separator:
        if not suffix:
            raise ValueError("Invalid empty Kodi URL headers")
        try:
            pairs = parse_qsl(suffix, keep_blank_values=True, strict_parsing=True)
        except ValueError as exc:
            raise ValueError("Invalid URL header suffix") from exc
        for name, value in pairs:
            put(headers, name, value)
    return url, headers


def request_identity(entry: Dict[str, str]) -> str:
    """Identity includes effective headers: different credentials are different probes."""
    try:
        url, headers = stream_request(entry)
        value = [url, headers]
    except ValueError:
        value = [entry["url"], entry.get("directives", "")]
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _request_error(entry, error):
    return {
        **entry,
        "working": False,
        "quality": "failed",
        "width": 0,
        "height": 0,
        "error": str(error),
        "method": "validation",
        "retryable": False,
    }


def check_stream_with_curl(entry: Dict[str, str], timeout: int = 15) -> Dict[str, Any]:
    """
    Use curl to check if the stream works and get basic information.

    Args:
        entry: Stream entry with 'name', 'info', 'url'
        timeout: Timeout in seconds

    Returns:
        Dictionary with stream info including 'working', 'quality', 'width', 'height'
    """
    try:
        url, request_headers = stream_request(entry)
    except ValueError as exc:
        return _request_error(entry, exc)

    # Validate URL before passing to subprocess
    if not validate_url(url):
        logger.warning(f"Invalid URL for {entry['name']}: {url}")
        return {
            **entry,
            "working": False,
            "quality": "failed",
            "width": 0,
            "height": 0,
            "error": "Invalid URL",
            "method": "validation",
        }

    try:
        # Get the full path to curl
        curl_path = get_tool_path("curl")
        if not curl_path:
            logger.warning(f"curl not found for {entry['name']}")
            return {
                **entry,
                "working": False,
                "quality": "failed",
                "width": 0,
                "height": 0,
                "error": "curl not found",
                "method": "validation",
            }

        # Use curl to check if the stream is accessible
        cmd = [
            curl_path,  # Use full path instead of just "curl"
            "--disable",
            "--globoff",
            "-I",
            "--location",
            "--max-redirs",
            "5",
            "--proto",
            "=http,https",
            "--proto-redir",
            "=http,https",
            "--connect-timeout",
            str(timeout),
            "--max-time",
            str(timeout),
            "--silent",
            "--show-error",
            "--fail",
            url,
        ]

        for name, value in request_headers.items():
            cmd[-1:-1] = ["--header", f"{name}: {value}"]
        result = subprocess.run(  # nosec B603
            cmd, capture_output=True, text=True, timeout=timeout + 5
        )

        statuses = re.findall(r"^HTTP/\S+\s+(\d{3})", result.stdout, re.MULTILINE)
        status = int(statuses[-1]) if statuses else 0
        if result.returncode == 0 and 200 <= status < 300:
            # Extract content type and other headers
            headers = re.split(
                r"^HTTP/\S+\s+\d{3}.*$", result.stdout, flags=re.MULTILINE
            )[-1]
            content_type = ""
            if "content-type:" in headers.lower():
                content_type_match = re.search(
                    r"content-type:\s*([^\r\n]+)", headers, re.IGNORECASE
                )
                if content_type_match:
                    content_type = content_type_match.group(1).strip()

            # Determine quality based on URL patterns or content type
            quality = "unknown"
            width = 0
            height = 0

            # Try to extract quality from URL patterns
            if "1080" in url or "1920" in url:
                quality = "1080p"
                width = RESOLUTION_1080P
                height = 1080
            elif "720" in url or "1280" in url:
                quality = "720p"
                width = RESOLUTION_720P
                height = 720
            elif "480" in url:
                quality = "480p"
                width = RESOLUTION_480P
                height = 480

            logger.debug(f"Stream OK: {entry['name']} - {quality}")
            return {
                **entry,
                "working": True,
                "quality": quality,
                "width": width,
                "height": height,
                "content_type": content_type,
                "method": "curl",
            }

        # If we get here, the stream failed
        error_msg = result.stderr.strip() or f"HTTP Error {status or 'unknown'}"
        logger.debug(f"Stream failed: {entry['name']} - {error_msg}")
        return {
            **entry,
            "working": False,
            "quality": "failed",
            "width": 0,
            "height": 0,
            "error": error_msg,
            "method": "curl",
            "http_status": status,
            "retryable": status in (408, 425, 429, 500, 502, 503, 504)
            or result.returncode in (5, 6, 7, 18, 28, 52, 55, 56),
        }

    except subprocess.TimeoutExpired:
        logger.debug(f"Stream timeout: {entry['name']}")
        return {
            **entry,
            "working": False,
            "quality": "timeout",
            "width": 0,
            "height": 0,
            "error": "Timeout",
            "method": "curl",
            "retryable": True,
        }
    except Exception as e:
        logger.error(f"Error checking stream {entry['name']}", exc_info=True)
        return {
            **entry,
            "working": False,
            "quality": f"error: {str(e)}",
            "width": 0,
            "height": 0,
            "error": str(e),
            "method": "curl",
        }


def check_stream_with_ffprobe(
    entry: Dict[str, str], timeout: int = 15
) -> Dict[str, Any]:
    """
    Check direct stream URLs using ffprobe.

    Args:
        entry: Stream entry with 'name', 'info', 'url'
        timeout: Timeout in seconds

    Returns:
        Dictionary with stream info including 'working', 'quality', 'width', 'height'
    """
    try:
        url, request_headers = stream_request(entry)
    except ValueError as exc:
        return _request_error(entry, exc)

    # Validate URL before passing to subprocess
    if not validate_url(url):
        logger.warning(f"Invalid URL for {entry['name']}: {url}")
        return {
            **entry,
            "working": False,
            "quality": "failed",
            "width": 0,
            "height": 0,
            "error": "Invalid URL",
            "method": "validation",
        }

    try:
        # Get the full path to ffprobe
        ffprobe_path = get_tool_path("ffprobe")
        if not ffprobe_path:
            logger.warning(f"ffprobe not found for {entry['name']}")
            return {
                **entry,
                "working": False,
                "quality": "failed",
                "width": 0,
                "height": 0,
                "error": "ffprobe not found",
                "method": "validation",
            }

        # Use ffprobe to check if the stream is valid and get stream info
        cmd = [
            ffprobe_path,  # Use full path instead of just "ffprobe"
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            "-allowed_extensions",
            "ALL",
            "-user_agent",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15",
            "-timeout",
            str(timeout * 1000000),  # Convert to microseconds
            url,
        ]

        if request_headers:
            header_text = "".join(
                f"{name}: {value}\r\n" for name, value in request_headers.items()
            )
            cmd[-1:-1] = ["-headers", header_text]
        result = subprocess.run(  # nosec B603
            cmd, capture_output=True, text=True, timeout=timeout + 5
        )

        if result.returncode == 0 and result.stdout.strip():
            try:
                # Parse JSON output to get stream information
                stream_info = json.loads(result.stdout)
                if not isinstance(stream_info, dict):
                    raise ValueError("Invalid ffprobe response")
                streams = stream_info.get("streams", [])
                if not isinstance(streams, list) or not any(
                    isinstance(s, dict) and s.get("codec_type") in ("video", "audio")
                    for s in streams
                ):
                    raise ValueError("No playable streams found")

                # Determine quality from video streams
                quality = "unknown"
                width = 0
                height = 0

                if streams:
                    video_streams = [
                        s
                        for s in stream_info["streams"]
                        if isinstance(s, dict) and s.get("codec_type") == "video"
                    ]
                    if video_streams:
                        video_stream = max(
                            video_streams,
                            key=lambda s: (s.get("height") or 0, s.get("width") or 0),
                        )
                        width = video_stream.get("width") or 0
                        height = video_stream.get("height") or 0
                        if width > 0 and height > 0:
                            quality = f"{height}p"

                logger.debug(f"Stream OK (ffprobe): {entry['name']} - {quality}")
                return {
                    **entry,
                    "working": True,
                    "quality": quality,
                    "width": width,
                    "height": height,
                    "method": "ffprobe",
                }
            except ValueError as exc:
                logger.debug(f"Invalid ffprobe output for {entry['name']}: {exc}")
                return {
                    **entry,
                    "working": False,
                    "quality": "failed",
                    "width": 0,
                    "height": 0,
                    "error": str(exc),
                    "method": "ffprobe",
                }
        else:
            error_msg = result.stderr.strip() or "ffprobe failed"
            logger.debug(f"Stream failed (ffprobe): {entry['name']} - {error_msg}")
            return {
                **entry,
                "working": False,
                "quality": "failed",
                "width": 0,
                "height": 0,
                "error": error_msg,
                "method": "ffprobe",
            }

    except subprocess.TimeoutExpired:
        logger.debug(f"Stream timeout (ffprobe): {entry['name']}")
        return {
            **entry,
            "working": False,
            "quality": "failed",
            "width": 0,
            "height": 0,
            "error": "Timeout",
            "method": "ffprobe",
            "retryable": True,
        }
    except Exception as e:
        logger.error(f"Error checking stream (ffprobe) {entry['name']}", exc_info=True)
        return {
            **entry,
            "working": False,
            "quality": "failed",
            "width": 0,
            "height": 0,
            "error": str(e),
            "method": "ffprobe",
        }


def extract_resolution_from_quality(quality_str: str) -> Dict[str, int]:
    """
    Extract width and height from quality string.

    Args:
        quality_str: Quality string like "720p" or "1920x1080"

    Returns:
        Dictionary with 'width' and 'height' keys

    Example:
        >>> extract_resolution_from_quality("720p")
        {'width': 1280, 'height': 720}
    """
    # Common quality patterns: 720p, 1080p, 480p, etc.
    resolution_pattern = r"(\d+)p"
    match = re.search(resolution_pattern, quality_str)

    if match:
        height = int(match.group(1))
        # Estimate width based on common aspect ratios (16:9)
        width = int(height * 16 / 9)
        return {"width": width, "height": height}

    # Try to extract explicit dimensions like "1920x1080"
    dimension_pattern = r"(\d+)x(\d+)"
    match = re.search(dimension_pattern, quality_str)

    if match:
        width = int(match.group(1))
        height = int(match.group(2))
        return {"width": width, "height": height}

    return {"width": 0, "height": 0}


def filter_best_quality(
    entries: List[Dict[str, Any]], deduplicate: bool = True
) -> List[Dict[str, Any]]:
    """
    Group streams by name and select the best quality for each.

    This function groups streams by channel name (normalized) and selects
    the stream with the highest resolution for each channel. Optionally
    deduplicates streams based on URL hash.

    Args:
        entries: List of stream dictionaries containing 'name', 'url',
                 'quality', and optionally 'resolution' keys.
        deduplicate: If True, removes streams with duplicate URLs.

    Returns:
        Filtered list of streams with best quality per channel.

    Example:
        >>> streams = [
        ...     {"name": "TF1", "url": "http://a", "width": 1920, "height": 1080, "working": True},
        ...     {"name": "TF1", "url": "http://b", "width": 1280, "height": 720, "working": True}
        ... ]
        >>> result = filter_best_quality(streams)
        >>> len(result)
        1
        >>> result[0]["width"]
        1920
    """
    logger.debug(f"Filtering best quality from {len(entries)} entries")

    # First deduplicate by URL if requested
    if deduplicate:
        seen_urls = set()
        unique_entries = []
        for entry in entries:
            if entry.get("working"):
                url_hash = request_identity(entry)
                if url_hash not in seen_urls:
                    seen_urls.add(url_hash)
                    unique_entries.append(entry)
        logger.debug(f"After deduplication: {len(unique_entries)} unique entries")
    else:
        unique_entries = [e for e in entries if e.get("working")]

    # Group by name and select best quality
    grouped = defaultdict(list)
    for entry in unique_entries:
        grouped[entry.get("normalized_name") or entry["name"]].append(entry)

    best_streams = []
    for name, group in grouped.items():
        if group:
            # Sort by height (resolution) and select the best
            best = max(
                group,
                key=lambda e: (e.get("height", 0), e.get("width", 0), e["url"]),
            )
            best_streams.append(best)

    logger.info(f"Selected {len(best_streams)} best quality streams")
    return sorted(best_streams, key=lambda e: (e["name"].casefold(), e["url"]))


def write_playlist(
    entries: List[Dict[str, Any]], output_file: str = "filtered.m3u"
) -> None:
    """
    Write the filtered playlist to an M3U file.

    Args:
        entries: List of stream entries to write
        output_file: Path to output file
    """
    from datetime import datetime

    logger.info(f"Writing {len(entries)} entries to {output_file}")

    destination = os.path.realpath(output_file)
    temporary_path = None
    try:
        # Replace only after a complete write, on the same filesystem.
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=os.path.dirname(destination),
            prefix=".playlist-",
            suffix=".tmp",
            delete=False,
        ) as f:
            temporary_path = f.name
            f.write("#EXTM3U\n")
            f.write(
                f"# Playlist générée le {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}\n"
            )
            f.write(f"# Total: {len(entries)} flux valides\n")
            qualities = {e.get("quality") for e in entries} - {None, "", "unknown"}
            if qualities:
                f.write(f"# Qualités détectées: {', '.join(sorted(qualities))}\n")
            f.write("\n")
            for entry in entries:
                # Keep original channel labels and player directives unchanged.
                f.write(f"{entry['info']}\n")
                if entry.get("directives"):
                    f.write(f"{entry['directives']}\n")
                f.write(f"{entry['url']}\n\n")
            f.flush()
            os.fsync(f.fileno())
        if os.path.exists(destination):
            os.chmod(temporary_path, os.stat(destination).st_mode & 0o777)
        os.replace(temporary_path, destination)
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.unlink(temporary_path)

    logger.info(f"Playlist written successfully to {output_file}")


def get_tool_path(tool_name: str) -> Optional[str]:
    """
    Get the full path to a tool executable.

    Args:
        tool_name: Name of the tool to find (e.g., 'curl', 'ffprobe')

    Returns:
        Full path to the tool, or None if not found
    """
    # First try to find the tool using shutil.which()
    # This searches the PATH and returns the full path if found
    tool_path = shutil.which(tool_name)

    if tool_path:
        logger.debug(f"Found {tool_name} at: {tool_path}")
        return tool_path

    # If not found in PATH, try common locations (especially for Homebrew on macOS)
    common_paths = [
        f"/usr/local/bin/{tool_name}",
        f"/opt/homebrew/bin/{tool_name}",
        f"/usr/bin/{tool_name}",
    ]

    for path in common_paths:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            logger.debug(f"Found {tool_name} at: {path}")
            return path

    logger.debug(f"{tool_name} not found in PATH or common locations")
    return None


def check_tool_availability(tool_name: str) -> bool:
    """
    Check if a tool is available on the system.

    Args:
        tool_name: Name of the tool to check (e.g., 'curl', 'ffprobe')

    Returns:
        True if tool is available, False otherwise
    """
    return get_tool_path(tool_name) is not None


def analyze_failures(
    failed_streams: List[Dict[str, Any]],
) -> Tuple[Dict[str, int], Dict[str, int]]:
    """
    Analyze why streams are failing and provide insights.

    Args:
        failed_streams: List of failed stream entries

    Returns:
        Tuple of (error_counts, method_counts) dictionaries
    """
    error_counts = defaultdict(int)
    method_counts = defaultdict(int)

    for stream in failed_streams:
        error = stream.get("error", "Unknown error")
        method = stream.get("method", "unknown")
        method_counts[method] += 1

        # Extract the main error type
        if "Invalid URL" in error:
            error_counts["Invalid URL"] += 1
        elif "No plugin can handle URL" in error:
            error_counts["No plugin can handle URL"] += 1
        elif "No playable streams found" in error:
            error_counts["No playable streams found"] += 1
        elif "timeout" in error.lower():
            error_counts["Timeout"] += 1
        elif "404" in error or "not found" in error.lower():
            error_counts["404/Not Found"] += 1
        elif "403" in error or "forbidden" in error.lower():
            error_counts["403/Forbidden"] += 1
        elif "ssl" in error.lower() or "certificate" in error.lower():
            error_counts["SSL/Certificate Error"] += 1
        elif "ffprobe" in error.lower():
            error_counts["FFprobe Error"] += 1
        elif "HTTP Error" in error:
            error_counts["HTTP Error"] += 1
        else:
            error_counts["Other"] += 1

    return dict(error_counts), dict(method_counts)


def setup_logging(verbose: bool = False, log_file: Optional[str] = None) -> None:
    """
    Configure logging for the application.

    Args:
        verbose: If True, set log level to DEBUG
        log_file: Optional path to log file
    """
    level = logging.DEBUG if verbose else logging.INFO

    # Create formatters
    console_formatter = logging.Formatter("%(message)s")
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Console handler (always)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(console_formatter)

    handlers = [console_handler]

    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)  # Always DEBUG for files
        file_handler.setFormatter(file_formatter)
        handlers.append(file_handler)

    # Configure root logger
    logging.basicConfig(level=level, handlers=handlers)

    logger.info("Logging configured")
