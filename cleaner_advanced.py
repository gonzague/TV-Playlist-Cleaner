#!/usr/bin/env python3
"""
Advanced TV playlist cleaner with ffprobe support for stream validation.
"""

import argparse
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
from tqdm import tqdm

# Import shared utilities
from playlist_utils import (
    download_playlist,
    parse_m3u,
    check_stream_with_ffprobe,
    filter_best_quality,
    write_playlist,
    check_tool_availability,
    analyze_failures,
    setup_logging
)

# Configuration
M3U_URL = "https://iptv-org.github.io/iptv/countries/fr.m3u"

logger = logging.getLogger(__name__)


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments with validation."""
    parser = argparse.ArgumentParser(description="Nettoyeur de playlist TV avancé")
    parser.add_argument("--url", default=M3U_URL, help="URL de la playlist M3U")
    parser.add_argument("--output", default="filtered.m3u", help="Fichier de sortie")
    parser.add_argument(
        "--workers",
        type=int,
        default=10,
        help="Nombre de workers parallèles (1-50)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=15,
        help="Timeout en secondes (1-60)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Mode verbeux (debug logging)"
    )

    args = parser.parse_args()

    # Validate arguments
    if not (1 <= args.workers <= 50):
        parser.error("Workers must be between 1 and 50")

    if not (1 <= args.timeout <= 60):
        parser.error("Timeout must be between 1 and 60 seconds")

    return args


def main() -> None:
    """Main entry point for the advanced playlist cleaner."""
    args = parse_arguments()

    # Setup logging
    setup_logging(verbose=args.verbose)

    logger.info("🔍 Vérification des outils...")
    if not check_tool_availability("ffprobe"):
        logger.error("❌ ffprobe n'est pas installé. Veuillez installer FFmpeg.")
        return
    logger.info("✅ ffprobe disponible pour la vérification des flux")

    logger.info("📥 Téléchargement de la playlist...")
    try:
        m3u_text = download_playlist(args.url, timeout=args.timeout)
        if not m3u_text:
            logger.error("❌ Échec du téléchargement de la playlist")
            return

        entries = parse_m3u(m3u_text)
        logger.info(f"🎬 {len(entries)} flux trouvés.")
    except Exception as e:
        logger.error(f"❌ Erreur lors du téléchargement: {e}", exc_info=True)
        return

    # Process streams with progress bar
    logger.info("⏳ Test des flux (cela peut prendre du temps)...")
    results: List[Dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        # Submit all tasks
        future_to_entry = {
            executor.submit(check_stream_with_ffprobe, entry, args.timeout): entry
            for entry in entries
        }

        # Process results with progress bar (as_completed for better performance)
        with tqdm(total=len(entries), desc="Test des flux", unit="flux") as pbar:
            for future in as_completed(future_to_entry):
                result = future.result()
                results.append(result)
                pbar.update(1)

                # Update description with current stats
                working_count = len([r for r in results if r.get("working")])
                pbar.set_postfix(
                    {"Valides": working_count, "Échoués": len(results) - working_count}
                )

    working = [r for r in results if r.get("working")]
    failed = [r for r in results if not r.get("working")]

    logger.info(f"\n✅ {len(working)} flux valides trouvés.")
    logger.info(f"❌ {len(failed)} flux échoués.")

    # Analyze failures
    if failed:
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
            logger.info(f"\n📊 Qualités disponibles: {', '.join(unique_qualities)}")

    best_streams = filter_best_quality(working)
    logger.info(f"🔝 {len(best_streams)} flux sélectionnés avec la meilleure qualité.")

    if best_streams:
        write_playlist(best_streams, args.output)
        logger.info(f"💾 Playlist enregistrée dans '{args.output}'")

        # Show some examples of selected streams
        logger.info("\n📺 Exemples de flux sélectionnés:")
        for i, stream in enumerate(best_streams[:5]):  # Show first 5
            quality_info = (
                f" ({stream.get('quality')})" if stream.get("quality") != "unknown" else ""
            )
            method_info = f" [{stream.get('method', 'unknown')}]"
            logger.info(f"  {i+1}. {stream['name']}{quality_info}{method_info}")
        if len(best_streams) > 5:
            logger.info(f"  ... et {len(best_streams) - 5} autres")
    else:
        logger.warning("⚠️  Aucun flux valide trouvé.")


if __name__ == "__main__":
    main()
