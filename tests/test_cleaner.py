"""
Tests for the cleaner module
"""

import pytest
import tempfile
import os
import sys
import subprocess
from unittest.mock import patch, MagicMock

# Ajouter le répertoire parent au path pour importer les modules
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)  # noqa: E402

from cleaner import (  # noqa: E402
    download_playlist,
    parse_m3u,
    check_stream_with_curl,
    extract_resolution_from_quality,
    filter_best_quality,
    write_playlist,
    check_curl_availability,
    analyze_failures,
)


class TestCleaner:
    """Test class for cleaner module"""

    def test_download_playlist_success(self):
        """Test successful playlist download"""
        with patch("cleaner.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.text = (
                "#EXTM3U\n#EXTINF:-1,Test Channel\nhttp://example.com/stream"
            )
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            result = download_playlist("http://example.com/playlist.m3u")
            assert "#EXTM3U" in result
            assert "Test Channel" in result

    def test_download_playlist_failure(self):
        """Test playlist download failure"""
        with patch("cleaner.requests.get") as mock_get:
            mock_get.side_effect = Exception("Network error")

            with pytest.raises(Exception):
                download_playlist("http://example.com/playlist.m3u")

    def test_parse_m3u_valid(self):
        """Test parsing valid M3U content"""
        m3u_content = """#EXTM3U
#EXTINF:-1 tvg-name="TF1",TF1
http://example.com/tf1.m3u8
#EXTINF:-1 tvg-name="France 2",France 2
http://example.com/france2.m3u8"""

        entries = parse_m3u(m3u_content)
        assert len(entries) == 2
        assert entries[0]["name"] == "TF1"
        assert entries[0]["url"] == "http://example.com/tf1.m3u8"
        assert entries[1]["name"] == "France 2"
        assert entries[1]["url"] == "http://example.com/france2.m3u8"

    def test_parse_m3u_empty(self):
        """Test parsing empty M3U content"""
        entries = parse_m3u("")
        assert len(entries) == 0

    def test_parse_m3u_invalid(self):
        """Test parsing invalid M3U content"""
        entries = parse_m3u("Invalid content without #EXTINF")
        assert len(entries) == 0

    def test_extract_resolution_from_quality_1080p(self):
        """Test extracting resolution from 1080p quality"""
        result = extract_resolution_from_quality("1080p")
        assert result["width"] == 1920
        assert result["height"] == 1080

    def test_extract_resolution_from_quality_720p(self):
        """Test extracting resolution from 720p quality"""
        result = extract_resolution_from_quality("720p")
        assert result["width"] == 1280
        assert result["height"] == 720

    def test_extract_resolution_from_quality_explicit(self):
        """Test extracting resolution from explicit dimensions"""
        result = extract_resolution_from_quality("1920x1080")
        assert result["width"] == 1920
        assert result["height"] == 1080

    def test_extract_resolution_from_quality_unknown(self):
        """Test extracting resolution from unknown quality"""
        result = extract_resolution_from_quality("unknown")
        assert result["width"] == 0
        assert result["height"] == 0

    def test_filter_best_quality(self):
        """Test filtering best quality streams"""
        entries = [
            {
                "name": "TF1",
                "working": True,
                "height": 720,
                "width": 1280,
                "quality": "720p",
            },
            {
                "name": "TF1",
                "working": True,
                "height": 1080,
                "width": 1920,
                "quality": "1080p",
            },
            {
                "name": "France 2",
                "working": True,
                "height": 480,
                "width": 854,
                "quality": "480p",
            },
            {
                "name": "France 2",
                "working": False,
                "height": 0,
                "width": 0,
                "quality": "failed",
            },
        ]

        result = filter_best_quality(entries)
        assert len(result) == 2

        # TF1 should have the 1080p version
        tf1_entry = next(e for e in result if e["name"] == "TF1")
        assert tf1_entry["height"] == 1080
        assert tf1_entry["quality"] == "1080p"

        # France 2 should have the 480p version (only working one)
        france2_entry = next(e for e in result if e["name"] == "France 2")
        assert france2_entry["height"] == 480
        assert france2_entry["quality"] == "480p"

    def test_write_playlist(self):
        """Test writing playlist to file"""
        entries = [
            {
                "name": "TF1",
                "info": '#EXTINF:-1 tvg-name="TF1",TF1',
                "url": "http://example.com/tf1.m3u8",
            },
            {
                "name": "France 2",
                "info": '#EXTINF:-1 tvg-name="France 2",France 2',
                "url": "http://example.com/france2.m3u8",
            },
        ]

        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".m3u"
        ) as tmp_file:
            tmp_filename = tmp_file.name

        try:
            write_playlist(entries, tmp_filename)

            with open(tmp_filename, "r", encoding="utf-8") as f:
                content = f.read()

            assert "#EXTM3U" in content
            assert "TF1" in content
            assert "France 2" in content
            assert "http://example.com/tf1.m3u8" in content
            assert "http://example.com/france2.m3u8" in content
        finally:
            if os.path.exists(tmp_filename):
                os.unlink(tmp_filename)

    def test_analyze_failures(self):
        """Test analyzing stream failures"""
        failed_streams = [
            {"error": "timeout"},
            {"error": "404 Not Found"},
            {"error": "403 Forbidden"},
            {"error": "SSL certificate error"},
            {"error": "Unknown error"},
        ]

        result = analyze_failures(failed_streams)
        assert result["Timeout"] == 1
        assert result["404/Not Found"] == 1
        assert result["403/Forbidden"] == 1
        assert result["SSL/Certificate Error"] == 1
        assert result["Other"] == 1

    @patch("cleaner.subprocess.run")
    def test_check_curl_availability_true(self, mock_run):
        """Test curl availability check when curl is available"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = check_curl_availability()
        assert result is True

    @patch("cleaner.subprocess.run")
    def test_check_curl_availability_false(self, mock_run):
        """Test curl availability check when curl is not available"""
        mock_run.side_effect = FileNotFoundError()

        result = check_curl_availability()
        assert result is False

    @patch("cleaner.subprocess.run")
    def test_check_stream_with_curl_success(self, mock_run):
        """Test successful stream check with curl"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "HTTP/1.1 200 OK\nContent-Type: video/mp4\n"
        mock_run.return_value = mock_result

        entry = {"name": "Test Channel", "url": "http://example.com/1080p.m3u8"}
        result = check_stream_with_curl(entry)

        assert result["working"] is True
        assert result["quality"] == "1080p"
        assert result["width"] == 1920
        assert result["height"] == 1080

    @patch("cleaner.subprocess.run")
    def test_check_stream_with_curl_failure(self, mock_run):
        """Test failed stream check with curl"""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "404 Not Found"
        mock_run.return_value = mock_result

        entry = {"name": "Test Channel", "url": "http://example.com/invalid.m3u8"}
        result = check_stream_with_curl(entry)

        assert result["working"] is False
        assert result["quality"] == "failed"
        assert "404 Not Found" in result["error"]

    @patch("cleaner.subprocess.run")
    def test_check_stream_with_curl_timeout(self, mock_run):
        """Test stream check timeout with curl"""
        mock_run.side_effect = subprocess.TimeoutExpired("curl", 15)

        entry = {"name": "Test Channel", "url": "http://example.com/slow.m3u8"}
        result = check_stream_with_curl(entry)

        assert result["working"] is False
        assert result["quality"] == "timeout"
        assert result["error"] == "Timeout"


if __name__ == "__main__":
    pytest.main([__file__])
