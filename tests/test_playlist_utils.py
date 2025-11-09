#!/usr/bin/env python3
"""
Comprehensive unit tests for playlist_utils module.

Tests URL validation, M3U parsing, stream validation, quality filtering,
and all other shared utility functions.
"""

import pytest
import hashlib
from unittest.mock import Mock, patch, MagicMock
import subprocess
import json
from typing import List, Dict, Any

# Import functions to test
from playlist_utils import (
    validate_url,
    download_playlist,
    parse_m3u,
    check_stream_with_curl,
    check_stream_with_ffprobe,
    extract_resolution_from_quality,
    filter_best_quality,
    write_playlist,
    check_tool_availability,
    analyze_failures,
    setup_logging,
    RESOLUTION_1080P,
    RESOLUTION_720P,
    RESOLUTION_480P,
)


class TestURLValidation:
    """Test URL validation function."""

    def test_valid_http_url(self):
        """Test validation of valid HTTP URLs."""
        assert validate_url("http://example.com/stream.m3u8") is True
        assert validate_url("http://192.168.1.1:8080/playlist.m3u") is True

    def test_valid_https_url(self):
        """Test validation of valid HTTPS URLs."""
        assert validate_url("https://example.com/stream.m3u8") is True
        assert validate_url("https://sub.example.com:8443/path/to/stream") is True

    def test_invalid_scheme(self):
        """Test rejection of invalid URL schemes."""
        assert validate_url("ftp://malicious.com") is False
        assert validate_url("file:///etc/passwd") is False
        assert validate_url("javascript:alert(1)") is False

    def test_dangerous_characters(self):
        """Test rejection of URLs with dangerous characters."""
        assert validate_url("http://test.com;rm -rf /") is False
        assert validate_url("http://test.com|whoami") is False
        assert validate_url("http://test.com&id") is False
        assert validate_url("http://test.com`id`") is False
        assert validate_url("http://test.com$(whoami)") is False
        assert validate_url("http://test.com\nmalicious") is False

    def test_empty_and_invalid_input(self):
        """Test handling of empty and invalid input."""
        assert validate_url("") is False
        assert validate_url(None) is False
        assert validate_url(123) is False

    def test_missing_netloc(self):
        """Test rejection of URLs without domain."""
        assert validate_url("http://") is False
        assert validate_url("https://") is False


class TestDownloadPlaylist:
    """Test playlist download function."""

    @patch('playlist_utils.requests.get')
    def test_successful_download(self, mock_get):
        """Test successful playlist download."""
        mock_response = Mock()
        mock_response.headers = {'Content-Type': 'audio/x-mpegurl'}
        mock_response.iter_content = lambda chunk_size, decode_unicode: ['#EXTM3U\n', '#EXTINF:-1,Test\nhttp://test']
        mock_get.return_value = mock_response

        result = download_playlist("http://example.com/playlist.m3u")
        assert result == "#EXTM3U\n#EXTINF:-1,Test\nhttp://test"
        mock_get.assert_called_once()

    @patch('playlist_utils.requests.get')
    def test_download_timeout(self, mock_get):
        """Test handling of download timeout."""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout()

        result = download_playlist("http://example.com/playlist.m3u")
        assert result is None

    @patch('playlist_utils.requests.get')
    def test_download_http_error(self, mock_get):
        """Test handling of HTTP errors."""
        import requests
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
        mock_get.return_value = mock_response

        result = download_playlist("http://example.com/playlist.m3u")
        assert result is None

    @patch('playlist_utils.validate_url')
    def test_download_invalid_url(self, mock_validate):
        """Test rejection of invalid URLs."""
        mock_validate.return_value = False

        result = download_playlist("invalid://url")
        assert result is None

    @patch('playlist_utils.requests.get')
    def test_download_size_limit(self, mock_get):
        """Test enforcement of size limits."""
        from playlist_utils import MAX_PLAYLIST_SIZE

        mock_response = Mock()
        mock_response.headers = {
            'Content-Type': 'text/plain',
            'Content-Length': str(MAX_PLAYLIST_SIZE + 1)
        }
        mock_get.return_value = mock_response

        # Function returns None on error instead of raising
        result = download_playlist("http://example.com/huge.m3u")
        assert result is None


class TestParseM3U:
    """Test M3U parsing function."""

    def test_parse_simple_m3u(self):
        """Test parsing simple M3U content."""
        m3u = "#EXTM3U\n#EXTINF:-1,Test Channel\nhttp://example.com/stream"
        entries = parse_m3u(m3u)

        assert len(entries) == 1
        assert entries[0]["name"] == "Test Channel"
        assert entries[0]["url"] == "http://example.com/stream"
        assert "#EXTINF" in entries[0]["info"]

    def test_parse_multiple_entries(self):
        """Test parsing multiple M3U entries."""
        m3u = """#EXTM3U
#EXTINF:-1,Channel 1
http://example.com/stream1
#EXTINF:-1,Channel 2
http://example.com/stream2
#EXTINF:-1,Channel 3
http://example.com/stream3"""
        entries = parse_m3u(m3u)

        assert len(entries) == 3
        assert entries[0]["name"] == "Channel 1"
        assert entries[1]["name"] == "Channel 2"
        assert entries[2]["name"] == "Channel 3"

    def test_parse_tvg_name_attribute(self):
        """Test extraction of channel name from tvg-name attribute."""
        m3u = '#EXTM3U\n#EXTINF:-1 tvg-name="TF1",TF1 HD\nhttp://test'
        entries = parse_m3u(m3u)

        assert len(entries) == 1
        assert entries[0]["name"] == "TF1"

    def test_parse_empty_playlist(self):
        """Test parsing empty playlist."""
        m3u = "#EXTM3U\n"
        entries = parse_m3u(m3u)

        assert len(entries) == 0

    def test_parse_skip_invalid_entries(self):
        """Test skipping invalid entries."""
        m3u = """#EXTM3U
#EXTINF:-1,Valid
http://example.com/stream
#EXTINF:-1,Invalid

#EXTINF:-1,Another Invalid
#Comment
#EXTINF:-1,Another Valid
http://example.com/stream2"""
        entries = parse_m3u(m3u)

        assert len(entries) == 2
        assert entries[0]["name"] == "Valid"
        assert entries[1]["name"] == "Another Valid"


class TestStreamValidation:
    """Test stream validation functions."""

    @patch('playlist_utils.validate_url')
    def test_curl_validation_invalid_url(self, mock_validate):
        """Test curl validation rejects invalid URLs."""
        mock_validate.return_value = False

        entry = {"name": "Test", "info": "#EXTINF:-1,Test", "url": "invalid://url"}
        result = check_stream_with_curl(entry)

        assert result["working"] is False
        assert "Invalid URL" in result["error"]

    @patch('playlist_utils.validate_url')
    @patch('playlist_utils.subprocess.run')
    def test_curl_validation_success(self, mock_run, mock_validate):
        """Test successful curl validation."""
        mock_validate.return_value = True
        mock_run.return_value = Mock(
            returncode=0,
            stdout="HTTP/1.1 200 OK\nContent-Type: video/mp4\n",
            stderr=""
        )

        entry = {"name": "Test", "info": "#EXTINF:-1,Test", "url": "http://example.com/1080p/stream"}
        result = check_stream_with_curl(entry, timeout=5)

        assert result["working"] is True
        assert result["quality"] == "1080p"
        assert result["width"] == RESOLUTION_1080P
        assert result["method"] == "curl"

    @patch('playlist_utils.validate_url')
    @patch('playlist_utils.subprocess.run')
    def test_curl_validation_timeout(self, mock_run, mock_validate):
        """Test curl validation timeout handling."""
        mock_validate.return_value = True
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=[], timeout=5)

        entry = {"name": "Test", "info": "#EXTINF:-1,Test", "url": "http://example.com/stream"}
        result = check_stream_with_curl(entry, timeout=5)

        assert result["working"] is False
        assert result["error"] == "Timeout"

    @patch('playlist_utils.validate_url')
    @patch('playlist_utils.subprocess.run')
    def test_ffprobe_validation_success(self, mock_run, mock_validate):
        """Test successful ffprobe validation."""
        mock_validate.return_value = True

        stream_info = {
            "streams": [{
                "codec_type": "video",
                "width": 1920,
                "height": 1080
            }]
        }
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps(stream_info),
            stderr=""
        )

        entry = {"name": "Test", "info": "#EXTINF:-1,Test", "url": "http://example.com/stream"}
        result = check_stream_with_ffprobe(entry, timeout=5)

        assert result["working"] is True
        assert result["quality"] == "1080p"
        assert result["width"] == 1920
        assert result["height"] == 1080
        assert result["method"] == "ffprobe"

    @patch('playlist_utils.validate_url')
    @patch('playlist_utils.subprocess.run')
    def test_ffprobe_validation_720p(self, mock_run, mock_validate):
        """Test ffprobe detection of 720p quality."""
        mock_validate.return_value = True

        stream_info = {
            "streams": [{
                "codec_type": "video",
                "width": 1280,
                "height": 720
            }]
        }
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps(stream_info),
            stderr=""
        )

        entry = {"name": "Test", "info": "#EXTINF:-1,Test", "url": "http://example.com/stream"}
        result = check_stream_with_ffprobe(entry, timeout=5)

        assert result["quality"] == "720p"


class TestExtractResolution:
    """Test resolution extraction from quality strings."""

    def test_extract_720p(self):
        """Test extraction of 720p resolution."""
        result = extract_resolution_from_quality("720p")
        assert result["width"] == 1280
        assert result["height"] == 720

    def test_extract_1080p(self):
        """Test extraction of 1080p resolution."""
        result = extract_resolution_from_quality("1080p")
        assert result["width"] == 1920
        assert result["height"] == 1080

    def test_extract_explicit_dimensions(self):
        """Test extraction of explicit dimensions."""
        result = extract_resolution_from_quality("1920x1080")
        assert result["width"] == 1920
        assert result["height"] == 1080

    def test_extract_unknown(self):
        """Test handling of unknown quality strings."""
        result = extract_resolution_from_quality("unknown")
        assert result["width"] == 0
        assert result["height"] == 0


class TestFilterBestQuality:
    """Test quality filtering function."""

    def test_filter_single_stream_per_channel(self):
        """Test filtering keeps one stream per channel."""
        streams = [
            {"name": "TF1", "url": "http://a", "width": 1920, "height": 1080, "working": True},
            {"name": "TF1", "url": "http://b", "width": 1280, "height": 720, "working": True},
            {"name": "M6", "url": "http://c", "width": 1920, "height": 1080, "working": True},
        ]

        result = filter_best_quality(streams, deduplicate=False)

        assert len(result) == 2
        # Should keep the 1080p stream for TF1
        tf1_stream = [s for s in result if s["name"] == "TF1"][0]
        assert tf1_stream["width"] == 1920

    def test_filter_skip_non_working(self):
        """Test filtering skips non-working streams."""
        streams = [
            {"name": "TF1", "url": "http://a", "width": 1920, "height": 1080, "working": False},
            {"name": "M6", "url": "http://b", "width": 1280, "height": 720, "working": True},
        ]

        result = filter_best_quality(streams)

        assert len(result) == 1
        assert result[0]["name"] == "M6"

    def test_filter_deduplication(self):
        """Test URL deduplication."""
        url = "http://example.com/stream"
        streams = [
            {"name": "TF1", "url": url, "width": 1920, "height": 1080, "working": True},
            {"name": "TF1 HD", "url": url, "width": 1920, "height": 1080, "working": True},
        ]

        result = filter_best_quality(streams, deduplicate=True)

        assert len(result) == 1

    def test_filter_no_deduplication(self):
        """Test without deduplication."""
        streams = [
            {"name": "TF1", "url": "http://a", "width": 1920, "height": 1080, "working": True},
            {"name": "TF1", "url": "http://b", "width": 1280, "height": 720, "working": True},
        ]

        result = filter_best_quality(streams, deduplicate=False)

        # Should still group by name and pick best
        assert len(result) == 1
        assert result[0]["width"] == 1920


class TestWritePlaylist:
    """Test playlist writing function."""

    @patch('builtins.open', create=True)
    def test_write_playlist_basic(self, mock_open):
        """Test basic playlist writing."""
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file

        entries = [
            {"name": "TF1", "info": "#EXTINF:-1,TF1", "url": "http://test", "quality": "1080p"},
        ]

        write_playlist(entries, "test.m3u")

        mock_open.assert_called_once_with("test.m3u", "w", encoding="utf-8")
        # Check that write was called
        assert mock_file.write.called

    @patch('builtins.open', create=True)
    def test_write_playlist_with_metadata(self, mock_open):
        """Test playlist writing includes metadata."""
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file

        entries = [
            {"name": "Test", "info": "#EXTINF:-1,Test", "url": "http://test", "quality": "720p"},
        ]

        write_playlist(entries, "test.m3u")

        # Check that metadata was written
        calls = [call[0][0] for call in mock_file.write.call_args_list]
        assert any("#EXTM3U" in call for call in calls)
        assert any("Playlist générée" in call for call in calls)


class TestToolAvailability:
    """Test tool availability checking."""

    @patch('playlist_utils.subprocess.run')
    def test_tool_available(self, mock_run):
        """Test detection of available tool."""
        mock_run.return_value = Mock(returncode=0)

        assert check_tool_availability("curl") is True
        mock_run.assert_called_once()

    @patch('playlist_utils.subprocess.run')
    def test_tool_not_available(self, mock_run):
        """Test detection of unavailable tool."""
        mock_run.side_effect = FileNotFoundError()

        assert check_tool_availability("nonexistent") is False

    @patch('playlist_utils.subprocess.run')
    def test_tool_timeout(self, mock_run):
        """Test handling of tool check timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=[], timeout=5)

        assert check_tool_availability("slow_tool") is False


class TestAnalyzeFailures:
    """Test failure analysis function."""

    def test_analyze_timeout_errors(self):
        """Test analysis of timeout errors."""
        failed = [
            {"error": "Timeout", "method": "curl"},
            {"error": "timeout occurred", "method": "ffprobe"},
        ]

        error_counts, method_counts = analyze_failures(failed)

        assert error_counts["Timeout"] == 2
        assert method_counts["curl"] == 1
        assert method_counts["ffprobe"] == 1

    def test_analyze_http_errors(self):
        """Test analysis of HTTP errors."""
        failed = [
            {"error": "404 Not Found", "method": "curl"},
            {"error": "403 Forbidden", "method": "curl"},
        ]

        error_counts, method_counts = analyze_failures(failed)

        assert error_counts["404/Not Found"] == 1
        assert error_counts["403/Forbidden"] == 1

    def test_analyze_invalid_url_errors(self):
        """Test analysis of invalid URL errors."""
        failed = [
            {"error": "Invalid URL", "method": "validation"},
        ]

        error_counts, method_counts = analyze_failures(failed)

        assert error_counts["Invalid URL"] == 1


class TestSetupLogging:
    """Test logging setup function."""

    def test_setup_logging_basic(self):
        """Test basic logging setup."""
        setup_logging(verbose=False)

        import logging
        logger = logging.getLogger("playlist_utils")
        assert logger.level <= logging.INFO

    def test_setup_logging_verbose(self):
        """Test verbose logging setup."""
        setup_logging(verbose=True)

        import logging
        logger = logging.getLogger("playlist_utils")
        assert logger.level <= logging.DEBUG


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_parse_m3u_malformed(self):
        """Test handling of malformed M3U content."""
        m3u = "Not a valid M3U file"
        entries = parse_m3u(m3u)

        # Should not crash, return empty list
        assert isinstance(entries, list)

    def test_filter_empty_list(self):
        """Test filtering empty stream list."""
        result = filter_best_quality([])

        assert result == []

    @patch('playlist_utils.subprocess.run')
    def test_ffprobe_json_decode_error(self, mock_run):
        """Test handling of invalid JSON from ffprobe."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Invalid JSON",
            stderr=""
        )

        entry = {"name": "Test", "info": "#EXTINF:-1,Test", "url": "http://example.com/stream"}
        result = check_stream_with_ffprobe(entry)

        # Should handle gracefully
        assert result["working"] is True
        assert result["quality"] == "unknown"
