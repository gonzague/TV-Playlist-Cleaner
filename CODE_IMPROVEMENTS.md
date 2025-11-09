# Code Improvements Report - TV Playlist Cleaner

Generated: 2025-11-09

## Executive Summary

This codebase has solid functionality but requires significant improvements in:
- **Security**: Command injection risks, weak hashing
- **Code Quality**: 60% code duplication across files
- **Testing**: Only 11% test coverage
- **Error Handling**: Overly broad exception catching
- **Maintainability**: No type hints, minimal logging

---

## CRITICAL ISSUES (Immediate Action Required)

### 1. Command Injection Vulnerability ⚠️
**Severity**: CRITICAL
**Files**: `cleaner.py:46-56`, `cleaner_advanced.py:54-68`, `cleaner_tnt.py:400-415`, `cleaner_multi_source.py:114-129`

**Problem**: URLs from external sources passed directly to subprocess commands.

**Current Code**:
```python
cmd = ["curl", "-I", "--connect-timeout", str(TIMEOUT), url]  # Unvalidated
result = subprocess.run(cmd, capture_output=True, text=True)
```

**Fix**:
```python
import validators
from urllib.parse import urlparse

def validate_stream_url(url: str) -> bool:
    """Validate URL is safe for subprocess calls."""
    if not validators.url(url):
        return False
    parsed = urlparse(url)
    # Only allow http/https
    if parsed.scheme not in ('http', 'https'):
        return False
    # Prevent command injection via protocol handlers
    if any(char in url for char in [';', '&', '|', '`', '$', '(', ')']):
        return False
    return True
```

### 2. Insecure Hash Function (MD5)
**Severity**: MEDIUM (Low impact for this use case)
**Files**: `cleaner_tnt.py:351`, `cleaner_multi_source.py:66`

**Current**:
```python
stream_hash = hashlib.md5(entry["url"].encode()).hexdigest()
```

**Fix**:
```python
stream_hash = hashlib.sha256(entry["url"].encode()).hexdigest()
```

### 3. Unsafe External Downloads
**Severity**: HIGH
**All files**: `download_playlist()` functions

**Issues**:
- No SSL certificate verification control
- No timeout (except cleaner_tnt.py)
- No size limits
- No content-type validation

**Fix**:
```python
import requests
from typing import Optional

MAX_PLAYLIST_SIZE = 50 * 1024 * 1024  # 50MB

def download_playlist(url: str, timeout: int = 30) -> Optional[str]:
    """
    Download playlist with safety checks.

    Args:
        url: Playlist URL to download
        timeout: Request timeout in seconds

    Returns:
        Playlist content or None on error
    """
    try:
        response = requests.get(
            url,
            timeout=timeout,
            stream=True,
            headers={'User-Agent': 'TV-Playlist-Cleaner/1.0'}
        )
        response.raise_for_status()

        # Check content type
        content_type = response.headers.get('Content-Type', '')
        if 'audio/x-mpegurl' not in content_type and 'text/plain' not in content_type:
            logging.warning(f"Unexpected content type: {content_type}")

        # Check size
        content_length = response.headers.get('Content-Length')
        if content_length and int(content_length) > MAX_PLAYLIST_SIZE:
            raise ValueError(f"Playlist too large: {content_length} bytes")

        # Download with size limit
        content = []
        size = 0
        for chunk in response.iter_content(chunk_size=8192, decode_unicode=True):
            size += len(chunk)
            if size > MAX_PLAYLIST_SIZE:
                raise ValueError("Playlist exceeds size limit")
            content.append(chunk)

        return ''.join(content)

    except requests.exceptions.RequestException as e:
        logging.error(f"Download failed for {url}: {e}")
        return None
```

---

## HIGH PRIORITY ISSUES

### 4. Massive Code Duplication (60%)
**Severity**: HIGH
**Impact**: Maintenance nightmare, inconsistent implementations

**Duplicated Functions**:
- `parse_m3u()` - 4 times
- `download_playlist()` - 4 times
- `check_direct_stream()` - 3 times
- `filter_best_quality()` - 4 times
- `write_playlist()` - 4 times

**Solution**: Create shared module `playlist_utils.py`:

```python
# playlist_utils.py
"""Shared utilities for M3U playlist processing."""

from typing import List, Dict, Optional, Tuple
import re
import hashlib
import subprocess
import logging

class PlaylistEntry:
    """Structured representation of a playlist entry."""
    def __init__(self, name: str, info: str, url: str, quality: Optional[str] = None):
        self.name = name
        self.info = info
        self.url = url
        self.quality = quality
        self.resolution: Optional[Tuple[int, int]] = None

def parse_m3u(m3u_text: str) -> List[Dict[str, str]]:
    """Parse M3U content and extract stream information."""
    # Single implementation used by all scripts
    pass

def validate_stream(url: str, timeout: int = 15) -> Tuple[bool, Optional[str]]:
    """Validate stream URL and detect quality."""
    pass

def deduplicate_entries(entries: List[Dict]) -> List[Dict]:
    """Remove duplicate streams keeping best quality."""
    pass
```

### 5. No Logging Framework
**Severity**: HIGH
**Current**: All scripts use `print()` statements

**Fix**: Implement proper logging:

```python
# Add to each script
import logging
from pathlib import Path

def setup_logging(verbose: bool = False, log_file: Optional[Path] = None):
    """Configure logging for the application."""
    level = logging.DEBUG if verbose else logging.INFO

    handlers = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )

# Replace all print() with:
logging.info("Test des flux...")
logging.warning("Échec de téléchargement")
logging.error("Erreur critique", exc_info=True)
```

### 6. Missing Type Hints
**Severity**: HIGH
**Current**: 0% type coverage

**Fix**: Add type hints to all functions:

```python
from typing import List, Dict, Optional, Tuple, Any
from concurrent.futures import Future

def parse_m3u(m3u_text: str) -> List[Dict[str, str]]:
    """Parse M3U content and extract stream information."""
    pass

def check_stream_with_curl(
    url: str,
    timeout: int = 15
) -> Tuple[bool, Optional[str], str]:
    """Check stream availability using curl."""
    pass

def filter_best_quality(
    streams: List[Dict[str, Any]],
    deduplicate: bool = True
) -> List[Dict[str, Any]]:
    """Select best quality stream for each channel."""
    pass
```

### 7. Inadequate Error Handling
**Severity**: HIGH

**Current Problems**:
```python
# Too broad
except Exception as e:
    print(f"Error: {e}")
    return None  # Silent failure

# No retry logic for network errors
# No exception chaining
```

**Fix**:
```python
import time
from requests.exceptions import Timeout, ConnectionError

def download_with_retry(
    url: str,
    max_retries: int = 3,
    timeout: int = 30
) -> Optional[str]:
    """Download with exponential backoff retry."""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            return response.text

        except (Timeout, ConnectionError) as e:
            if attempt == max_retries - 1:
                logging.error(f"Failed after {max_retries} attempts: {e}")
                raise
            wait_time = 2 ** attempt
            logging.warning(f"Retry {attempt + 1}/{max_retries} after {wait_time}s")
            time.sleep(wait_time)

        except requests.HTTPError as e:
            logging.error(f"HTTP error {e.response.status_code}: {url}")
            raise

        except Exception as e:
            logging.error(f"Unexpected error downloading {url}", exc_info=True)
            raise
```

### 8. Long and Complex Functions
**Severity**: HIGH
**Examples**:
- `cleaner_tnt.py:main()` - 145 lines
- `cleaner_multi_source.py:main()` - 132 lines

**Fix**: Break down into smaller functions:

```python
def main():
    """Main entry point."""
    config = parse_arguments()
    setup_logging(config.verbose)

    # Download
    playlists = download_playlists(config.sources)

    # Parse
    entries = parse_playlists(playlists)

    # Validate
    valid_entries = validate_streams(entries, config)

    # Process
    best_entries = select_best_quality(valid_entries)

    # Save
    save_playlist(best_entries, config.output)

    # Report
    print_statistics(entries, valid_entries, best_entries)
```

### 9. Inadequate Testing
**Severity**: HIGH
**Current**: Only `test_cleaner.py` exists (11% coverage)

**Missing**:
- Tests for `cleaner_advanced.py`
- Tests for `cleaner_tnt.py`
- Tests for `cleaner_multi_source.py`
- Integration tests
- Edge case tests

**Add**:
```python
# tests/test_playlist_utils.py
import pytest
from playlist_utils import parse_m3u, validate_stream_url

class TestParseM3U:
    def test_valid_playlist(self):
        """Test parsing valid M3U content."""
        m3u = "#EXTM3U\n#EXTINF:-1,Test Channel\nhttp://example.com/stream"
        entries = parse_m3u(m3u)
        assert len(entries) == 1
        assert entries[0]["name"] == "Test Channel"

    def test_malformed_playlist(self):
        """Test handling of malformed M3U."""
        with pytest.raises(ValueError):
            parse_m3u("Invalid content")

    def test_empty_playlist(self):
        """Test empty playlist handling."""
        entries = parse_m3u("#EXTM3U\n")
        assert len(entries) == 0

class TestURLValidation:
    @pytest.mark.parametrize("url,expected", [
        ("http://example.com/stream.m3u8", True),
        ("https://example.com/stream", True),
        ("ftp://malicious.com", False),
        ("http://test.com;rm -rf /", False),
        ("http://test.com|whoami", False),
    ])
    def test_url_validation(self, url, expected):
        """Test URL validation prevents injection."""
        assert validate_stream_url(url) == expected
```

### 10. Security Configuration
**Severity**: HIGH
**File**: `pyproject.toml:115`

**Problem**: Bandit skips shell injection check:
```toml
[tool.bandit]
skips = ["B101", "B601"]  # B601 = shell injection!
```

**Fix**: Remove B601 skip and fix the issues instead.

---

## MEDIUM PRIORITY ISSUES

### 11. Performance Issues

**A. Inefficient Future Processing**:
```python
# Current (blocks in submission order)
for future in future_to_entry:
    result = future.result()

# Better (process as completed)
from concurrent.futures import as_completed
for future in as_completed(future_to_entry):
    result = future.result()
```

**B. No Caching**:
```python
# Add simple cache
import time
from typing import Dict

class PlaylistCache:
    def __init__(self, ttl: int = 3600):
        self.cache: Dict[str, Tuple[float, str]] = {}
        self.ttl = ttl

    def get(self, url: str) -> Optional[str]:
        if url in self.cache:
            timestamp, content = self.cache[url]
            if time.time() - timestamp < self.ttl:
                return content
        return None

    def set(self, url: str, content: str):
        self.cache[url] = (time.time(), content)
```

### 12. Configuration Management
**Severity**: MEDIUM

**Add environment variable support**:
```python
from pathlib import Path
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Application configuration."""

    TIMEOUT: int = int(os.getenv('PLAYLIST_TIMEOUT', '15'))
    MAX_WORKERS: int = int(os.getenv('PLAYLIST_WORKERS', '10'))
    OUTPUT_FILE: Path = Path(os.getenv('PLAYLIST_OUTPUT', 'filtered.m3u'))
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    CACHE_DIR: Optional[Path] = Path(os.getenv('CACHE_DIR')) if os.getenv('CACHE_DIR') else None
```

### 13. Input Validation
**Severity**: MEDIUM

**Add argument validation**:
```python
def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--workers",
        type=int,
        default=10,
        help="Number of parallel workers (1-50)"
    )
    args = parser.parse_args()

    # Validate
    if not (1 <= args.workers <= 50):
        parser.error("Workers must be between 1 and 50")

    return args
```

### 14. Resource Management

**Add cleanup and context managers**:
```python
from contextlib import contextmanager
import tempfile
import shutil

@contextmanager
def temporary_workspace():
    """Create temporary directory for processing."""
    tmpdir = tempfile.mkdtemp(prefix='playlist_')
    try:
        yield Path(tmpdir)
    finally:
        shutil.rmtree(tmpdir)

# Usage
with temporary_workspace() as workspace:
    temp_file = workspace / "temp.m3u"
    # Process...
```

### 15. Code Organization

**Suggested structure**:
```
tv_playlist_cleaner/
├── __init__.py
├── core/
│   ├── __init__.py
│   ├── parser.py          # M3U parsing
│   ├── validator.py       # Stream validation
│   ├── processor.py       # Quality selection
│   └── models.py          # Data classes
├── cli/
│   ├── __init__.py
│   ├── main.py
│   ├── tnt.py
│   └── config.py
├── utils/
│   ├── __init__.py
│   ├── network.py
│   ├── cache.py
│   └── logging.py
└── config/
    ├── __init__.py
    └── sources.py
tests/
├── __init__.py
├── test_parser.py
├── test_validator.py
└── integration/
    └── test_end_to_end.py
```

---

## LOW PRIORITY ISSUES

### 16. Modern Python Features

**Use dataclasses**:
```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class StreamEntry:
    """Represents a single stream entry."""
    name: str
    url: str
    info: str
    quality: Optional[str] = None
    resolution: Optional[tuple[int, int]] = None
    method: str = "curl"

    @property
    def quality_score(self) -> int:
        """Calculate quality score for comparison."""
        if not self.resolution:
            return 0
        return self.resolution[0] * self.resolution[1]
```

**Use pathlib**:
```python
from pathlib import Path

# Instead of
with open("output.m3u", "w") as f:
    f.write(content)

# Use
output_path = Path("output.m3u")
output_path.write_text(content, encoding="utf-8")
```

**Use enums**:
```python
from enum import Enum, auto

class Quality(Enum):
    """Stream quality levels."""
    SD_480 = (854, 480)
    HD_720 = (1280, 720)
    FULL_HD_1080 = (1920, 1080)
    UHD_4K = (3840, 2160)

    @classmethod
    def from_resolution(cls, width: int, height: int):
        """Determine quality from resolution."""
        pixels = width * height
        if pixels >= 3840 * 2160:
            return cls.UHD_4K
        elif pixels >= 1920 * 1080:
            return cls.FULL_HD_1080
        elif pixels >= 1280 * 720:
            return cls.HD_720
        else:
            return cls.SD_480
```

### 17. Code Style

**Fix .flake8 configuration**:
```ini
[flake8]
max-line-length = 100
exclude = .git,__pycache__,.venv
# Don't ignore important checks
extend-ignore = E203, W503
# Keep these enabled: E501, F401, F841, C901
max-complexity = 10
```

**Use constants**:
```python
# Instead of magic numbers
RESOLUTION_1080P = 1920
RESOLUTION_720P = 1280
RESOLUTION_480P = 854

# Quality thresholds
MIN_HD_WIDTH = RESOLUTION_720P
MIN_FULL_HD_WIDTH = RESOLUTION_1080P
```

### 18. Documentation

**Improve docstrings**:
```python
def filter_best_quality(
    streams: List[Dict[str, Any]],
    deduplicate: bool = True
) -> List[Dict[str, Any]]:
    """
    Select the highest quality stream for each unique channel.

    This function groups streams by channel name (normalized) and selects
    the stream with the highest resolution for each channel. Optionally
    deduplicates streams based on URL hash.

    Args:
        streams: List of stream dictionaries containing 'name', 'url',
                 'quality', and optionally 'resolution' keys.
        deduplicate: If True, removes streams with duplicate URLs.

    Returns:
        Filtered list of streams with best quality per channel.

    Raises:
        ValueError: If streams list is empty or malformed.

    Example:
        >>> streams = [
        ...     {"name": "TF1", "url": "http://a", "resolution": "1920x1080"},
        ...     {"name": "TF1", "url": "http://b", "resolution": "1280x720"}
        ... ]
        >>> result = filter_best_quality(streams)
        >>> len(result)
        1
        >>> result[0]["resolution"]
        '1920x1080'
    """
    pass
```

---

## SPECIFIC FILE ISSUES

### demo.py
- Line 22: Truncates output to 500 chars (may hide errors)
- Line 65: References obsolete `--direct-only` flag
- No error handling for missing files

### sources_config.py
- Line 28: Typo in URL (`.m3us` should be `.m3u`)

### cleaner_config.py
- Line 62: `subprocess.run()` without timeout
- No validation of category input

---

## RECOMMENDED IMPLEMENTATION PHASES

### Phase 1: Critical Security (Week 1)
- [ ] Add URL validation to prevent injection
- [ ] Implement request timeouts and size limits
- [ ] Fix error handling with proper exceptions
- [ ] Add comprehensive logging
- [ ] Fix Bandit configuration

### Phase 2: Code Quality (Weeks 2-3)
- [ ] Extract shared functions to `playlist_utils.py`
- [ ] Add type hints to all functions
- [ ] Break down long functions
- [ ] Remove code duplication
- [ ] Add configuration management

### Phase 3: Testing (Week 4)
- [ ] Write tests for all modules (target 80% coverage)
- [ ] Add integration tests
- [ ] Add edge case tests (malformed M3U, huge files, etc.)
- [ ] Add performance tests
- [ ] Set up CI/CD with pytest

### Phase 4: Improvements (Weeks 5-6)
- [ ] Refactor to proper package structure
- [ ] Implement caching
- [ ] Optimize concurrent processing
- [ ] Improve documentation
- [ ] Add examples and tutorials

### Phase 5: Polish (Week 7)
- [ ] Use modern Python features (dataclasses, pathlib)
- [ ] Improve CLI UX
- [ ] Add progress persistence
- [ ] Add internationalization
- [ ] Performance profiling and optimization

---

## QUICK WINS (Easy improvements with high impact)

1. **Add logging** (2 hours)
   - Replace all `print()` with `logging`
   - Immediate debugging benefit

2. **Add type hints** (4 hours)
   - Add to function signatures
   - Catch bugs with mypy

3. **Fix URL validation** (2 hours)
   - Add `validators` library
   - Prevent injection attacks

4. **Extract common functions** (4 hours)
   - Create `playlist_utils.py`
   - Reduce duplication by 60%

5. **Add request timeouts** (1 hour)
   - Add to all `requests.get()` calls
   - Prevent hanging

6. **Fix typo in sources_config.py** (1 minute)
   - Line 28: `.m3us` → `.m3u`

---

## TOOLS TO ADD

Recommended additions to `pyproject.toml`:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "mypy>=1.0",
    "black>=23.0",
    "ruff>=0.1.0",
    "bandit>=1.7",
]

[tool.mypy]
python_version = "3.8"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true

[tool.coverage.run]
source = ["tv_playlist_cleaner"]
omit = ["tests/*"]

[tool.coverage.report]
fail_under = 80
```

---

## CONCLUSION

This codebase has solid functionality but needs significant refactoring for production use. The main concerns are:

1. **Security vulnerabilities** in URL handling
2. **60% code duplication** making maintenance difficult
3. **Lack of proper error handling** and logging
4. **Minimal testing** (11% coverage)
5. **No type hints** making code harder to maintain

Following the recommended phases above will result in a robust, maintainable, and secure codebase.
