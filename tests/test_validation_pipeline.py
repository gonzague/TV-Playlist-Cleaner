"""Retry policy, cache isolation, headers, and auditable selection reports."""

import csv
import json
from unittest.mock import Mock, patch

import pytest
import requests

import cleaner
from playlist_utils import (
    check_stream_with_curl,
    check_stream_with_ffprobe,
    download_playlist,
    filter_best_quality,
    request_identity,
    stream_request,
)
from validation_pipeline import (
    ValidationCache,
    build_report,
    is_retryable,
    save_outputs,
    validate_entries,
    validate_with_retries,
)


@pytest.fixture
def entry():
    return {"name": "TF1", "info": "#EXTINF:-1,TF1", "url": "http://example.com/tv"}


def success(entry):
    return {
        **entry,
        "working": True,
        "quality": "720p",
        "height": 720,
        "width": 1280,
        "method": "curl",
    }


def options(tmp_path, *extra):
    return cleaner.parse_arguments(
        ["--output", str(tmp_path / "out.m3u"), "--retry-delay", "0", *extra]
    )


def test_retries_transient_error_then_succeeds(entry):
    validate = Mock(
        side_effect=[{**entry, "working": False, "error": "Timeout"}, success(entry)]
    )
    with patch("validation_pipeline.time.sleep") as sleep:
        result = validate_with_retries(
            entry, validate, "curl", 5, 2, 0.5, ValidationCache()
        )
    assert result["working"] and result["attempts"] == 2
    sleep.assert_called_once_with(0.5)


def test_retry_budget_and_exponential_delay(entry):
    validate = Mock(return_value={**entry, "working": False, "error": "HTTP Error 503"})
    with patch("validation_pipeline.time.sleep") as sleep:
        result = validate_with_retries(
            entry, validate, "curl", 5, 3, 1, ValidationCache()
        )
    assert result["attempts"] == validate.call_count == 4
    assert [call.args[0] for call in sleep.call_args_list] == [1, 2, 4]


@pytest.mark.parametrize(
    "error,retryable",
    [
        ("HTTP Error 429", True),
        ("Server returned 503 Service Unavailable", True),
        ("Connection reset by peer", True),
        ("Connection timed out", True),
        ("404 Not Found", False),
        ("403 Forbidden", False),
        ("Invalid URL", False),
        ("SSL certificate error", False),
        ("Invalid data found when processing input", False),
    ],
)
def test_retry_classification(error, retryable):
    assert is_retryable({"working": False, "error": error}) is retryable


def test_permanent_failure_is_not_retried_or_cached(entry, tmp_path):
    cache = ValidationCache(tmp_path / "cache.json")
    validate = Mock(return_value={**entry, "working": False, "error": "403 Forbidden"})
    for _ in range(2):
        result = validate_with_retries(entry, validate, "curl", 5, 2, 0, cache)
        assert result["attempts"] == 1
    assert validate.call_count == 2
    assert cache.entries == {}


def test_cache_reloads_positive_facts_without_old_channel_metadata(entry, tmp_path):
    path = tmp_path / "cache.json"
    entry["directives"] = "#EXTVLCOPT:http-cookie=private-session"
    validate = Mock(side_effect=lambda entry, timeout: success(entry))
    cache = ValidationCache(path)
    validate_with_retries(entry, validate, "curl", 5, 0, 0, cache)
    cache.save()
    cached_text = path.read_text()
    assert "private-session" not in cached_text and "example.com" not in cached_text
    renamed = {**entry, "name": "Renamed", "source": "new-source"}
    result = validate_with_retries(
        renamed,
        Mock(side_effect=AssertionError("cache miss")),
        "curl",
        5,
        0,
        0,
        ValidationCache(path),
    )
    assert result["cached"] and result["attempts"] == 0
    assert result["name"] == "Renamed" and result["source"] == "new-source"


@pytest.mark.parametrize(
    "change", ["expired", "headers", "method", "timeout", "disabled", "url"]
)
def test_cache_invalidation(entry, tmp_path, change):
    path = tmp_path / "cache.json"
    validate = Mock(side_effect=lambda entry, timeout: success(entry))
    with patch("validation_pipeline.time.time", return_value=1000):
        cache = ValidationCache(path, ttl=60)
        validate_with_retries(entry, validate, "curl", 5, 0, 0, cache)
        cache.save()
    when = 1060 if change == "expired" else 1001
    if change == "headers":
        entry = {**entry, "directives": "#EXTVLCOPT:http-user-agent=Changed"}
    if change == "url":
        entry = {**entry, "url": entry["url"] + "?token=other"}
    with patch("validation_pipeline.time.time", return_value=when):
        result = validate_with_retries(
            entry,
            validate,
            "ffprobe" if change == "method" else "curl",
            6 if change == "timeout" else 5,
            0,
            0,
            ValidationCache(path, ttl=0 if change == "disabled" else 60),
        )
    assert not result["cached"] and validate.call_count == 2


@pytest.mark.parametrize(
    "content", ["not JSON", "[]", '{"version":1,"entries":{"bad":null}}']
)
def test_corrupt_cache_does_not_stop_validation(entry, tmp_path, content):
    path = tmp_path / "cache.json"
    path.write_text(content)
    validate = Mock(side_effect=lambda entry, timeout: success(entry))
    result = validate_with_retries(
        entry, validate, "curl", 5, 0, 0, ValidationCache(path)
    )
    assert result["working"] and not result["cached"]


def test_duplicates_share_probe_and_preserve_rows(entry, tmp_path):
    entries = [
        entry,
        {**entry, "name": "Second label", "source": "second"},
        {**entry, "directives": "#EXTVLCOPT:http-cookie=different"},
    ]
    validate = Mock(side_effect=lambda entry, timeout: success(entry))
    results = validate_entries(entries, validate, "curl", options(tmp_path))
    assert validate.call_count == 2
    assert len(results) == 3 and results[1]["reused"]
    assert results[1]["source"] == "second" and results[1]["attempts"] == 0
    assert not results[2]["reused"]


def test_vlc_and_kodi_headers_are_combined_and_decoded(entry):
    entry["directives"] = (
        "#EXTVLCOPT:http-user-agent=VLC Test\n"
        "#EXTVLCOPT:http-referrer=https://example.com/player\n"
        "#KODIPROP:inputstream.adaptive.common_headers=User-Agent=Kodi%2F1&Cookie=token%3Da%2Bb\n"
        "#KODIPROP:inputstream.adaptive.manifest_headers=X-Key=manifest\n"
        "#KODIPROP:inputstream.adaptive.stream_headers=Origin=https%3A%2F%2Fexample.com"
    )
    url, headers = stream_request(entry)
    assert url == entry["url"]
    assert headers == {
        "user-agent": "Kodi/1",
        "referer": "https://example.com/player",
        "cookie": "token=a+b",
        "x-key": "manifest",
        "origin": "https://example.com",
    }


def test_url_suffix_headers_and_request_identity(entry):
    encoded = {**entry, "url": entry["url"] + "|User-Agent=Client%2F1"}
    directive = {**entry, "directives": "#EXTVLCOPT:http-user-agent=Client/1"}
    assert request_identity(encoded) == request_identity(directive)
    assert request_identity(entry) != request_identity(encoded)


@pytest.mark.parametrize(
    "headers",
    [
        "X-Test=ok%0D%0AInjected%3Ayes",
        "Host=other",
        "bad+name=value",
        "X-Test=bad%00value",
        "broken",
    ],
)
@pytest.mark.parametrize(
    "validate", [check_stream_with_curl, check_stream_with_ffprobe]
)
def test_invalid_headers_fail_before_subprocess(entry, headers, validate):
    entry["directives"] = "#KODIPROP:inputstream.adaptive.stream_headers=" + headers
    with patch("playlist_utils.subprocess.run") as run:
        result = validate(entry)
    assert not result["working"] and result["method"] == "validation"
    run.assert_not_called()


def test_conflicting_kodi_headers_are_not_silently_merged(entry):
    entry["directives"] = (
        "#KODIPROP:inputstream.adaptive.manifest_headers=Cookie=a\n"
        "#KODIPROP:inputstream.adaptive.stream_headers=Cookie=b"
    )
    with pytest.raises(ValueError, match="Distinct Kodi"):
        stream_request(entry)


@pytest.mark.parametrize(
    "status,expected_calls", [(503, 2), (429, 2), (404, 1), (403, 1)]
)
def test_playlist_download_retry_policy(status, expected_calls):
    failed = Mock(status_code=status)
    failed.raise_for_status.side_effect = requests.HTTPError(response=failed)
    good = Mock(headers={})
    good.iter_content.return_value = [b"#EXTM3U\n"]
    with patch("playlist_utils.requests.get", side_effect=[failed, good]) as get:
        result = download_playlist(
            "https://example.com/test.m3u", retries=2, retry_delay=0
        )
    assert get.call_count == expected_calls
    assert result == ("#EXTM3U\n" if expected_calls == 2 else None)
    failed.close.assert_called_once()


def test_reports_account_for_invalid_duplicate_and_lower_quality(entry, tmp_path):
    results = [
        success(entry),
        success(entry),
        {**success(entry), "url": "http://example.com/low", "height": 480},
        {**entry, "working": False, "error": "404 Not Found"},
    ]
    selected = filter_best_quality(results)
    report = build_report(results, selected)
    assert [row["reason"] for row in report["streams"]] == [
        "best_quality",
        "duplicate",
        "lower_quality",
        "validation_failed",
    ]
    assert report["summary"]["selected"] == 1
    args = options(
        tmp_path,
        "--report-json",
        str(tmp_path / "report.json"),
        "--report-csv",
        str(tmp_path / "report.csv"),
    )
    assert save_outputs(results, selected, args)
    saved = json.loads((tmp_path / "report.json").read_text())
    assert saved["output_written"]
    with (tmp_path / "report.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 4 and rows[-1]["error"] == "404 Not Found"


def test_reports_written_when_all_streams_fail(entry, tmp_path):
    args = options(tmp_path, "--report-json", str(tmp_path / "report.json"))
    output = tmp_path / "out.m3u"
    output.write_text("old playlist")
    assert not save_outputs([{**entry, "working": False, "error": "403"}], [], args)
    assert output.read_text() == "old playlist"
    report = json.loads((tmp_path / "report.json").read_text())
    assert report["summary"]["invalid"] == 1 and not report["output_written"]


def test_report_records_playlist_write_failure(entry, tmp_path):
    args = options(tmp_path, "--report-json", str(tmp_path / "report.json"))
    result = success(entry)
    with patch("validation_pipeline.write_playlist", side_effect=OSError("disk error")):
        assert not save_outputs([result], [result], args)
    report = json.loads((tmp_path / "report.json").read_text())
    assert report["output_error"] == "disk error" and not report["output_written"]


def test_csv_quotes_labels_and_neutralizes_formulas(entry, tmp_path):
    entry["name"] = '=HYPERLINK("http://example.com", "écran")'
    result = success(entry)
    args = options(tmp_path, "--report-csv", str(tmp_path / "report.csv"))
    assert save_outputs([result], [result], args)
    with (tmp_path / "report.csv").open(newline="") as handle:
        assert next(csv.DictReader(handle))["name"] == "'" + entry["name"]


@pytest.mark.parametrize(
    "args",
    [
        ["--retries", "6"],
        ["--retry-delay", "nan"],
        ["--retry-delay", "inf"],
        ["--retry-delay", "-1"],
        ["--cache-ttl", "-1"],
        ["--output", "same", "--report-json", "same"],
        ["--input", "same", "--cache", "same"],
        ["--report-csv", "same", "--report-json", "same"],
    ],
)
def test_invalid_processing_options(args):
    with pytest.raises(SystemExit) as exc:
        cleaner.parse_arguments(args)
    assert exc.value.code == 2
