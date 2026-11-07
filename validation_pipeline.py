"""Shared retry/cache processing and JSON/CSV reports for every cleaner."""

import csv
import hashlib
import json
import logging
import math
import os
import re
import tempfile
import threading
import time
from concurrent.futures import CancelledError, ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import datetime, timezone

from tqdm import tqdm

from playlist_utils import request_identity, write_playlist

logger = logging.getLogger(__name__)
CACHE_VERSION = 1
CACHE_FIELDS = ("working", "quality", "width", "height", "content_type", "method")
PROBE_FIELDS = CACHE_FIELDS + (
    "error",
    "retryable",
    "http_status",
    "attempts",
    "cached",
)
REPORT_FIELDS = (
    "index",
    "name",
    "url",
    "source",
    "status",
    "reason",
    "quality",
    "width",
    "height",
    "method",
    "error",
    "attempts",
    "cached",
    "reused",
)


def add_processing_arguments(parser):
    parser.add_argument(
        "--retries",
        type=int,
        default=2,
        help="Nouvelles tentatives sur erreur temporaire (0-5)",
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=0.5,
        help="Délai initial entre tentatives, en secondes (0-30)",
    )
    parser.add_argument(
        "--cache", help="Fichier JSON du cache temporaire (désactivé par défaut)"
    )
    parser.add_argument(
        "--cache-ttl",
        type=int,
        default=3600,
        help="Validité du cache en secondes (0 désactive le cache)",
    )
    parser.add_argument("--report-json", help="Rapport détaillé au format JSON")
    parser.add_argument("--report-csv", help="Rapport détaillé au format CSV")


def validate_processing_arguments(args, parser):
    if not 0 <= args.retries <= 5:
        parser.error("--retries doit être compris entre 0 et 5")
    if not math.isfinite(args.retry_delay) or not 0 <= args.retry_delay <= 30:
        parser.error("--retry-delay doit être compris entre 0 et 30")
    if args.cache_ttl < 0:
        parser.error("--cache-ttl doit être positif ou nul")
    paths = [args.output, args.cache, args.report_json, args.report_csv]
    paths = [os.path.realpath(path) for path in paths if path]
    if len(paths) != len(set(paths)):
        parser.error(
            "Playlist, cache et rapports doivent utiliser des fichiers distincts"
        )
    source = getattr(args, "input", None)
    if source and os.path.realpath(source) in paths[1:]:
        parser.error(
            "Le cache et les rapports ne doivent pas remplacer le fichier source"
        )


@contextmanager
def atomic_text_file(path):
    destination = os.path.realpath(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=os.path.dirname(destination),
            prefix=".playlist-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = handle.name
            yield handle
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


class ValidationCache:
    """Cache positive probe facts only; never persist URLs, headers or errors."""

    def __init__(self, path=None, ttl=3600):
        self.path = path if ttl > 0 else None
        self.ttl = ttl
        self.entries = {}
        self.lock = threading.Lock()
        if self.path:
            try:
                with open(self.path, encoding="utf-8") as handle:
                    raw = handle.read(10 * 1024 * 1024 + 1)
                if len(raw) > 10 * 1024 * 1024:
                    raise ValueError("Cache too large")
                data = json.loads(raw)
                if data.get("version") == CACHE_VERSION and isinstance(
                    data.get("entries"), dict
                ):
                    self.entries = {
                        key: item
                        for key, item in data["entries"].items()
                        if self._valid(item)
                    }
            except FileNotFoundError:
                pass
            except (OSError, ValueError, TypeError, AttributeError):
                logger.warning(
                    "Cache illisible ou invalide : les flux seront revérifiés"
                )

    def _valid(self, item):
        if not isinstance(item, dict):
            return False
        timestamp, result = item.get("checked_at"), item.get("result")
        return (
            isinstance(timestamp, (int, float))
            and 0 <= time.time() - timestamp < self.ttl
            and isinstance(result, dict)
            and result.get("working") is True
            and isinstance(result.get("quality"), str)
            and result.get("method") in ("curl", "ffprobe")
            and all(
                isinstance(result.get(key), int) and result[key] >= 0
                for key in ("width", "height")
            )
        )

    def get(self, key):
        with self.lock:
            item = self.entries.get(key)
            if self._valid(item):
                return {
                    key: item["result"][key]
                    for key in CACHE_FIELDS
                    if key in item["result"]
                }
        return None

    def put(self, key, result):
        if self.path and result.get("working"):
            facts = {key: result[key] for key in CACHE_FIELDS if key in result}
            with self.lock:
                self.entries[key] = {"checked_at": time.time(), "result": facts}

    def save(self):
        if not self.path:
            return
        with self.lock:
            valid = [
                (key, item) for key, item in self.entries.items() if self._valid(item)
            ]
        # Keep bounded disk/memory use; the most recent 10,000 checks are enough.
        valid.sort(key=lambda pair: pair[1]["checked_at"], reverse=True)
        try:
            with atomic_text_file(self.path) as handle:
                json.dump(
                    {"version": CACHE_VERSION, "entries": dict(valid[:10000])}, handle
                )
        except OSError as exc:
            logger.warning("Impossible d'enregistrer le cache : %s", exc)


def is_retryable(result):
    if result.get("working"):
        return False
    if "retryable" in result:
        return bool(result["retryable"])
    error = result.get("error", "").lower()
    if re.search(r"\b(?:400|401|403|404|405|410)\b", error):
        return False
    return bool(re.search(r"\b(?:408|425|429|500|502|503|504)\b", error)) or any(
        word in error
        for word in (
            "timeout",
            "timed out",
            "connection reset",
            "connection refused",
            "temporarily unavailable",
            "temporary failure",
            "connection closed",
            "network is unreachable",
            "server returned 5",
        )
    )


def validate_with_retries(
    entry, validate, method, timeout, retries, delay, cache, cancel_event=None
):
    if cancel_event is not None and cancel_event.is_set():
        raise CancelledError()
    key = hashlib.sha256(
        f"{CACHE_VERSION}:{method}:{timeout}:{request_identity(entry)}".encode()
    ).hexdigest()
    cached = cache.get(key)
    if cached:
        return {**entry, **cached, "cached": True, "attempts": 0}
    for attempt in range(retries + 1):
        if cancel_event is not None and cancel_event.is_set():
            raise CancelledError()
        try:
            result = validate(entry, timeout)
        except Exception as exc:
            result = {
                **entry,
                "working": False,
                "quality": "failed",
                "width": 0,
                "height": 0,
                "method": method,
                "error": str(exc),
                "retryable": False,
            }
        result = {**result, "cached": False, "attempts": attempt + 1}
        if not is_retryable(result) or attempt == retries:
            cache.put(key, result)
            return result
        wait = min(delay * (2**attempt), 30)
        if cancel_event is not None:
            if cancel_event.wait(wait):
                raise CancelledError()
        else:
            time.sleep(wait)


def validate_entries(
    entries, validate, method, args, progress_callback=None, cancel_event=None
):
    """Probe each request once; keep every input row for selection and reports."""
    cache = ValidationCache(args.cache, args.cache_ttl)
    groups = {}
    for index, entry in enumerate(entries):
        groups.setdefault(request_identity(entry), []).append((index, entry))
    results = [None] * len(entries)
    working = completed = 0
    if progress_callback:
        progress_callback(0, len(entries), 0)
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                validate_with_retries,
                group[0][1],
                validate,
                method,
                args.timeout,
                args.retries,
                args.retry_delay,
                cache,
                cancel_event,
            ): group
            for group in groups.values()
        }
        with tqdm(
            total=len(entries),
            desc="Test des flux",
            unit="flux",
            disable=progress_callback is not None,
        ) as progress:
            for future in as_completed(futures):
                if cancel_event is not None and cancel_event.is_set():
                    for pending in futures:
                        pending.cancel()
                    raise CancelledError()
                group = futures[future]
                result = future.result()
                # Copy only probe facts, so each row retains its own original metadata.
                facts = {
                    key: value for key, value in result.items() if key in PROBE_FIELDS
                }
                for position, (index, entry) in enumerate(group):
                    results[index] = {**entry, **facts, "reused": position > 0}
                    if position:
                        results[index]["attempts"] = 0
                completed += len(group)
                working += len(group) if result.get("working") else 0
                progress.update(len(group))
                progress.set_postfix(
                    {"Valides": working, "Échoués": completed - working}
                )
                if progress_callback:
                    progress_callback(completed, len(entries), working)
    cache.save()
    return results


def build_report(results, selected, output_written=False, output_error=None):
    selected_ids = {id(entry) for entry in selected}
    selected_requests = {request_identity(entry) for entry in selected}
    rows = []
    for index, result in enumerate(results, 1):
        if id(result) in selected_ids:
            status, reason = "selected", "best_quality"
        elif not result.get("working"):
            status, reason = "invalid", "validation_failed"
        else:
            status = "discarded"
            reason = (
                "duplicate"
                if request_identity(result) in selected_requests
                else "lower_quality"
            )
        row = {key: result.get(key, "") for key in REPORT_FIELDS}
        row.update(index=index, status=status, reason=reason)
        rows.append(row)
    summary = {
        status: sum(row["status"] == status for row in rows)
        for status in ("selected", "invalid", "discarded")
    }
    summary.update(
        total=len(rows),
        cached=sum(bool(row["cached"]) for row in rows),
        attempts=sum(row["attempts"] or 0 for row in rows),
    )
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "output_written": output_written,
        "output_error": output_error,
        "streams": rows,
    }


def save_outputs(results, selected, args):
    """Write reports even if all streams fail or the playlist cannot be written."""
    written = False
    error = None
    if selected:
        try:
            write_playlist(selected, args.output)
            written = True
        except OSError as exc:
            error = str(exc)
            logger.error("Impossible d'écrire la playlist : %s", exc)
    report = build_report(results, selected, written, error)
    reports_ok = True
    for path, kind in ((args.report_json, "json"), (args.report_csv, "csv")):
        if not path:
            continue
        try:
            with atomic_text_file(path) as handle:
                if kind == "json":
                    json.dump(report, handle, ensure_ascii=False, indent=2)
                    handle.write("\n")
                else:
                    writer = csv.DictWriter(handle, fieldnames=REPORT_FIELDS)
                    writer.writeheader()
                    for row in report["streams"]:
                        # Prevent spreadsheet formula interpretation of playlist text.
                        safe = {
                            key: (
                                "'" + value
                                if isinstance(value, str)
                                and value.lstrip().startswith(("=", "+", "-", "@"))
                                else value
                            )
                            for key, value in row.items()
                        }
                        writer.writerow(safe)
            logger.info("Rapport %s enregistré : %s", kind.upper(), path)
        except OSError as exc:
            reports_ok = False
            logger.error("Impossible d'écrire le rapport %s : %s", kind, exc)
    return written and reports_ok
