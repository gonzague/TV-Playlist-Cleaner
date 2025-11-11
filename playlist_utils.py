#!/usr/bin/env python3
"""
Shared utilities for M3U playlist processing.

This module provides common functions for downloading, parsing, validating,
and processing M3U playlists.
"""

import re
import subprocess
import hashlib
import logging
import json
import shutil
import os
from typing import List, Dict, Optional, Tuple, Any
from collections import defaultdict
from urllib.parse import urlparse
import requests

# Configure module logger
logger = logging.getLogger(__name__)

# Constants
MAX_PLAYLIST_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_SCHEMES = ('http', 'https')
DANGEROUS_CHARS = [';', '&', '|', '`', '$', '(', ')', '\n', '\r']

# Quality thresholds
RESOLUTION_1080P = 1920
RESOLUTION_720P = 1280
RESOLUTION_480P = 854


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

        # Prevent command injection via special characters
        if any(char in url for char in DANGEROUS_CHARS):
            logger.warning(f"URL contains dangerous characters: {url}")
            return False

        # Must have netloc (domain)
        if not parsed.netloc:
            logger.warning(f"URL missing domain: {url}")
            return False

        return True

    except Exception as e:
        logger.error(f"URL validation error: {e}", exc_info=True)
        return False


def download_playlist(url: str, timeout: int = 30) -> Optional[str]:
    """
    Download playlist with safety checks.

    Args:
        url: Playlist URL to download
        timeout: Request timeout in seconds

    Returns:
        Playlist content or None on error

    Raises:
        ValueError: If playlist is too large or invalid content type
        requests.exceptions.RequestException: On network errors
    """
    if not validate_url(url):
        logger.error(f"Invalid URL rejected: {url}")
        return None

    try:
        logger.info(f"Downloading playlist from: {url}")
        response = requests.get(
            url,
            timeout=timeout,
            stream=True,
            headers={'User-Agent': 'TV-Playlist-Cleaner/1.0'}
        )
        response.raise_for_status()

        # Check content type
        content_type = response.headers.get('Content-Type', '')
        if content_type and 'audio/x-mpegurl' not in content_type and 'text/plain' not in content_type and 'application/vnd.apple.mpegurl' not in content_type:
            logger.warning(f"Unexpected content type: {content_type}")

        # Check size
        content_length = response.headers.get('Content-Length')
        if content_length and int(content_length) > MAX_PLAYLIST_SIZE:
            raise ValueError(f"Playlist too large: {content_length} bytes")

        # Download with size limit
        content = []
        size = 0
        for chunk in response.iter_content(chunk_size=8192, decode_unicode=True):
            if chunk:  # filter out keep-alive chunks
                size += len(chunk)
                if size > MAX_PLAYLIST_SIZE:
                    raise ValueError("Playlist exceeds size limit")
                content.append(chunk)

        result = ''.join(content)
        logger.info(f"Successfully downloaded {len(result)} bytes")
        return result

    except requests.exceptions.Timeout:
        logger.error(f"Timeout downloading playlist: {url}")
        return None
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error downloading playlist: {e}")
        return None
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error {e.response.status_code}: {url}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error downloading playlist", exc_info=True)
        return None


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
    lines = m3u_text.strip().splitlines()
    i = 0

    while i < len(lines):
        if lines[i].startswith("#EXTINF"):
            info = lines[i]
            i += 1
            if i < len(lines) and not lines[i].startswith("#"):
                url = lines[i].strip()

                # Skip invalid URLs
                if not url or url.startswith("#"):
                    i += 1
                    continue

                # Try to extract channel name from tvg-name attribute first, then from the end of the line
                match = re.search(r'tvg-name="([^"]+)"', info) or re.search(
                    r",(.+)$", info
                )
                name = match.group(1).strip() if match else "Unknown"
                entries.append({"name": name, "info": info, "url": url})
        i += 1

    logger.info(f"Parsed {len(entries)} entries from M3U")
    return entries


def check_stream_with_curl(
    entry: Dict[str, str],
    timeout: int = 15
) -> Dict[str, Any]:
    """
    Use curl to check if the stream works and get basic information.

    Args:
        entry: Stream entry with 'name', 'info', 'url'
        timeout: Timeout in seconds

    Returns:
        Dictionary with stream info including 'working', 'quality', 'width', 'height'
    """
    url = entry["url"]

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
            "method": "validation"
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
                "method": "validation"
            }
        
        # Use curl to check if the stream is accessible
        cmd = [
            curl_path,  # Use full path instead of just "curl"
            "-I",
            "--connect-timeout",
            str(timeout),
            "--max-time",
            str(timeout),
            "--silent",
            "--fail",
            url,
        ]

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout + 5
        )

        if result.returncode == 0:
            # Extract content type and other headers
            headers = result.stdout
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
                "method": "curl"
            }

        # If we get here, the stream failed
        error_msg = result.stderr.strip() if result.stderr else "Unknown error"
        logger.debug(f"Stream failed: {entry['name']} - {error_msg}")
        return {
            **entry,
            "working": False,
            "quality": "failed",
            "width": 0,
            "height": 0,
            "error": error_msg,
            "method": "curl"
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
            "method": "curl"
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
            "method": "curl"
        }


def check_stream_with_ffprobe(
    entry: Dict[str, str],
    timeout: int = 15
) -> Dict[str, Any]:
    """
    Check direct stream URLs using ffprobe.

    Args:
        entry: Stream entry with 'name', 'info', 'url'
        timeout: Timeout in seconds

    Returns:
        Dictionary with stream info including 'working', 'quality', 'width', 'height'
    """
    url = entry["url"]

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
            "method": "validation"
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
                "method": "validation"
            }
        
        # Use ffprobe to check if the stream is valid and get stream info
        cmd = [
            ffprobe_path,  # Use full path instead of just "ffprobe"
            "-v",
            "quiet",
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

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)

        if result.returncode == 0 and result.stdout.strip():
            try:
                # Parse JSON output to get stream information
                stream_info = json.loads(result.stdout)

                # Determine quality from video streams
                quality = "unknown"
                width = 0
                height = 0

                if "streams" in stream_info:
                    video_streams = [
                        s
                        for s in stream_info["streams"]
                        if s.get("codec_type") == "video"
                    ]
                    if video_streams:
                        video_stream = video_streams[0]
                        width = video_stream.get("width", 0)
                        height = video_stream.get("height", 0)

                        if width >= RESOLUTION_1080P and height >= 1080:
                            quality = "1080p"
                        elif width >= RESOLUTION_720P and height >= 720:
                            quality = "720p"
                        elif width >= RESOLUTION_480P and height >= 480:
                            quality = "480p"
                        elif width > 0 and height > 0:
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
            except json.JSONDecodeError:
                # If JSON parsing fails but command succeeded, stream is probably working
                logger.debug(f"Stream OK (ffprobe, no JSON): {entry['name']}")
                return {
                    **entry,
                    "working": True,
                    "quality": "unknown",
                    "width": 0,
                    "height": 0,
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
    entries: List[Dict[str, Any]],
    deduplicate: bool = True
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
                url_hash = hashlib.sha256(entry["url"].encode()).hexdigest()
                if url_hash not in seen_urls:
                    seen_urls.add(url_hash)
                    unique_entries.append(entry)
        logger.debug(f"After deduplication: {len(unique_entries)} unique entries")
    else:
        unique_entries = [e for e in entries if e.get("working")]

    # Group by name and select best quality
    grouped = defaultdict(list)
    for entry in unique_entries:
        grouped[entry["name"]].append(entry)

    best_streams = []
    for name, group in grouped.items():
        if group:
            # Sort by height (resolution) and select the best
            best = max(group, key=lambda e: (e.get("height", 0), e.get("width", 0)))
            best_streams.append(best)

    logger.info(f"Selected {len(best_streams)} best quality streams")
    return best_streams


def write_playlist(
    entries: List[Dict[str, Any]],
    output_file: str = "filtered.m3u"
) -> None:
    """
    Write the filtered playlist to an M3U file.

    Args:
        entries: List of stream entries to write
        output_file: Path to output file
    """
    from datetime import datetime

    logger.info(f"Writing {len(entries)} entries to {output_file}")

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write(
            f"# Playlist générée le {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}\n"
        )
        f.write(f"# Total: {len(entries)} flux valides\n")

        qualities = set(e.get('quality', 'unknown') for e in entries if e.get('quality') != 'unknown')
        if qualities:
            f.write(f"# Qualités détectées: {', '.join(sorted(qualities))}\n")
        f.write("\n")

        for entry in entries:
            quality_info = (
                f" ({entry.get('quality', 'unknown')})"
                if entry.get("quality") and entry.get("quality") != "unknown"
                else ""
            )
            f.write(f"{entry['info']}{quality_info}\n")
            f.write(f"{entry['url']}\n\n")

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


def analyze_failures(failed_streams: List[Dict[str, Any]]) -> Tuple[Dict[str, int], Dict[str, int]]:
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
    console_formatter = logging.Formatter('%(message)s')
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
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
    logging.basicConfig(
        level=level,
        handlers=handlers
    )

    logger.info("Logging configured")
