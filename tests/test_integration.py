#!/usr/bin/env python3
"""
Integration tests for the TV Playlist Cleaner.

These tests verify end-to-end functionality including downloading,
parsing, validating, and writing playlists.
"""

import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, Mock
import subprocess

# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration


class TestEndToEndFlow:
    """Test complete end-to-end workflow."""

    @pytest.fixture
    def temp_output_file(self):
        """Create temporary output file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.m3u', delete=False) as f:
            yield f.name
        # Cleanup
        if os.path.exists(f.name):
            os.unlink(f.name)

    @pytest.fixture
    def sample_m3u_content(self):
        """Provide sample M3U content for testing."""
        return """#EXTM3U
#EXTINF:-1 tvg-name="TF1",TF1 HD
http://example.com/tf1/stream.m3u8
#EXTINF:-1 tvg-name="France 2",France 2 HD
http://example.com/france2/stream.m3u8
#EXTINF:-1 tvg-name="M6",M6 HD
http://example.com/m6/stream.m3u8
"""

    @patch('playlist_utils.requests.get')
    @patch('playlist_utils.subprocess.run')
    def test_complete_workflow(self, mock_subprocess, mock_requests, sample_m3u_content, temp_output_file):
        """Test complete workflow from download to output."""
        from playlist_utils import (
            download_playlist,
            parse_m3u,
            check_stream_with_curl,
            filter_best_quality,
            write_playlist
        )

        # Mock download
        mock_response = Mock()
        mock_response.headers = {'Content-Type': 'audio/x-mpegurl'}
        mock_response.iter_content = lambda chunk_size, decode_unicode: [sample_m3u_content]
        mock_requests.return_value = mock_response

        # Mock curl validation (all streams working)
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout="HTTP/1.1 200 OK\nContent-Type: video/mp4\n",
            stderr=""
        )

        # Execute workflow
        playlist_text = download_playlist("http://example.com/playlist.m3u")
        assert playlist_text is not None

        entries = parse_m3u(playlist_text)
        assert len(entries) == 3

        # Validate streams
        validated = []
        for entry in entries:
            result = check_stream_with_curl(entry, timeout=5)
            validated.append(result)

        working = [s for s in validated if s.get("working")]
        assert len(working) == 3

        # Filter best quality
        best = filter_best_quality(working)
        assert len(best) == 3

        # Write output
        write_playlist(best, temp_output_file)

        # Verify output file exists and has content
        assert os.path.exists(temp_output_file)
        assert os.path.getsize(temp_output_file) > 0

        # Verify output format
        with open(temp_output_file, 'r') as f:
            content = f.read()
            assert "#EXTM3U" in content
            assert "TF1" in content or "France 2" in content

    @patch('playlist_utils.requests.get')
    def test_download_failure_handling(self, mock_requests):
        """Test handling of download failures."""
        from playlist_utils import download_playlist
        import requests

        # Mock download failure
        mock_requests.side_effect = requests.exceptions.ConnectionError()

        result = download_playlist("http://example.com/playlist.m3u")
        assert result is None

    def test_parse_real_m3u_format(self, sample_m3u_content):
        """Test parsing realistic M3U content."""
        from playlist_utils import parse_m3u

        entries = parse_m3u(sample_m3u_content)

        assert len(entries) == 3
        assert all("name" in entry for entry in entries)
        assert all("url" in entry for entry in entries)
        assert all("info" in entry for entry in entries)


class TestConcurrentProcessing:
    """Test concurrent stream validation."""

    @pytest.fixture
    def mock_streams(self):
        """Create mock stream entries for testing."""
        return [
            {"name": f"Channel {i}", "info": f"#EXTINF:-1,Channel {i}", "url": f"http://example.com/stream{i}"}
            for i in range(20)
        ]

    @patch('playlist_utils.subprocess.run')
    def test_concurrent_validation(self, mock_subprocess, mock_streams):
        """Test concurrent validation of multiple streams."""
        from playlist_utils import check_stream_with_curl
        from concurrent.futures import ThreadPoolExecutor, as_completed

        # Mock successful validation
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout="HTTP/1.1 200 OK\n",
            stderr=""
        )

        results = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(check_stream_with_curl, stream, 5): stream
                for stream in mock_streams
            }

            for future in as_completed(futures):
                results.append(future.result())

        assert len(results) == 20
        assert all(r.get("working") for r in results)


class TestQualitySelection:
    """Test quality selection logic."""

    def test_select_best_among_duplicates(self):
        """Test selection of best quality among duplicate channels."""
        from playlist_utils import filter_best_quality

        streams = [
            {"name": "TF1", "url": "http://a", "width": 854, "height": 480, "working": True, "quality": "480p"},
            {"name": "TF1", "url": "http://b", "width": 1280, "height": 720, "working": True, "quality": "720p"},
            {"name": "TF1", "url": "http://c", "width": 1920, "height": 1080, "working": True, "quality": "1080p"},
            {"name": "France 2", "url": "http://d", "width": 1280, "height": 720, "working": True, "quality": "720p"},
        ]

        result = filter_best_quality(streams, deduplicate=False)

        assert len(result) == 2
        tf1 = [s for s in result if s["name"] == "TF1"][0]
        assert tf1["quality"] == "1080p"
        assert tf1["width"] == 1920


class TestErrorRecovery:
    """Test error recovery and resilience."""

    @patch('playlist_utils.subprocess.run')
    def test_partial_failure_recovery(self, mock_subprocess):
        """Test recovery from partial stream validation failures."""
        from playlist_utils import check_stream_with_curl

        # Simulate alternating success/failure
        mock_subprocess.side_effect = [
            Mock(returncode=0, stdout="HTTP/1.1 200 OK\n", stderr=""),
            Mock(returncode=1, stdout="", stderr="Failed"),
            Mock(returncode=0, stdout="HTTP/1.1 200 OK\n", stderr=""),
        ]

        entries = [
            {"name": "Stream1", "info": "#EXTINF:-1,Stream1", "url": "http://example.com/1"},
            {"name": "Stream2", "info": "#EXTINF:-1,Stream2", "url": "http://example.com/2"},
            {"name": "Stream3", "info": "#EXTINF:-1,Stream3", "url": "http://example.com/3"},
        ]

        results = [check_stream_with_curl(entry, 5) for entry in entries]

        working = [r for r in results if r.get("working")]
        failed = [r for r in results if not r.get("working")]

        assert len(working) == 2
        assert len(failed) == 1


class TestDataIntegrity:
    """Test data integrity throughout the pipeline."""

    def test_preserve_metadata(self):
        """Test that metadata is preserved through processing."""
        from playlist_utils import parse_m3u, filter_best_quality

        m3u = """#EXTM3U
#EXTINF:-1 tvg-id="TF1" tvg-name="TF1" group-title="French",TF1 HD
http://example.com/stream"""

        entries = parse_m3u(m3u)
        assert "tvg-id" in entries[0]["info"]
        assert "tvg-name" in entries[0]["info"]

        # Add required fields for filtering
        for entry in entries:
            entry["working"] = True
            entry["width"] = 1920
            entry["height"] = 1080

        filtered = filter_best_quality(entries)
        assert "tvg-id" in filtered[0]["info"]

    def test_url_preservation(self):
        """Test that URLs are preserved correctly."""
        from playlist_utils import parse_m3u

        url = "http://example.com:8080/live/stream.m3u8?token=abc123"
        m3u = f"#EXTM3U\n#EXTINF:-1,Test\n{url}"

        entries = parse_m3u(m3u)
        assert entries[0]["url"] == url


class TestPerformance:
    """Test performance-related aspects (marked as slow)."""

    @pytest.mark.slow
    @patch('playlist_utils.subprocess.run')
    def test_large_playlist_processing(self, mock_subprocess):
        """Test processing of large playlists."""
        from playlist_utils import parse_m3u

        # Generate large playlist
        num_entries = 1000
        m3u_lines = ["#EXTM3U"]
        for i in range(num_entries):
            m3u_lines.append(f"#EXTINF:-1,Channel {i}")
            m3u_lines.append(f"http://example.com/stream{i}")

        m3u = "\n".join(m3u_lines)

        entries = parse_m3u(m3u)
        assert len(entries) == num_entries

    @pytest.mark.slow
    @patch('playlist_utils.subprocess.run')
    def test_concurrent_performance(self, mock_subprocess):
        """Test concurrent processing performance."""
        from playlist_utils import check_stream_with_curl
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import time

        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout="HTTP/1.1 200 OK\n",
            stderr=""
        )

        entries = [
            {"name": f"Stream{i}", "info": f"#EXTINF:-1,Stream{i}", "url": f"http://example.com/{i}"}
            for i in range(100)
        ]

        start = time.time()

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(check_stream_with_curl, entry, 5): entry
                for entry in entries
            }

            results = [future.result() for future in as_completed(futures)]

        duration = time.time() - start

        assert len(results) == 100
        # Should complete in reasonable time (not sequential)
        assert duration < 30  # Adjust based on expected performance


class TestSecurityValidation:
    """Test security-related validations."""

    def test_url_injection_prevention(self):
        """Test prevention of URL injection attacks."""
        from playlist_utils import validate_url, check_stream_with_curl

        malicious_urls = [
            "http://example.com;rm -rf /",
            "http://example.com|whoami",
            "http://example.com`id`",
            "http://example.com$(whoami)",
        ]

        for url in malicious_urls:
            assert validate_url(url) is False

            entry = {"name": "Test", "info": "#EXTINF:-1,Test", "url": url}
            result = check_stream_with_curl(entry, 5)

            # Should be rejected before subprocess call
            assert result["working"] is False
            assert "Invalid URL" in result["error"]

    def test_safe_file_writing(self, tmpdir):
        """Test safe file writing without path traversal."""
        from playlist_utils import write_playlist

        entries = [
            {"name": "Test", "info": "#EXTINF:-1,Test", "url": "http://test", "quality": "unknown"}
        ]

        # Normal file should work
        output_path = str(tmpdir / "output.m3u")
        write_playlist(entries, output_path)
        assert os.path.exists(output_path)
