#!/usr/bin/env python3
"""
Multi-source TV playlist cleaner with intelligent deduplication.
"""

import re
import hashlib
import argparse
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
from tqdm import tqdm

# Import shared utilities
from playlist_utils import (
    download_playlist,
    check_stream_with_ffprobe,
    filter_best_quality,
    write_playlist,
    check_tool_availability,
    analyze_failures,
    setup_logging
)

# Sources M3U multiples
M3U_SOURCES = [
    "https://iptv-org.github.io/iptv/countries/fr.m3u",
    "https://raw.githubusercontent.com/ipstreet312/freeiptv/refs/heads/master/all.m3u",
    "https://raw.githubusercontent.com/Paradise-91/ParaTV/refs/heads/main/playlists/paratv/main/paratv-highest.m3u",
]

logger = logging.getLogger(__name__)


def normalize_channel_name(name: str) -> str:
    """
    Normalize channel name for better deduplication.

    Args:
        name: Channel name to normalize

    Returns:
        Normalized channel name in lowercase

    Example:
        >>> normalize_channel_name("TF1 HD [FR]")
        'tf1'
    """
    # Remove common suffixes and prefixes
    name = name.strip()

    # Remove quality indicators
    name = re.sub(r"\s*\(\d+p\)", "", name)
    name = re.sub(r"\s*\[.*?\]", "", name)
    name = re.sub(r"\s*\{.*?\}", "", name)

    # Remove common prefixes
    name = re.sub(r"^\[.*?\]\s*", "", name)
    name = re.sub(r"^\|.*?\|\s*", "", name)

    # Normalize common variations
    name = name.replace("FRANCE 2", "France 2")
    name = name.replace("FRANCE 3", "France 3")
    name = name.replace("TF1", "TF1")
    name = name.replace("M6", "M6")
    name = name.replace("BFM TV", "BFM TV")
    name = name.replace("CNEWS", "CNEWS")
    name = name.replace("LCI", "LCI")

    # Remove extra spaces and normalize
    name = re.sub(r"\s+", " ", name).strip()

    return name.lower()


def parse_m3u_with_source(m3u_text: str, source_name: str = "Unknown") -> List[Dict[str, str]]:
    """
    Parse M3U content and extract stream information with source tracking.

    Args:
        m3u_text: Raw M3U playlist content
        source_name: Name of the source for tracking

    Returns:
        List of stream entries with normalized names and hashes
    """
    entries = []
    lines = m3u_text.strip().splitlines()
    i = 0

    while i < len(lines):
        if lines[i].startswith("#EXTINF"):
            info = lines[i]
            i += 1
            if i < len(lines) and not lines[i].startswith("#"):
                url = lines[i].strip()

                # Skip invalid URLs
                if not url or url.startswith("#"):
                    i += 1
                    continue

                # Try to extract channel name from tvg-name attribute first, then from the end of the line
                tvg_match = re.search(r'tvg-name="([^"]+)"', info)
                if tvg_match:
                    name = tvg_match.group(1).strip()
                else:
                    # Extract from the end of the line after the comma
                    name_match = re.search(r",(.+)$", info)
                    name = name_match.group(1).strip() if name_match else "Unknown"

                # Generate normalized name and hash (using SHA256 instead of MD5)
                normalized_name = normalize_channel_name(name)
                stream_hash = hashlib.sha256(url.encode()).hexdigest()[:16]

                entries.append({
                    "name": name,
                    "normalized_name": normalized_name,
                    "stream_hash": stream_hash,
                    "info": info,
                    "url": url,
                    "source": source_name,
                })
        i += 1

    return entries


def deduplicate_streams(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Remove duplicate streams based on URL hash and normalized name.

    Args:
        entries: List of stream entries

    Returns:
        Deduplicated list of stream entries
    """
    seen_hashes = set()
    unique_entries = []

    for entry in entries:
        stream_hash = entry.get("stream_hash")
        if stream_hash and stream_hash not in seen_hashes:
            seen_hashes.add(stream_hash)
            unique_entries.append(entry)

    logger.info(f"Deduplication: {len(entries)} -> {len(unique_entries)} streams")
    return unique_entries


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments with validation."""
    parser = argparse.ArgumentParser(
        description="Nettoyeur de playlist TV multi-sources avec dédoublonnage"
    )
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
        "--no-deduplication",
        action="store_true",
        help="Désactiver le dédoublonnage"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Mode verbeux (debug logging)"
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        help="Sources M3U personnalisées (URLs)"
    )

    args = parser.parse_args()

    # Validate arguments
    if not (1 <= args.workers <= 50):
        parser.error("Workers must be between 1 and 50")

    if not (1 <= args.timeout <= 60):
        parser.error("Timeout must be between 1 and 60 seconds")

    return args


def main() -> None:
    """Main entry point for the multi-source playlist cleaner."""
    args = parse_arguments()

    # Setup logging
    setup_logging(verbose=args.verbose)

    logger.info("🔍 Vérification des outils...")
    if not check_tool_availability("ffprobe"):
        logger.error("❌ ffprobe n'est pas installé. Veuillez installer FFmpeg.")
        return
    logger.info("✅ ffprobe disponible")

    # Use custom sources or default
    sources = args.sources if args.sources else M3U_SOURCES
    logger.info(f"📥 Téléchargement de {len(sources)} playlists...")

    all_entries: List[Dict[str, Any]] = []

    for i, url in enumerate(sources, 1):
        logger.info(f"  [{i}/{len(sources)}] Téléchargement de {url[:60]}...")
        m3u_text = download_playlist(url, timeout=args.timeout)

        if m3u_text:
            source_name = url.split("/")[-2] if "/" in url else f"Source{i}"
            entries = parse_m3u_with_source(m3u_text, source_name)
            logger.info(f"  ✓ {len(entries)} flux trouvés")
            all_entries.extend(entries)
        else:
            logger.warning(f"  ✗ Échec du téléchargement")

    logger.info(f"🎬 Total: {len(all_entries)} flux de toutes les sources")

    # Deduplicate if requested
    if not args.no_deduplication:
        logger.info("🔄 Dédoublonnage des flux...")
        all_entries = deduplicate_streams(all_entries)

    # Process streams with progress bar
    logger.info("⏳ Test des flux (cela peut prendre du temps)...")
    results: List[Dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        # Submit all tasks
        future_to_entry = {
            executor.submit(check_stream_with_ffprobe, entry, args.timeout): entry
            for entry in all_entries
        }

        # Process results with progress bar (as_completed for better performance)
        with tqdm(total=len(all_entries), desc="Test des flux", unit="flux") as pbar:
            for future in as_completed(future_to_entry):
                result = future.result()
                results.append(result)
                pbar.update(1)

                # Update stats
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
        for error_type, count in sorted(error_counts.items(), key=lambda x: -x[1])[:5]:
            logger.info(f"    {error_type}: {count} flux")

    if working:
        # Show quality statistics
        qualities = [r.get("quality") for r in working if r.get("quality") != "unknown"]
        if qualities:
            unique_qualities = sorted(set(qualities))
            logger.info(f"\n📊 Qualités disponibles: {', '.join(unique_qualities)}")

    best_streams = filter_best_quality(working, deduplicate=not args.no_deduplication)
    logger.info(f"🔝 {len(best_streams)} flux sélectionnés avec la meilleure qualité.")

    if best_streams:
        write_playlist(best_streams, args.output)
        logger.info(f"💾 Playlist enregistrée dans '{args.output}'")

        # Show some examples
        logger.info("\n📺 Exemples de flux sélectionnés:")
        for i, stream in enumerate(best_streams[:5]):
            quality_info = (
                f" ({stream.get('quality')})" if stream.get("quality") != "unknown" else ""
            )
            source_info = f" [{stream.get('source', 'unknown')}]"
            logger.info(f"  {i+1}. {stream['name']}{quality_info}{source_info}")
        if len(best_streams) > 5:
            logger.info(f"  ... et {len(best_streams) - 5} autres")
    else:
        logger.warning("⚠️  Aucun flux valide trouvé.")


if __name__ == "__main__":
    main()
