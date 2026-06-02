#!/usr/bin/env python3
"""
Basic TV playlist cleaner using curl for stream validation.
"""

import logging
import subprocess  # nosec B404
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
from tqdm import tqdm

# Import shared utilities
from playlist_utils import (
    download_playlist,
    parse_m3u,
    check_stream_with_curl,
    extract_resolution_from_quality,
    filter_best_quality,
    write_playlist,
    check_tool_availability,
    get_tool_path,
    analyze_failures,
    setup_logging,
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


def main() -> None:
    """Main entry point for the basic playlist cleaner."""
    # Setup logging
    setup_logging(verbose=False)

    logger.info("🔍 Vérification de curl...")
    if not check_tool_availability("curl"):
        logger.error("❌ curl n'est pas installé ou n'est pas dans le PATH.")
        logger.error("📦 Installez-le avec votre gestionnaire de paquets système")
        return

    logger.info("📥 Téléchargement de la playlist...")
    try:
        m3u_text = download_playlist(M3U_URL)
        if not m3u_text:
            logger.error("❌ Échec du téléchargement de la playlist")
            return

        entries = parse_m3u(m3u_text)
        logger.info(f"🎬 {len(entries)} flux trouvés. Test en cours avec curl...")
    except Exception as e:
        logger.error(f"❌ Erreur lors du téléchargement: {e}", exc_info=True)
        return

    # Process streams with curl and progress bar
    logger.info("⏳ Test des flux (cela peut prendre du temps)...")
    results: List[Dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all tasks
        future_to_entry = {
            executor.submit(check_stream_with_curl, entry, TIMEOUT): entry
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

    if best_streams:
        output_file = "filtered.m3u"
        write_playlist(best_streams, output_file)
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


if __name__ == "__main__":
    main()
