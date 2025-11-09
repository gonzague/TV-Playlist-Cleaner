#!/usr/bin/env python3
"""
Specialized TV playlist cleaner for French TNT (Télévision Numérique Terrestre) channels.

Filters and cleans playlists to keep only the 25 main French TNT channels with intelligent
name matching and quality selection.
"""

import re
import hashlib
import argparse
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional
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

# Sources M3U pour les chaînes françaises
M3U_SOURCES = [
    "https://raw.githubusercontent.com/Paradise-91/ParaTV/refs/heads/main/playlists/paratv/main/paratv-highest.m3u",
    "https://iptv-org.github.io/iptv/countries/fr.m3u",
]

# Liste des 25 chaînes TNT principales en France
TNT_CHANNELS = [
    "TF1",
    "France 2",
    "France 3",
    "France 4",
    "France 5",
    "M6",
    "Arte",
    "La Chaîne parlementaire",
    "W9",
    "TMC",
    "TFX",
    "Gulli",
    "BFM TV",
    "CNEWS",
    "LCI",
    "Franceinfo",
    "CSTAR",
    "T18",
    "NOVO19",
    "TF1 Séries Films",
    "L'Équipe",
    "6Ter",
    "RMC Story",
    "RMC Découverte",
    "Chérie 25",
]

# Variations de noms pour une meilleure correspondance
CHANNEL_VARIATIONS = {
    "TF1": [
        "TF1",
        "TF1 HD",
        "TF1 FHD",
        "TF1 HD FR",
        "TF1 FR",
        "TF1 [FR]",
        "1. TF1 [FR]",
        "TF1_",
        "TF1-",
        "TF1 (backup SD)",
        "TF1 (720p) [Geo-blocked]",
        "TF1 HD (720p)",
        "1693. TF1 HD [FR]",
        "TF1 HD [FR]",
    ],
    "France 2": [
        "France 2",
        "FRANCE 2",
        "France2",
        "FRANCE2",
        "France 2 HD",
        "FRANCE 2 HD",
        "France-2",
        "FRANCE-2",
        "france-2-highest",
    ],
    "France 3": [
        "France 3",
        "FRANCE 3",
        "France3",
        "FRANCE3",
        "France 3 HD",
        "FRANCE 3 HD",
        "3. France 3 [1080p-france.tv]",
        "49. France 3 [SSAI][1080p-france.tv]",
        "France 3 [1080p-france.tv]",
        "France 3 [SSAI][1080p-france.tv]",
    ],
    "France 4": [
        "France 4",
        "FRANCE 4",
        "France4",
        "FRANCE4",
        "France 4 HD",
        "FRANCE 4 HD",
        "112. FRANCE 4 [1080p-france.tv]",
        "FRANCE 4 [1080p-france.tv]",
    ],
    "France 5": [
        "France 5",
        "FRANCE 5",
        "France5",
        "FRANCE5",
        "France 5 HD",
        "FRANCE 5 HD",
        "5. France 5 [1080p-france.tv]",
        "France 5 [1080p-france.tv]",
    ],
    "M6": [
        "M6",
        "M6 HD",
        "M6 FHD",
        "M6 HD FR",
        "M6 FR",
        "M6 [Geo-blocked]",
        "M6 CH/SWISS",
        "M6 [drm-keycrypted]",
    ],
    "Arte": [
        "Arte",
        "ARTE",
        "Arte HD",
        "ARTE HD",
        "Arte FR",
        "ARTE FR",
        "7. Arte [720p-arte.tv]",
        "46. ARTE [1080p-tf1.fr]",
        "47. Arte [1080p-france.tv]",
        "Arte [720p-arte.tv]",
        "ARTE [1080p-tf1.fr]",
        "Arte [1080p-france.tv]",
    ],
    "La Chaîne parlementaire": [
        "La Chaîne parlementaire",
        "LCP",
        "LCP-AN",
        "LCP Assemblée nationale",
        "LCP-AN FR",
        "1682. LCP [FR]",
        "8. LCP [1080p-france.tv]",
        "51. LCP-AN [1080p-dailymotion.com]",
        "LCP [1080p-france.tv]",
        "LCP-AN [1080p-dailymotion.com]",
    ],
    "W9": [
        "W9",
        "W9 HD",
        "W9 FHD",
        "W9 HD FR",
        "W9 FR",
        "9. W9 [720p-tf1.fr]",
        "W9 [720p-tf1.fr]",
        "1701. W9 [FR]",
        "W9 [FR]",
    ],
    "TMC": [
        "TMC",
        "TMC HD",
        "TMC FHD",
        "TMC HD FR",
        "TMC FR",
        "10. TMC [720p-tf1.fr]",
        "TMC [720p-tf1.fr]",
    ],
    "TFX": [
        "TFX",
        "TFX HD",
        "TFX FHD",
        "TFX HD FR",
        "TFX FR",
        "TFX [FR]",
        "TFX Séries Films",
        "TFX Séries Films [FR]",
        "11. TFX [720p-tf1.fr]",
        "1695. TFX [FR]",
    ],
    "Gulli": ["Gulli", "GULLI", "Gulli HD", "GULLI HD", "Gulli FR", "GULLI FR"],
    "BFM TV": [
        "BFM TV",
        "BFM",
        "BFM TV HD",
        "BFM HD",
        "BFM TV FR",
        "BFM FR",
        "1659. BFM TV [FR]",
        "13. BFM TV [1080p-rmcbfmplay.com]",
        "BFM TV [1080p-rmcbfmplay.com]",
        "1000. BFM TV [1080p-samsungtvplus]",
        "BFM TV [1080p-samsungtvplus]",
    ],
    "CNEWS": [
        "CNEWS",
        "CNews",
        "CNEWS HD",
        "CNews HD",
        "CNEWS FR",
        "CNews FR",
        "14. CNEWS [720p-tf1.fr]",
        "CNEWS [720p-tf1.fr]",
        "14. C NEWS [1080p-canalplus.com]",
        "C NEWS [1080p-canalplus.com]",
    ],
    "LCI": ["LCI", "LCI HD", "LCI FHD", "LCI HD FR", "LCI FR"],
    "Franceinfo": [
        "Franceinfo",
        "France Info",
        "FRANCEINFO",
        "France Info TV",
        "France Info FR",
        "FRANCEINFO FR",
        "FRANCE INFO",
        "FRANCE INFO [FR]",
        "1677. FRANCE INFO [FR]",
    ],
    "CSTAR": [
        "CSTAR",
        "CStar",
        "CSTAR HD",
        "CStar HD",
        "CSTAR FR",
        "CStar FR",
        "17. CStar [1080p-dailymotion.com]",
        "CStar [1080p-dailymotion.com]",
    ],
    "T18": ["T18", "T18 HD", "T18 HD FR", "T18 FR"],
    "NOVO19": [
        "NOVO19",
        "NOVO",
        "NOVO 19",
        "NOVO19 HD",
        "NOVO19 FR",
        "NOVO FR",
        "19. NOVO [720p-tf1.fr]",
        "NOVO [720p-tf1.fr]",
    ],
    "TF1 Séries Films": [
        "TF1 Séries Films",
        "TF1 Séries",
        "TF1 Series Films",
        "TF1 Series",
        "TF1 Séries Films FR",
        "TF1 Séries FR",
        "TF1 Séries Films [FR]",
        "TF1 Séries [FR]",
        "20. TF1 Séries Films [720p-tf1.fr]",
    ],
    "L'Équipe": [
        "L'Équipe",
        "L'Equipe",
        "L EQUIPE",
        "LEQUIPE",
        "L'Équipe HD",
        "L'Equipe HD",
        "21. L'Équipe [1080p-rmcbfmplay.com]",
        "L'Équipe [1080p-rmcbfmplay.com]",
    ],
    "6Ter": [
        "6Ter",
        "6TER",
        "6ter",
        "6 Ter",
        "6 TER",
        "6Ter HD",
        "6TER HD",
        "22. 6ter [720p-tf1.fr]",
        "6ter [720p-tf1.fr]",
    ],
    "RMC Story": [
        "RMC Story",
        "RMC STORY",
        "RMC Story HD",
        "RMC STORY HD",
        "23. RMC Story [720p-tf1.fr]",
        "RMC Story [720p-tf1.fr]",
    ],
    "RMC Découverte": [
        "RMC Découverte",
        "RMC Decouverte",
        "RMC DÉCOUVERTE",
        "RMC DECOUVERTE",
        "RMC Découverte HD",
        "RMC Decouverte HD",
        "24. RMC Découverte [720p-tf1.fr]",
        "RMC Découverte [720p-tf1.fr]",
    ],
    "Chérie 25": [
        "Chérie 25",
        "Cherie 25",
        "CHÉRIE 25",
        "CHERIE 25",
        "Chérie 25 HD",
        "Chérie 25 FR",
        "CHÉRIE 25 FR",
    ],
}

logger = logging.getLogger(__name__)


def normalize_channel_name(name: str) -> str:
    """
    Normalize channel name for better matching (TNT-specific version).

    Args:
        name: Channel name to normalize

    Returns:
        Normalized channel name

    Example:
        >>> normalize_channel_name("TF1 HD [FR]")
        'TF1 HD'
    """
    # Remove common suffixes and prefixes
    name = name.strip()

    # Remove quality indicators
    name = re.sub(r"\s*\(\d+p\)", "", name)
    name = re.sub(r"\s*\{.*?\}", "", name)

    # Remove common prefixes (but keep the name part)
    name = re.sub(r"^\[.*?\]\s*", "", name)
    name = re.sub(r"^\|.*?\|\s*", "", name)

    # Remove extra spaces and normalize
    name = re.sub(r"\s+", " ", name).strip()

    return name


def is_tnt_channel(channel_name: str) -> Optional[str]:
    """
    Check if a channel name matches one of the TNT channels.

    Args:
        channel_name: Channel name to check

    Returns:
        Official TNT channel name if matched, None otherwise

    Example:
        >>> is_tnt_channel("TF1 HD [FR]")
        'TF1'
        >>> is_tnt_channel("Some Random Channel")
        None
    """
    normalized_name = normalize_channel_name(channel_name)

    for official_name, variations in CHANNEL_VARIATIONS.items():
        for variation in variations:
            if normalized_name.lower() == variation.lower():
                return official_name

    return None


def parse_m3u_tnt_filter(m3u_text: str, source_name: str = "Unknown") -> List[Dict[str, str]]:
    """
    Parse M3U content and filter for TNT channels only.

    Args:
        m3u_text: Raw M3U playlist content
        source_name: Name of the source for tracking

    Returns:
        List of TNT channel entries with normalized names and hashes
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

                # Check if this is a TNT channel
                tnt_channel = is_tnt_channel(name)
                if tnt_channel:
                    # Generate normalized name and hash (using SHA256 instead of MD5)
                    normalized_name = normalize_channel_name(name)
                    stream_hash = hashlib.sha256(url.encode()).hexdigest()[:16]

                    entries.append({
                        "name": name,
                        "tnt_name": tnt_channel,  # Official TNT name
                        "normalized_name": normalized_name,
                        "stream_hash": stream_hash,
                        "info": info,
                        "url": url,
                        "source": source_name,
                    })
        i += 1

    logger.debug(f"Found {len(entries)} TNT channels from {source_name}")
    return entries


def deduplicate_streams(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Remove duplicate streams based on URL hash.

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

    logger.info(f"Deduplication: {len(entries)} -> {len(unique_entries)} TNT streams")
    return unique_entries


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments with validation."""
    parser = argparse.ArgumentParser(
        description="Nettoyeur de playlist TV spécialisé pour les chaînes TNT françaises"
    )
    parser.add_argument(
        "--output",
        default="tnt_channels.m3u",
        help="Fichier de sortie"
    )
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
    """Main entry point for the TNT playlist cleaner."""
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
    logger.info(f"📥 Téléchargement de {len(sources)} playlists pour les chaînes TNT...")

    all_entries: List[Dict[str, Any]] = []

    for i, url in enumerate(sources, 1):
        logger.info(f"  [{i}/{len(sources)}] Téléchargement de {url[:60]}...")
        m3u_text = download_playlist(url, timeout=args.timeout)

        if m3u_text:
            source_name = url.split("/")[-2] if "/" in url else f"Source{i}"
            entries = parse_m3u_tnt_filter(m3u_text, source_name)
            logger.info(f"  ✓ {len(entries)} chaînes TNT trouvées")
            all_entries.extend(entries)
        else:
            logger.warning(f"  ✗ Échec du téléchargement")

    logger.info(f"🎬 Total: {len(all_entries)} flux TNT de toutes les sources")

    # Deduplicate
    logger.info("🔄 Dédoublonnage des flux...")
    all_entries = deduplicate_streams(all_entries)

    # Show which TNT channels were found
    found_channels = set(entry.get("tnt_name") for entry in all_entries)
    missing_channels = set(TNT_CHANNELS) - found_channels
    logger.info(f"📺 {len(found_channels)}/25 chaînes TNT trouvées")
    if missing_channels:
        logger.warning(f"⚠️  Chaînes manquantes: {', '.join(sorted(missing_channels))}")

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
        with tqdm(total=len(all_entries), desc="Test des flux TNT", unit="flux") as pbar:
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

    # Select best quality for each TNT channel
    best_streams = filter_best_quality(working, deduplicate=True)
    logger.info(f"🔝 {len(best_streams)} flux TNT sélectionnés avec la meilleure qualité.")

    # Show which TNT channels we have working streams for
    working_tnt_channels = set(entry.get("tnt_name") for entry in best_streams)
    logger.info(f"📺 {len(working_tnt_channels)}/25 chaînes TNT disponibles")

    if best_streams:
        write_playlist(best_streams, args.output)
        logger.info(f"💾 Playlist TNT enregistrée dans '{args.output}'")

        # Show all TNT channels found
        logger.info("\n📺 Chaînes TNT disponibles:")
        # Sort by TNT channel name
        sorted_streams = sorted(best_streams, key=lambda x: TNT_CHANNELS.index(x.get("tnt_name", "")))
        for i, stream in enumerate(sorted_streams, 1):
            quality_info = (
                f" ({stream.get('quality')})" if stream.get("quality") != "unknown" else ""
            )
            resolution_info = ""
            if stream.get("width") and stream.get("height"):
                resolution_info = f" {stream.get('width')}x{stream.get('height')}"
            source_info = f" [{stream.get('source', 'unknown')}]"
            logger.info(
                f"  {i}. {stream.get('tnt_name', stream['name'])}{quality_info}{resolution_info}{source_info}"
            )

        # Show missing channels
        if missing_tnt := (set(TNT_CHANNELS) - working_tnt_channels):
            logger.warning(f"\n⚠️  Chaînes TNT non disponibles ({len(missing_tnt)}):")
            for channel in sorted(missing_tnt):
                logger.warning(f"  - {channel}")
    else:
        logger.warning("⚠️  Aucun flux TNT valide trouvé.")


if __name__ == "__main__":
    main()
