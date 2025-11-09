#!/usr/bin/env python3
"""
M3U playlist comparison script.

Analyzes and compares multiple M3U playlists, showing statistics about
channels, qualities, groups, and finding common/unique channels.
"""

import re
import os
import sys
import logging
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Set, Optional, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def parse_playlist(filename: str) -> List[Dict[str, str]]:
    """
    Parse an M3U playlist and return channel information.

    Args:
        filename: Path to M3U playlist file

    Returns:
        List of channel dictionaries with name, quality, group, and URL

    Example:
        >>> channels = parse_playlist("test.m3u")
        >>> len(channels) > 0
        True
    """
    try:
        playlist_path = Path(filename)
        if not playlist_path.exists():
            logger.error(f"❌ Fichier {filename} non trouvé")
            return []

        with open(playlist_path, "r", encoding="utf-8") as f:
            content = f.read()

        lines = content.strip().splitlines()
        extinf_lines = [line for line in lines if line.startswith("#EXTINF")]
        url_lines = [
            line for line in lines if not line.startswith("#") and line.strip()
        ]

        channels = []
        for i, info_line in enumerate(extinf_lines):
            if i < len(url_lines):
                # Extract channel name
                name_match = re.search(r",(.+)$", info_line)
                name = name_match.group(1).strip() if name_match else f"Channel_{i+1}"

                # Extract quality info
                quality_match = re.search(r"\((\d+p)\)", info_line)
                quality = quality_match.group(1) if quality_match else "unknown"

                # Extract group info
                group_match = re.search(r'group-title="([^"]+)"', info_line)
                group = group_match.group(1) if group_match else "General"

                channels.append({
                    "name": name,
                    "quality": quality,
                    "group": group,
                    "url": url_lines[i].strip(),
                })

        logger.debug(f"Parsed {len(channels)} channels from {filename}")
        return channels

    except PermissionError:
        logger.error(f"❌ Permission refusée pour lire {filename}")
        return []
    except UnicodeDecodeError:
        logger.error(f"❌ Erreur d'encodage dans {filename}")
        return []
    except Exception as e:
        logger.error(f"❌ Erreur lors de la lecture de {filename}: {e}")
        return []


def analyze_playlist(channels: List[Dict[str, str]], filename: str) -> Optional[Dict[str, any]]:
    """
    Analyze a playlist and display statistics.

    Args:
        channels: List of channel dictionaries
        filename: Name of the playlist file

    Returns:
        Dictionary with statistics or None if no channels
    """
    if not channels:
        logger.warning(f"⚠️  Pas de chaînes dans {filename}")
        return None

    logger.info(f"\n📊 Analyse de {filename}:")
    logger.info(f"  📺 Nombre de chaînes: {len(channels)}")

    # Qualities
    qualities: Dict[str, int] = defaultdict(int)
    for channel in channels:
        qualities[channel["quality"]] += 1

    logger.info(f"  🎯 Qualités:")
    for quality, count in sorted(qualities.items(), key=lambda x: x[1], reverse=True):
        logger.info(f"    {quality}: {count} chaînes")

    # Groups
    groups: Dict[str, int] = defaultdict(int)
    for channel in channels:
        groups[channel["group"]] += 1

    logger.info(f"  📂 Groupes (top 10):")
    for group, count in sorted(groups.items(), key=lambda x: x[1], reverse=True)[:10]:
        display_group = group if len(group) <= 40 else group[:37] + "..."
        logger.info(f"    {display_group}: {count} chaînes")

    # Unique channels
    unique_names = set(channel["name"] for channel in channels)
    logger.info(f"  🔍 Noms uniques: {len(unique_names)}")

    # Duplicate detection
    duplicates = len(channels) - len(unique_names)
    if duplicates > 0:
        logger.info(f"  ⚠️  Doublons détectés: {duplicates} chaînes")

    return {
        "total": len(channels),
        "qualities": dict(qualities),
        "groups": dict(groups),
        "unique_names": len(unique_names),
        "duplicates": duplicates,
    }


def find_common_channels(
    all_channels: Dict[str, List[Dict[str, str]]]
) -> Tuple[Set[str], Dict[str, Set[str]]]:
    """
    Find common and unique channels across playlists.

    Args:
        all_channels: Dictionary mapping filenames to channel lists

    Returns:
        Tuple of (common_channels, unique_per_playlist)
    """
    if len(all_channels) < 2:
        return set(), {}

    filenames = list(all_channels.keys())
    channel_sets = {
        filename: set(ch["name"] for ch in channels)
        for filename, channels in all_channels.items()
    }

    # Find common channels (intersection of all)
    common = set.intersection(*channel_sets.values())

    # Find unique channels per playlist
    unique_per_playlist = {}
    for filename, channels in channel_sets.items():
        # Channels only in this playlist
        other_channels = set.union(*(s for f, s in channel_sets.items() if f != filename))
        unique_per_playlist[filename] = channels - other_channels

    return common, unique_per_playlist


def compare_playlists(files: List[str]) -> None:
    """
    Compare multiple playlists and display statistics.

    Args:
        files: List of playlist filenames to compare
    """
    logger.info("🔍 Comparaison des playlists")
    logger.info("=" * 50)

    results = {}
    all_channels = {}

    # Parse all playlists
    for filename in files:
        channels = parse_playlist(filename)
        if channels:
            results[filename] = analyze_playlist(channels, filename)
            all_channels[filename] = channels

    if not results:
        logger.error("\n❌ Aucune playlist valide trouvée")
        return

    if len(results) < 2:
        logger.warning("\n⚠️  Au moins 2 playlists sont nécessaires pour la comparaison")
        return

    # Comparison
    logger.info(f"\n📈 Comparaison:")
    logger.info(f"  📊 Nombre de chaînes:")
    for filename, stats in results.items():
        if stats:
            logger.info(f"    {filename}: {stats['total']} chaînes")

    # Find common and unique channels
    common, unique_per_playlist = find_common_channels(all_channels)

    if common:
        logger.info(f"\n  🔄 Chaînes communes à toutes les playlists: {len(common)}")
        logger.info(f"\n  📋 Exemples de chaînes communes:")
        for i, name in enumerate(sorted(list(common))[:10]):
            logger.info(f"    {i+1}. {name}")
        if len(common) > 10:
            logger.info(f"    ... et {len(common) - 10} autres")

    # Unique channels per playlist
    logger.info(f"\n  ➕ Chaînes uniques par playlist:")
    for filename, unique_channels in unique_per_playlist.items():
        logger.info(f"    {filename}: {len(unique_channels)} chaînes uniques")

        if unique_channels and len(unique_channels) <= 10:
            logger.info(f"      Exemples:")
            for name in sorted(list(unique_channels))[:5]:
                logger.info(f"        • {name}")

    # Quality comparison
    logger.info(f"\n  🎯 Comparaison des qualités:")
    for filename, stats in results.items():
        if stats and stats["qualities"]:
            best_quality = max(stats["qualities"].items(), key=lambda x: (x[0] != "unknown", x[1]))
            logger.info(f"    {filename}: {best_quality[1]} chaînes en {best_quality[0]}")


def list_available_playlists() -> List[Tuple[str, int]]:
    """
    List all M3U files in current directory.

    Returns:
        List of (filename, channel_count) tuples
    """
    playlists = []
    for file_path in Path(".").glob("*.m3u"):
        if file_path.is_file():
            channels = parse_playlist(str(file_path))
            playlists.append((str(file_path), len(channels)))

    return sorted(playlists, key=lambda x: x[1], reverse=True)


def main() -> None:
    """Main entry point for playlist comparison."""
    if len(sys.argv) < 2:
        logger.info("🔍 Comparateur de playlists M3U")
        logger.info("=" * 40)
        logger.info("\n💡 Utilisation:")
        logger.info("  python compare_playlists.py playlist1.m3u playlist2.m3u")
        logger.info("  python compare_playlists.py filtered.m3u french_only.m3u")

        logger.info("\n📋 Fichiers M3U disponibles:")
        playlists = list_available_playlists()

        if not playlists:
            logger.warning("  Aucun fichier .m3u trouvé dans le répertoire courant")
        else:
            for i, (filename, count) in enumerate(playlists, 1):
                size = Path(filename).stat().st_size
                size_kb = size / 1024
                logger.info(f"  {i}. {filename} ({count} chaînes, {size_kb:.1f} KB)")

        return

    files = sys.argv[1:]

    # Validate files exist
    valid_files = []
    for filename in files:
        if Path(filename).exists():
            valid_files.append(filename)
        else:
            logger.error(f"❌ Fichier non trouvé: {filename}")

    if not valid_files:
        logger.error("\n❌ Aucun fichier valide fourni")
        sys.exit(1)

    if len(valid_files) < 2:
        logger.warning("\n⚠️  Un seul fichier fourni, affichage de l'analyse uniquement")

    compare_playlists(valid_files)


if __name__ == "__main__":
    main()
