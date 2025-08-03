#!/usr/bin/env python3
"""
Nettoyeur de playlist TV spécialisé pour les chaînes TNT françaises
Filtre et nettoie les playlists pour ne garder que les 25 chaînes TNT principales
"""

import requests
import re
import subprocess
import json
import argparse
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from tqdm import tqdm
import hashlib

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
        "L'ÉQUIPE",
        "L'Equipe",
        "L'Équipe TV",
        "L'Équipe 21",
        "L'Équipe FR",
        "L'ÉQUIPE FR",
        "21. LA CHAÎNE L'ÉQUIPE [1080p-dailymotion.com]",
        "LA CHAÎNE L'ÉQUIPE [1080p-dailymotion.com]",
    ],
    "6Ter": [
        "6Ter",
        "6TER",
        "6Ter HD",
        "6TER HD",
        "6Ter FR",
        "6TER FR",
        "6ter (1080p) [Geo-blocked]",
        "6TER [drm-keycrypted]",
        "1656. 6TER [FR]",
    ],
    "RMC Story": [
        "RMC Story",
        "RMC STORY",
        "RMC Story HD",
        "RMC Story FR",
        "RMC STORY FR",
        "RMC Story [FR]",
        "RMC STORY [FR]",
        "1689. RMC STORY [FR]",
        "1065. RMC Story [1080p-samsungtvplus]",
        "RMC Story [1080p-samsungtvplus]",
    ],
    "RMC Découverte": [
        "RMC Découverte",
        "RMC DÉCOUVERTE",
        "RMC Decouverte",
        "RMC Découverte HD",
        "RMC Découverte FR",
        "RMC DÉCOUVERTE FR",
        "RMC Découverte [FR]",
        "RMC DÉCOUVERTE [FR]",
        "1066. RMC Découverte [1080p-samsungtvplus]",
    ],
    "Chérie 25": [
        "Chérie 25",
        "CHÉRIE 25",
        "Cherie 25",
        "Chérie 25 HD",
        "Chérie 25 FR",
        "CHÉRIE 25 FR",
    ],
}


def download_playlist(url):
    """Download the M3U playlist from the given URL."""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"⚠️  Erreur lors du téléchargement de {url}: {e}")
        return None


def normalize_channel_name(name):
    """Normalize channel name for better matching."""
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


def is_tnt_channel(channel_name):
    """Check if a channel name matches one of the TNT channels."""
    normalized_name = normalize_channel_name(channel_name)

    for official_name, variations in CHANNEL_VARIATIONS.items():
        for variation in variations:
            if normalized_name.lower() == variation.lower():
                return official_name

    return None


def generate_stream_hash(url):
    """Generate a hash for the stream URL to help with deduplication."""
    return hashlib.md5(url.encode()).hexdigest()[:8]


def parse_m3u(m3u_text, source_name="Unknown"):
    """Parse M3U content and extract stream information."""
    entries = []
    lines = m3u_text.strip().splitlines()
    i = 0
    while i < len(lines):
        if lines[i].startswith("#EXTINF"):
            info = lines[i]
            i += 1
            if i < len(lines):
                url = lines[i]
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
                    # Generate normalized name and hash
                    normalized_name = normalize_channel_name(name)
                    stream_hash = generate_stream_hash(url)

                    entries.append(
                        {
                            "name": name,
                            "tnt_name": tnt_channel,  # Official TNT name
                            "normalized_name": normalized_name,
                            "stream_hash": stream_hash,
                            "info": info,
                            "url": url,
                            "source": source_name,
                        }
                    )
        i += 1
    return entries


def check_direct_stream(entry):
    """Check direct stream using ffprobe."""
    try:
        # Use ffprobe to check if the stream is valid and get stream info
        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            "-allowed_extensions",
            "ALL",
            "-user_agent",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15",
            "-timeout",
            "15000000",  # 15 seconds in microseconds
            entry["url"],
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)

        if result.returncode == 0 and result.stdout.strip():
            try:
                # Parse JSON output to get stream information
                stream_info = json.loads(result.stdout)

                # Determine quality from video streams
                quality = "unknown"
                if "streams" in stream_info:
                    video_streams = [
                        s
                        for s in stream_info["streams"]
                        if s.get("codec_type") == "video"
                    ]
                    if video_streams:
                        video_stream = video_streams[0]
                        width = video_stream.get("width", 0)
                        height = video_stream.get("height", 0)

                        if width >= 1920 and height >= 1080:
                            quality = "1080p"
                        elif width >= 1280 and height >= 720:
                            quality = "720p"
                        elif width >= 854 and height >= 480:
                            quality = "480p"
                        elif width > 0 and height > 0:
                            quality = f"{height}p"

                return {
                    "working": True,
                    "quality": quality,
                    "method": "ffprobe",
                    "error": None,
                    **entry,
                }
            except json.JSONDecodeError:
                # If JSON parsing fails but command succeeded, stream is probably working
                return {
                    "working": True,
                    "quality": "unknown",
                    "method": "ffprobe",
                    "error": None,
                    **entry,
                }
        else:
            return {
                "working": False,
                "quality": "unknown",
                "method": "ffprobe",
                "error": result.stderr.strip() or "ffprobe failed",
                **entry,
            }

    except subprocess.TimeoutExpired:
        return {
            "working": False,
            "quality": "unknown",
            "method": "ffprobe",
            "error": "Timeout",
            **entry,
        }
    except Exception as e:
        return {
            "working": False,
            "quality": "unknown",
            "method": "ffprobe",
            "error": str(e),
            **entry,
        }


def check_stream(entry):
    """Check if a stream is working using ffprobe."""
    return check_direct_stream(entry)


def extract_resolution_from_quality(quality_str):
    """Extract resolution number from quality string."""
    if not quality_str or quality_str == "unknown":
        return 0

    # Extract number from quality string (e.g., "720p" -> 720)
    match = re.search(r"(\d+)p", quality_str)
    if match:
        return int(match.group(1))

    # Default values for other quality indicators
    quality_map = {"best": 1080, "worst": 480, "direct_stream": 720}

    return quality_map.get(quality_str.lower(), 0)


def deduplicate_streams(entries):
    """Group streams by TNT channel name and keep multiple sources for fallback."""
    print("🔄 Groupement des flux par chaîne...")

    # Group by TNT channel name
    channel_groups = defaultdict(list)
    for entry in entries:
        channel_groups[entry["tnt_name"]].append(entry)

    deduplicated = []
    for channel_name, streams in channel_groups.items():
        # Sort by quality (highest first) and remove exact URL duplicates
        unique_streams = []
        seen_urls = set()

        for stream in streams:
            if stream["url"] not in seen_urls:
                unique_streams.append(stream)
                seen_urls.add(stream["url"])

        # Sort by quality (highest first)
        unique_streams.sort(
            key=lambda x: extract_resolution_from_quality(x.get("quality", "unknown")),
            reverse=True,
        )

        # Keep up to 5 sources per channel for better fallback coverage
        max_sources = 5
        selected_streams = unique_streams[:max_sources]

        deduplicated.extend(selected_streams)
        print(
            f"  {channel_name}: {len(streams)} flux → {len(selected_streams)} sources gardées"
        )

    print(f"✅ Groupement terminé: {len(entries)} → {len(deduplicated)} flux")
    return deduplicated


def filter_best_quality(entries):
    """Filter to keep the best working stream for each channel with fallback logic."""
    # Group by TNT channel name
    channel_groups = defaultdict(list)
    for entry in entries:
        channel_groups[entry["tnt_name"]].append(entry)

    best_streams = []
    fallback_used = 0

    for channel_name, streams in channel_groups.items():
        # Sort by quality (highest first)
        streams.sort(
            key=lambda x: extract_resolution_from_quality(x.get("quality", "unknown")),
            reverse=True,
        )

        # Find the first working stream
        working_stream = None
        for i, stream in enumerate(streams):
            if stream["working"]:
                working_stream = stream
                if i > 0:  # If not the first (best quality) stream
                    fallback_used += 1
                    print(
                        f"  🔄 {channel_name}: Fallback utilisé (source {i+1}/{len(streams)})"
                    )
                break

        if working_stream:
            best_streams.append(working_stream)
        else:
            print(
                f"  ❌ {channel_name}: Aucune source fonctionnelle ({len(streams)} sources testées)"
            )

    if fallback_used > 0:
        print(f"🔄 Fallback utilisé pour {fallback_used} chaînes")

    return best_streams


def write_playlist(entries, output_file="tnt_channels.m3u"):
    """Write the filtered playlist to a file."""
    from datetime import datetime

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write("# Playlist TNT française - Chaînes principales\n")
        f.write(
            f"# Généré automatiquement le {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}\n"
        )
        f.write(f"# Total: {len(entries)} chaînes TNT valides\n")
        f.write(
            f"# Qualités détectées: {', '.join(set(e.get('quality', 'unknown') for e in entries))}\n\n"
        )

        for entry in entries:
            quality_info = (
                f" ({entry.get('quality', 'unknown')})"
                if entry.get("quality") != "unknown"
                else ""
            )
            f.write(f"{entry['info']}{quality_info}\n")
            f.write(f"{entry['url']}\n\n")


def check_ffprobe_availability():
    """Check if ffprobe is available."""
    try:
        subprocess.run(["ffprobe", "-version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def analyze_failures(failed_streams):
    """Analyze failed streams and provide statistics."""
    error_counts = defaultdict(int)
    method_counts = defaultdict(int)
    source_counts = defaultdict(int)

    for stream in failed_streams:
        error_type = stream.get("error", "Unknown error")
        if "timeout" in error_type.lower():
            error_type = "Timeout"
        elif "http" in error_type.lower():
            error_type = "HTTP Error"

        elif "ffprobe" in error_type.lower():
            error_type = "FFprobe Error"
        else:
            error_type = "Other"

        error_counts[error_type] += 1
        method_counts[stream.get("method", "unknown")] += 1
        source_counts[stream.get("source", "unknown")] += 1

    return error_counts, method_counts, source_counts


def main():
    parser = argparse.ArgumentParser(
        description="Nettoyeur de playlist TV spécialisé pour les chaînes TNT françaises"
    )
    parser.add_argument(
        "--sources", nargs="+", default=M3U_SOURCES, help="URLs des playlists M3U"
    )
    parser.add_argument(
        "--output", default="tnt_channels.m3u", help="Fichier de sortie"
    )

    parser.add_argument(
        "--workers", type=int, default=10, help="Nombre de workers parallèles"
    )
    parser.add_argument("--timeout", type=int, default=15, help="Timeout en secondes")
    parser.add_argument(
        "--no-deduplication", action="store_true", help="Désactiver le dédoublonnage"
    )

    args = parser.parse_args()

    print("🎯 Nettoyeur de playlist TV - Chaînes TNT françaises")
    print("=" * 60)
    print(f"📺 Chaînes cibles: {len(TNT_CHANNELS)} chaînes TNT principales")
    for i, channel in enumerate(TNT_CHANNELS, 1):
        print(f"  {i:2d}. {channel}")
    print()

    print("🔍 Vérification des outils...")
    if not check_ffprobe_availability():
        print("❌ ffprobe n'est pas installé. Veuillez installer FFmpeg.")
        return
    print("✅ ffprobe disponible pour la vérification des flux")

    # Download and parse all sources
    all_entries = []
    print(f"📥 Téléchargement de {len(args.sources)} sources...")

    for i, source_url in enumerate(args.sources, 1):
        print(f"  {i}/{len(args.sources)}: {source_url}")
        m3u_text = download_playlist(source_url)
        if m3u_text:
            source_name = f"Source_{i}"
            entries = parse_m3u(m3u_text, source_name)
            all_entries.extend(entries)
            print(f"    ✅ {len(entries)} flux TNT trouvés")
        else:
            print(f"    ❌ Échec du téléchargement")

    if not all_entries:
        print("❌ Aucun flux TNT trouvé dans les sources")
        return

    print(f"\n🎬 Total: {len(all_entries)} flux TNT trouvés dans toutes les sources")

    # Show found channels
    found_channels = set(entry["tnt_name"] for entry in all_entries)
    missing_channels = set(TNT_CHANNELS) - found_channels

    print(f"\n📊 Chaînes trouvées: {len(found_channels)}/{len(TNT_CHANNELS)}")
    if missing_channels:
        print(f"❌ Chaînes manquantes: {', '.join(missing_channels)}")

    # Deduplicate if not disabled
    if not args.no_deduplication:
        all_entries = deduplicate_streams(all_entries)

    # Process streams with progress bar
    print("⏳ Test des flux TNT (cela peut prendre du temps)...")
    results = []

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        # Submit all tasks
        future_to_entry = {
            executor.submit(check_stream, entry): entry for entry in all_entries
        }

        # Process results with progress bar
        with tqdm(total=len(all_entries), desc="Test des flux", unit="flux") as pbar:
            for future in future_to_entry:
                result = future.result()
                results.append(result)
                pbar.update(1)

                # Update description with current stats
                working_count = len([r for r in results if r["working"]])
                pbar.set_postfix(
                    {"Valides": working_count, "Échoués": len(results) - working_count}
                )

    working = [r for r in results if r["working"]]
    failed = [r for r in results if not r["working"]]

    print(f"\n✅ {len(working)} flux TNT valides trouvés.")
    print(f"❌ {len(failed)} flux TNT échoués.")

    # Analyze failures
    if failed:
        print("\n🔍 Analyse des échecs...")
        error_counts, method_counts, source_counts = analyze_failures(failed)

        print("  Sources:")
        for source, count in source_counts.items():
            print(f"    {source}: {count} flux")

        print("  Méthodes utilisées:")
        for method, count in method_counts.items():
            print(f"    {method}: {count} flux")

        print("  Types d'erreurs:")
        for error_type, count in error_counts.items():
            print(f"    {error_type}: {count} flux")

    if working:
        # Show some quality statistics
        qualities = [r["quality"] for r in working if r["quality"] != "unknown"]
        if qualities:
            print(f"\n📊 Qualités disponibles: {', '.join(set(qualities))}")

    best_streams = filter_best_quality(working)
    print(f"🔝 {len(best_streams)} flux TNT sélectionnés avec la meilleure qualité.")

    if best_streams:
        write_playlist(best_streams, args.output)
        print(f"💾 Playlist TNT enregistrée dans '{args.output}'")

        # Show selected channels
        print("\n📺 Chaînes TNT sélectionnées:")
        for i, stream in enumerate(best_streams, 1):
            quality_info = (
                f" ({stream['quality']})" if stream["quality"] != "unknown" else ""
            )
            method_info = f" [{stream.get('method', 'unknown')}]"
            print(f"  {i:2d}. {stream['tnt_name']}{quality_info}{method_info}")

        # Show missing channels
        working_channels = set(stream["tnt_name"] for stream in best_streams)
        still_missing = set(TNT_CHANNELS) - working_channels
        if still_missing:
            print(f"\n⚠️  Chaînes TNT toujours manquantes: {', '.join(still_missing)}")
    else:
        print("⚠️  Aucun flux TNT valide trouvé.")


if __name__ == "__main__":
    main()
