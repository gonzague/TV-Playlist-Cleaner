"""Local web interface for the playlist cleaning engine."""

import argparse
import atexit
import copy
import json
import logging
import math
import re
import secrets
import shutil
import threading
import time
from concurrent.futures import CancelledError, ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

from flask import Flask, Response, abort, jsonify, render_template, request, send_file
from werkzeug.exceptions import HTTPException

from cleaner_multi_source import parse_m3u_with_source
from playlist_utils import (
    MAX_PLAYLIST_SIZE,
    check_stream_with_curl,
    check_stream_with_ffprobe,
    check_tool_availability,
    download_playlist,
    filter_best_quality,
    validate_url,
)
from sources_config import CATEGORY_MAP
from validation_pipeline import (
    atomic_text_file,
    build_report,
    save_outputs,
    validate_entries,
)
from .media import LogoCatalog, playback_metadata
from .metadata import ChannelCatalog
from .relay import PlaybackPool, media_response

logger = logging.getLogger(__name__)
DEFAULT_URL = "https://iptv-org.github.io/iptv/countries/fr.m3u"
TERMINAL = {"completed", "failed", "cancelled"}
MAX_ENTRIES = 10000
PRESETS = {
    "france": ("France · iptv-org", [DEFAULT_URL]),
    "french": ("France · multi-sources", CATEGORY_MAP["french"]),
    "english": ("Chaînes anglophones", CATEGORY_MAP["english"]),
    "european": ("Europe", CATEGORY_MAP["european"]),
    "news": ("Information", CATEGORY_MAP["news"]),
    "sports": ("Sport", CATEGORY_MAP["sports"]),
    "movies": ("Cinéma", CATEGORY_MAP["movies"]),
    "kids": ("Jeunesse", CATEGORY_MAP["kids"]),
}
ARTIFACTS = {
    "playlist": ("playlist.m3u", "audio/x-mpegurl"),
    "json": ("report.json", "application/json"),
    "csv": ("report.csv", "text/csv"),
}


def parse_options(raw):
    if not isinstance(raw, dict):
        raise ValueError("Les réglages doivent être un objet JSON.")
    method = raw.get("validator", "ffprobe")
    if method not in ("curl", "ffprobe"):
        raise ValueError("Méthode de vérification inconnue.")
    options = {"validator": method}
    for name, default, minimum, maximum in (
        ("workers", 10, 1, 50),
        ("timeout", 15, 1, 60),
        ("retries", 2, 0, 5),
        ("cache_ttl", 3600, 1, 86400),
    ):
        value = raw.get(name, default)
        if type(value) is not int or not minimum <= value <= maximum:
            raise ValueError(f"{name} doit être compris entre {minimum} et {maximum}.")
        options[name] = value
    delay = raw.get("retry_delay", 0.5)
    if (
        type(delay) not in (int, float)
        or not math.isfinite(delay)
        or not 0 <= delay <= 30
    ):
        raise ValueError(
            "Le délai entre tentatives doit être compris entre 0 et 30 secondes."
        )
    options["retry_delay"] = delay
    cache = raw.get("use_cache", True)
    if type(cache) is not bool:
        raise ValueError("Le choix du cache doit être un booléen.")
    options["use_cache"] = cache
    return options


class JobManager:
    """One active run, bounded recent results, cancellable stream verification."""

    def __init__(self, directory):
        self.directory = Path(directory).expanduser().resolve()
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock = threading.RLock()
        self.executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="playlist-web"
        )
        self.jobs = {}
        self.events = {}
        self.logos = LogoCatalog(self.directory)
        self.catalog = ChannelCatalog(self.directory)
        self.prune()

    def prune(self):
        with self.lock:
            for job_id, job in list(self.jobs.items()):
                if job["state"] in TERMINAL and (
                    time.time() - job["created_at"] > 86400 or len(self.jobs) >= 10
                ):
                    self.jobs.pop(job_id)
                    self.events.pop(job_id)
                    shutil.rmtree(self.directory / job_id, ignore_errors=True)
            for folder in self.directory.iterdir():
                if (
                    re.fullmatch(r"[a-f0-9]{32}", folder.name)
                    and folder.name not in self.jobs
                    and not folder.is_symlink()
                    and folder.is_dir()
                ):
                    if time.time() - folder.stat().st_mtime > 86400:
                        shutil.rmtree(folder)

    def create(self, source, options):
        with self.lock:
            if any(job["state"] not in TERMINAL for job in self.jobs.values()):
                raise RuntimeError(
                    "Une analyse est déjà en cours. Attendez sa fin ou annulez-la."
                )
            self.prune()
            job_id = secrets.token_hex(16)
            folder = self.directory / job_id
            folder.mkdir(mode=0o700)
            self.jobs[job_id] = {
                "id": job_id,
                "state": "queued",
                "stage": "Préparation…",
                "source": source["label"],
                "created_at": time.time(),
                "completed": 0,
                "total": 0,
                "working": 0,
                "warnings": [],
                "error": None,
                "summary": None,
                "downloads": {},
            }
            self.events[job_id] = threading.Event()
            self.executor.submit(self.run, job_id, source, options)
            return job_id

    def update(self, job_id, **values):
        with self.lock:
            self.jobs[job_id].update(values)

    def snapshot(self, job_id):
        with self.lock:
            return copy.deepcopy(self.jobs.get(job_id))

    def cancel(self, job_id):
        with self.lock:
            job = self.jobs.get(job_id)
            if job is None:
                return False
            if job["state"] not in TERMINAL:
                self.events[job_id].set()
                job.update(
                    state="cancelling", stage="Annulation après les requêtes en cours…"
                )
            return True

    def run(self, job_id, source, options):
        event = self.events[job_id]
        folder = self.directory / job_id
        args = SimpleNamespace(
            **options,
            output=str(folder / "playlist.m3u"),
            report_json=str(folder / "report.json"),
            report_csv=str(folder / "report.csv"),
            cache=str(self.directory / "cache.json") if options["use_cache"] else None,
        )
        try:
            self.update(job_id, state="loading", stage="Chargement de la playlist…")
            entries, warnings = [], []
            if source["mode"] == "file":
                entries = parse_m3u_with_source(source["text"], source["label"])
            else:
                for index, url in enumerate(source["urls"], 1):
                    if event.is_set():
                        raise CancelledError()
                    self.update(
                        job_id,
                        stage=f"Chargement de la source {index}/{len(source['urls'])}…",
                    )
                    text = download_playlist(
                        url,
                        timeout=args.timeout,
                        retries=args.retries,
                        retry_delay=args.retry_delay,
                        cancel_event=event,
                    )
                    if text:
                        entries.extend(
                            parse_m3u_with_source(
                                text, urlsplit(url).hostname or "Source"
                            )
                        )
                    else:
                        warnings.append(f"La source {index} n'a pas pu être chargée.")
                    if len(entries) > MAX_ENTRIES:
                        raise ValueError(
                            "La version web accepte au maximum 10 000 entrées par analyse."
                        )
            if event.is_set():
                raise CancelledError()
            if not entries:
                raise ValueError(
                    "Aucun flux M3U trouvé. Vérifiez le fichier ou l'adresse de la source."
                )
            if len(entries) > MAX_ENTRIES:
                raise ValueError(
                    "La version web accepte au maximum 10 000 entrées par analyse."
                )
            self.update(
                job_id,
                state="validating",
                stage="Vérification des flux…",
                total=len(entries),
                warnings=warnings,
            )

            def progress(completed, total, working):
                self.update(job_id, completed=completed, total=total, working=working)

            validate = (
                check_stream_with_curl
                if args.validator == "curl"
                else check_stream_with_ffprobe
            )
            results = validate_entries(
                entries, validate, args.validator, args, progress, event
            )
            if event.is_set():
                raise CancelledError()
            self.update(job_id, stage="Chargement des informations des chaînes…")
            self.catalog.enrich(results)
            if event.is_set():
                raise CancelledError()
            self.logos.enrich(results)
            if event.is_set():
                raise CancelledError()
            self.update(job_id, stage="Préparation des téléchargements…")
            selected = filter_best_quality(results)
            ok = save_outputs(results, selected, args)
            if selected and not ok:
                raise OSError("Impossible d'enregistrer les résultats.")
            if (
                not (folder / "report.json").is_file()
                or not (folder / "report.csv").is_file()
            ):
                raise OSError("Impossible d'enregistrer les rapports.")
            report = build_report(results, selected, bool(selected))
            for row, entry in zip(report["streams"], results):
                row.update(playback_metadata(entry))
            with atomic_text_file(str(folder / "browser.json")) as handle:
                json.dump(report, handle, ensure_ascii=False)
            downloads = {
                key: f"/api/jobs/{job_id}/download/{key}"
                for key, (name, _) in ARTIFACTS.items()
                if (folder / name).is_file()
            }
            with self.lock:
                if event.is_set():
                    raise CancelledError()
                self.update(
                    job_id,
                    state="completed",
                    stage="Analyse terminée",
                    summary=report["summary"],
                    downloads=downloads,
                )
        except CancelledError:
            self.update(job_id, state="cancelled", stage="Analyse annulée")
        except Exception as exc:
            logger.exception("Web analysis failed")
            self.update(
                job_id, state="failed", stage="L'analyse n'a pas abouti", error=str(exc)
            )

    def close(self):
        for event in self.events.values():
            event.set()
        self.executor.shutdown(wait=True)


def create_app(data_dir=None):
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_PLAYLIST_SIZE + 1024 * 1024
    manager = JobManager(
        data_dir or Path.home() / ".cache" / "tv-playlist-cleaner" / "web"
    )
    playbacks = PlaybackPool()
    token = secrets.token_urlsafe(32)
    app.extensions["jobs"] = manager
    atexit.register(manager.close)

    @app.before_request
    def guard_local_requests():
        # Prevent DNS rebinding and cross-origin access to a local network-capable tool.
        if urlsplit("http://" + request.host).hostname not in (
            "127.0.0.1",
            "localhost",
            "::1",
        ):
            abort(
                403, description="Cette interface est accessible uniquement en local."
            )
        origin = request.headers.get("Origin")
        if origin and origin != request.host_url.rstrip("/"):
            abort(403, description="Origine de la requête refusée.")
        if request.method != "GET" and request.method != "HEAD":
            if not secrets.compare_digest(
                request.headers.get("X-Playlist-Token", ""), token
            ):
                abort(403, description="Rechargez la page avant de lancer une analyse.")

    @app.after_request
    def response_headers(response):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data: http: https:; connect-src 'self' http: https:; "
            "media-src 'self' blob: http: https:; worker-src 'self' blob:; "
            "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )
        if request.endpoint == "relay_media":
            response.headers["Content-Security-Policy"] = "sandbox; default-src 'none'"
            response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(HTTPException)
    def http_error(exc):
        message = (
            "Le fichier dépasse la limite de 50 Mo."
            if exc.code == 413
            else exc.description
        )
        return jsonify(error=message), exc.code

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/config")
    def config():
        return jsonify(
            token=token,
            default_url=DEFAULT_URL,
            tools={name: check_tool_availability(name) for name in ("curl", "ffprobe")},
            presets=[
                {"id": key, "name": name, "count": len(urls)}
                for key, (name, urls) in PRESETS.items()
            ],
            max_size=MAX_PLAYLIST_SIZE,
        )

    @app.post("/api/jobs")
    def start():
        try:
            options = parse_options(json.loads(request.form.get("options", "{}")))
            if not check_tool_availability(options["validator"]):
                raise ValueError(
                    f"{options['validator']} est introuvable. Installez l'outil puis rechargez la page."
                )
            mode = request.form.get("mode", "url")
            if mode == "file":
                upload = request.files.get("file")
                if (
                    not upload
                    or not upload.filename
                    or Path(upload.filename).suffix.lower() not in (".m3u", ".m3u8")
                ):
                    raise ValueError("Choisissez un fichier .m3u ou .m3u8.")
                content = upload.read(MAX_PLAYLIST_SIZE + 1)
                if len(content) > MAX_PLAYLIST_SIZE:
                    abort(413)
                if not content.strip():
                    raise ValueError("Le fichier est vide.")
                source = {
                    "mode": mode,
                    "label": Path(upload.filename).name[:200],
                    "text": content.decode("utf-8-sig", errors="replace"),
                }
            elif mode == "url":
                url = request.form.get("url", "").strip()
                if not validate_url(url):
                    raise ValueError("Saisissez une URL HTTP ou HTTPS valide.")
                source = {"mode": mode, "label": urlsplit(url).hostname, "urls": [url]}
            elif mode == "preset":
                preset = request.form.get("preset", "")
                if preset not in PRESETS:
                    raise ValueError("Cette catégorie de sources n'existe pas.")
                label, urls = PRESETS[preset]
                source = {"mode": mode, "label": label, "urls": urls}
            else:
                raise ValueError("Type de source inconnu.")
            job_id = manager.create(source, options)
            return jsonify(id=job_id), 202
        except (ValueError, json.JSONDecodeError) as exc:
            return jsonify(error=str(exc)), 400
        except RuntimeError as exc:
            return jsonify(error=str(exc)), 409

    @app.get("/api/jobs/<job_id>")
    def status(job_id):
        job = manager.snapshot(job_id)
        if job is None:
            abort(404, description="Cette analyse n'est plus disponible.")
        return jsonify(job)

    @app.post("/api/jobs/<job_id>/cancel")
    def cancel(job_id):
        if not manager.cancel(job_id):
            abort(404)
        return jsonify(ok=True), 202

    @app.get("/api/jobs/<job_id>/results")
    def results(job_id):
        job = manager.snapshot(job_id)
        if not job or job["state"] != "completed":
            abort(404)
        with (manager.directory / job_id / "browser.json").open(
            encoding="utf-8"
        ) as handle:
            report = json.load(handle)
        return jsonify(report)

    def playable_row(job_id, stream_index):
        job = manager.snapshot(job_id)
        if not job or job["state"] != "completed":
            abort(404)
        with (manager.directory / job_id / "browser.json").open(
            encoding="utf-8"
        ) as handle:
            streams = json.load(handle)["streams"]
        if not 1 <= stream_index <= len(streams):
            abort(404)
        row = streams[stream_index - 1]
        if row["status"] == "invalid":
            abort(404)
        return row

    @app.post("/api/jobs/<job_id>/streams/<int:stream_index>/playback")
    def start_playback(job_id, stream_index):
        row = playable_row(job_id, stream_index)
        try:
            return jsonify(url=playbacks.create(row))
        except ValueError:
            abort(
                422,
                description="Ces réglages de lecture nécessitent VLC. Téléchargez le M3U.",
            )

    @app.get("/api/playback/<session>/<resource>")
    def relay_media(session, resource):
        return media_response(playbacks.get(session), resource)

    @app.get("/api/jobs/<job_id>/streams/<int:stream_index>/playlist")
    def stream_playlist(job_id, stream_index):
        row = playable_row(job_id, stream_index)
        lines = ["#EXTM3U", row["info"]]
        if row["directives"]:
            lines.append(row["directives"])
        lines.append(row["url"])
        return Response(
            "\n".join(lines) + "\n",
            mimetype="audio/x-mpegurl",
            headers={"Content-Disposition": 'attachment; filename="chaine.m3u"'},
        )

    @app.get("/api/jobs/<job_id>/download/<kind>")
    def download(job_id, kind):
        job = manager.snapshot(job_id)
        if not job or job["state"] != "completed" or kind not in job["downloads"]:
            abort(404)
        filename, mimetype = ARTIFACTS[kind]
        return send_file(
            manager.directory / job_id / filename,
            as_attachment=True,
            download_name=filename,
            mimetype=mimetype,
        )

    return app


def main():
    parser = argparse.ArgumentParser(
        description="Interface web locale de Playlist Cleaner"
    )
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data-dir", help="Répertoire local des résultats et du cache")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Le port doit être compris entre 1 et 65535")
    from waitress import serve

    app = create_app(args.data_dir)
    print(f"Playlist Cleaner : http://127.0.0.1:{args.port}", flush=True)
    try:
        serve(
            app,
            host="127.0.0.1",
            port=args.port,
            threads=4,
            max_request_body_size=MAX_PLAYLIST_SIZE + 1024 * 1024,
        )
    finally:
        app.extensions["jobs"].close()


if __name__ == "__main__":
    main()
