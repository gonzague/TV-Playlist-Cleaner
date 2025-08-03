#!/usr/bin/env python3
"""
Version avancée du nettoyeur de playlist TV avec support pour différents types de flux
"""

import requests
import re
import subprocess
import json
import argparse
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from tqdm import tqdm

M3U_URL = "https://iptv-org.github.io/iptv/countries/fr.m3u"


def download_playlist(url):
    """Download the M3U playlist from the given URL."""
    response = requests.get(url)
    response.raise_for_status()
    return response.text

def parse_m3u(m3u_text):
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
                match = re.search(r'tvg-name="([^"]+)"', info) or re.search(r',(.+)$', info)
                name = match.group(1).strip() if match else "Unknown"
                entries.append({'name': name, 'info': info, 'url': url})
        i += 1
    return entries





def check_direct_stream(entry):
    """Check direct stream URLs using ffprobe"""
    url = entry['url']
    name = entry['name']
    
    try:
        # Use ffprobe to check if the stream is valid and get stream info
        cmd = [
            'ffprobe', 
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            '-allowed_extensions', 'ALL',
            '-user_agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15',
            '-timeout', '15000000',  # 15 seconds in microseconds
            url
        ]
        
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=20
        )
        
        if result.returncode == 0 and result.stdout.strip():
            try:
                # Parse JSON output to get stream information
                stream_info = json.loads(result.stdout)
                
                # Determine quality from video streams
                quality = 'unknown'
                width = 0
                height = 0
                
                if 'streams' in stream_info:
                    video_streams = [s for s in stream_info['streams'] if s.get('codec_type') == 'video']
                    if video_streams:
                        video_stream = video_streams[0]
                        width = video_stream.get('width', 0)
                        height = video_stream.get('height', 0)
                        
                        if width >= 1920 and height >= 1080:
                            quality = '1080p'
                        elif width >= 1280 and height >= 720:
                            quality = '720p'
                        elif width >= 854 and height >= 480:
                            quality = '480p'
                        elif width > 0 and height > 0:
                            quality = f'{height}p'
                
                return {
                    **entry,
                    'working': True,
                    'quality': quality,
                    'width': width,
                    'height': height,
                    'method': 'ffprobe'
                }
            except json.JSONDecodeError:
                # If JSON parsing fails but command succeeded, stream is probably working
                return {
                    **entry,
                    'working': True,
                    'quality': 'unknown',
                    'width': 0,
                    'height': 0,
                    'method': 'ffprobe'
                }
        else:
            return {
                **entry,
                'working': False,
                'quality': 'failed',
                'width': 0,
                'height': 0,
                'error': result.stderr.strip() or 'ffprobe failed',
                'method': 'ffprobe'
            }
            
    except subprocess.TimeoutExpired:
        return {
            **entry,
            'working': False,
            'quality': 'failed',
            'width': 0,
            'height': 0,
            'error': 'Timeout',
            'method': 'ffprobe'
        }
    except Exception as e:
        return {
            **entry,
            'working': False,
            'quality': 'failed',
            'width': 0,
            'height': 0,
            'error': str(e),
            'method': 'ffprobe'
        }

def check_stream(entry):
    """Check stream using ffprobe"""
    return check_direct_stream(entry)

def extract_resolution_from_quality(quality_str):
    """Extract width and height from quality string."""
    # Common quality patterns: 720p, 1080p, 480p, etc.
    resolution_pattern = r'(\d+)p'
    match = re.search(resolution_pattern, quality_str)
    
    if match:
        height = int(match.group(1))
        # Estimate width based on common aspect ratios (16:9)
        width = int(height * 16 / 9)
        return {'width': width, 'height': height}
    
    # Try to extract explicit dimensions like "1920x1080"
    dimension_pattern = r'(\d+)x(\d+)'
    match = re.search(dimension_pattern, quality_str)
    
    if match:
        width = int(match.group(1))
        height = int(match.group(2))
        return {'width': width, 'height': height}
    
    return {'width': 0, 'height': 0}

def filter_best_quality(entries):
    """Group streams by name and select the best quality for each."""
    grouped = defaultdict(list)
    for entry in entries:
        if entry['working']:
            grouped[entry['name']].append(entry)
    
    best_streams = []
    for name, group in grouped.items():
        if group:
            # Sort by height (resolution) and select the best
            best = max(group, key=lambda e: (e['height'], e['width']))
            best_streams.append(best)
    
    return best_streams

def write_playlist(entries, output_file="filtered.m3u"):
    """Write the filtered playlist to an M3U file."""
    from datetime import datetime
    
    with open(output_file, "w", encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        f.write(f"# Playlist générée le {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}\n")
        f.write(f"# Total: {len(entries)} flux valides\n")
        f.write(f"# Qualités détectées: {', '.join(set(e.get('quality', 'unknown') for e in entries))}\n\n")
        
        for entry in entries:
            quality_info = f" ({entry.get('quality', 'unknown')})" if entry.get('quality') != 'unknown' else ""
            f.write(f"{entry['info']}{quality_info}\n")
            f.write(f"{entry['url']}\n\n")



def check_ffprobe_availability():
    """Check if ffprobe is available on the system."""
    try:
        result = subprocess.run(["ffprobe", "-version"], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False

def analyze_failures(failed_streams):
    """Analyze why streams are failing and provide insights."""
    error_counts = defaultdict(int)
    method_counts = defaultdict(int)
    
    for stream in failed_streams:
        error = stream.get('error', 'Unknown error')
        method = stream.get('method', 'unknown')
        method_counts[method] += 1
        
        # Extract the main error type
        if 'No plugin can handle URL' in error:
            error_counts['No plugin can handle URL'] += 1
        elif 'No playable streams found' in error:
            error_counts['No playable streams found'] += 1
        elif 'timeout' in error.lower():
            error_counts['Timeout'] += 1
        elif '404' in error or 'not found' in error.lower():
            error_counts['404/Not Found'] += 1
        elif '403' in error or 'forbidden' in error.lower():
            error_counts['403/Forbidden'] += 1
        elif 'ssl' in error.lower() or 'certificate' in error.lower():
            error_counts['SSL/Certificate Error'] += 1
        elif 'ffprobe' in error.lower():
            error_counts['FFprobe Error'] += 1
        else:
            error_counts['Other'] += 1
    
    return error_counts, method_counts

def main():
    parser = argparse.ArgumentParser(description='Nettoyeur de playlist TV avancé')
    parser.add_argument('--url', default=M3U_URL, help='URL de la playlist M3U')
    parser.add_argument('--output', default='filtered.m3u', help='Fichier de sortie')

    parser.add_argument('--workers', type=int, default=10, help='Nombre de workers parallèles')
    parser.add_argument('--timeout', type=int, default=15, help='Timeout en secondes')
    
    args = parser.parse_args()
    
    print("🔍 Vérification des outils...")
    if not check_ffprobe_availability():
        print("❌ ffprobe n'est pas installé. Veuillez installer FFmpeg.")
        return
    print("✅ ffprobe disponible pour la vérification des flux")
    
    print("📥 Téléchargement de la playlist...")
    try:
        m3u_text = download_playlist(args.url)
        entries = parse_m3u(m3u_text)
        print(f"🎬 {len(entries)} flux trouvés.")
    except Exception as e:
        print(f"❌ Erreur lors du téléchargement: {e}")
        return

    # Process streams with progress bar
    print("⏳ Test des flux (cela peut prendre du temps)...")
    results = []
    
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        # Submit all tasks
        future_to_entry = {executor.submit(check_stream, entry): entry for entry in entries}
        
        # Process results with progress bar
        with tqdm(total=len(entries), desc="Test des flux", unit="flux") as pbar:
            for future in future_to_entry:
                result = future.result()
                results.append(result)
                pbar.update(1)
                
                # Update description with current stats
                working_count = len([r for r in results if r['working']])
                pbar.set_postfix({
                    'Valides': working_count,
                    'Échoués': len(results) - working_count
                })

    working = [r for r in results if r['working']]
    failed = [r for r in results if not r['working']]
    
    print(f"\n✅ {len(working)} flux valides trouvés.")
    print(f"❌ {len(failed)} flux échoués.")
    
    # Analyze failures
    if failed:
        print("\n🔍 Analyse des échecs...")
        error_counts, method_counts = analyze_failures(failed)
        
        print("  Méthodes utilisées:")
        for method, count in method_counts.items():
            print(f"    {method}: {count} flux")
        
        print("  Types d'erreurs:")
        for error_type, count in error_counts.items():
            print(f"    {error_type}: {count} flux")
        
        # Show some example errors
        print("\n📋 Exemples d'erreurs:")
        for i, stream in enumerate(failed[:3]):
            error_msg = stream.get('error', 'Unknown error')[:100]
            print(f"  {stream['name']}: {error_msg}...")
    
    if working:
        # Show some quality statistics
        qualities = [r['quality'] for r in working if r['quality'] != 'unknown']
        if qualities:
            print(f"\n📊 Qualités disponibles: {', '.join(set(qualities))}")

    best_streams = filter_best_quality(working)
    print(f"🔝 {len(best_streams)} flux sélectionnés avec la meilleure qualité.")

    if best_streams:
        write_playlist(best_streams, args.output)
        print(f"💾 Playlist enregistrée dans '{args.output}'")
        
        # Show some examples of selected streams
        print("\n📺 Exemples de flux sélectionnés:")
        for i, stream in enumerate(best_streams[:5]):  # Show first 5
            quality_info = f" ({stream['quality']})" if stream['quality'] != 'unknown' else ""
            method_info = f" [{stream.get('method', 'unknown')}]"
            print(f"  {i+1}. {stream['name']}{quality_info}{method_info}")
        if len(best_streams) > 5:
            print(f"  ... et {len(best_streams) - 5} autres")
    else:
        print("⚠️  Aucun flux valide trouvé.")

if __name__ == "__main__":
    main() 