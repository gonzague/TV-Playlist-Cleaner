#!/usr/bin/env python3
"""
Basic TV playlist cleaner using curl for stream validation.
"""

import logging
import argparse
import sys
import subprocess  # nosec B404
from typing import List, Dict, Any, Optional

from validation_pipeline import (
    add_processing_arguments,
    validate_processing_arguments,
    validate_entries,
    save_outputs,
)

# Import shared utilities
from playlist_utils import (
    download_playlist,
    parse_m3u,
    check_stream_with_curl,
    check_stream_with_ffprobe,
    extract_resolution_from_quality,
    filter_best_quality,
    write_playlist,
    check_tool_availability,
    get_tool_path,
    analyze_failures,
    setup_logging,
    MAX_PLAYLIST_SIZE,
)

# Configuration
M3U_URL = "https://iptv-org.github.io/iptv/countries/fr.m3u"
TIMEOUT = 15  # seconds
MAX_WORKERS = 10

logger = logging.getLogger(__name__)


def check_curl_availability() -> bool:
    """Backward-compatible helper for callers that imported it from cleaner."""
    curl_path = get_tool_path("curl")
    if not curl_path:
        return False

    try:
        result = subprocess.run(  # nosec B603
            [curl_path, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def parse_arguments(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Nettoyeur de playlists TV M3U")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--url", default=M3U_URL, help="URL de la playlist M3U")
    source.add_argument("--input", help="Fichier M3U local")
    parser.add_argument("--output", default="filtered.m3u", help="Fichier de sortie")
    parser.add_argument(
        "--workers", type=int, default=MAX_WORKERS, help="Workers (1-50)"
    )
    parser.add_argument("--timeout", type=int, default=TIMEOUT, help="Timeout (1-60 s)")
    parser.add_argument("--verbose", action="store_true", help="Journal détaillé")
    parser.add_argument(
        "--validator",
        choices=("curl", "ffprobe"),
        default="curl",
        help="curl : disponibilité HTTP ; ffprobe : analyse du média et de sa résolution",
    )
    add_processing_arguments(parser)
    args = parser.parse_args(argv)
    validate_processing_arguments(args, parser)
    if not 1 <= args.workers <= 50:
        parser.error("--workers doit être compris entre 1 et 50")
    if not 1 <= args.timeout <= 60:
        parser.error("--timeout doit être compris entre 1 et 60")
    return args


def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point for the basic playlist cleaner."""
    args = parse_arguments(argv)
    # Setup logging
    setup_logging(verbose=args.verbose)

    logger.info(f"🔍 Vérification de {args.validator}...")
    if not check_tool_availability(args.validator):
        logger.error(
            f"❌ {args.validator} n'est pas installé ou n'est pas dans le PATH."
        )
        logger.error("📦 Installez-le avec votre gestionnaire de paquets système")
        return 1

    logger.info("📥 Chargement de la playlist...")
    try:
        if args.input:
            with open(args.input, "rb") as source:
                content = source.read(MAX_PLAYLIST_SIZE + 1)
            if len(content) > MAX_PLAYLIST_SIZE:
                raise ValueError("Playlist trop volumineuse (maximum 50 Mo)")
            m3u_text = content.decode("utf-8-sig", errors="replace")
        else:
            m3u_text = download_playlist(
                args.url,
                timeout=args.timeout,
                retries=args.retries,
                retry_delay=args.retry_delay,
            )
        if not m3u_text:
            logger.error("❌ Playlist vide ou impossible à charger")
            return 1

        entries = parse_m3u(m3u_text)
        if not entries:
            logger.error("❌ Aucune entrée M3U trouvée")
            return 1
        logger.info(f"🎬 {len(entries)} flux trouvés. Test avec {args.validator}...")
    except Exception as e:
        logger.error(f"❌ Erreur lors du chargement: {e}", exc_info=args.verbose)
        return 1

    # Process streams with curl and progress bar
    logger.info("⏳ Test des flux (cela peut prendre du temps)...")
    validate = (
        check_stream_with_curl
        if args.validator == "curl"
        else check_stream_with_ffprobe
    )
    results = validate_entries(entries, validate, args.validator, args)

    working = [r for r in results if r.get("working")]
    failed = [r for r in results if not r.get("working")]

    logger.info(f"\n✅ {len(working)} flux valides trouvés.")
    logger.info(f"❌ {len(failed)} flux échoués.")

    # Analyze failures if all streams failed
    if len(working) == 0 and len(failed) > 0:
        logger.info("\n🔍 Analyse des échecs...")
        error_counts, method_counts = analyze_failures(failed)

        logger.info("  Méthodes utilisées:")
        for method, count in method_counts.items():
            logger.info(f"    {method}: {count} flux")

        logger.info("  Types d'erreurs:")
        for error_type, count in error_counts.items():
            logger.info(f"    {error_type}: {count} flux")

        # Show some example errors
        logger.info("\n📋 Exemples d'erreurs:")
        for i, stream in enumerate(failed[:3]):
            error_msg = stream.get("error", "Unknown error")[:100]
            logger.info(f"  {stream['name']}: {error_msg}...")

    if working:
        # Show some quality statistics
        qualities = [r.get("quality") for r in working if r.get("quality") != "unknown"]
        if qualities:
            unique_qualities = sorted(set(qualities))
            logger.info(f"📊 Qualités disponibles: {', '.join(unique_qualities)}")

    best_streams = filter_best_quality(working)
    logger.info(f"🔝 {len(best_streams)} flux sélectionnés avec la meilleure qualité.")

    output_ok = save_outputs(results, best_streams, args)
    if best_streams:
        output_file = args.output
        if not output_ok:
            return 1
        logger.info(f"💾 Playlist enregistrée dans '{output_file}'")

        # Show some examples of selected streams
        logger.info("\n📺 Exemples de flux sélectionnés:")
        for i, stream in enumerate(best_streams[:5]):  # Show first 5
            quality_info = (
                f" ({stream.get('quality')})"
                if stream.get("quality") != "unknown"
                else ""
            )
            logger.info(f"  {i+1}. {stream['name']}{quality_info}")
        if len(best_streams) > 5:
            logger.info(f"  ... et {len(best_streams) - 5} autres")
    else:
        logger.warning("⚠️  Aucun flux valide trouvé.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
