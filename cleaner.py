import requests
import re
import subprocess
import json
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from tqdm import tqdm

M3U_URL = "https://iptv-org.github.io/iptv/countries/fr.m3"
TIMEOUT = 15  # seconds

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

def check_stream_with_curl(entry):
    """Use curl to check if the stream works and get basic information."""
    url = entry['url']
    try:
        # Use curl to check if the stream is accessible
        cmd = [
            "curl", "-I", "--connect-timeout", str(TIMEOUT),
            "--max-time", str(TIMEOUT), "--silent", "--fail",
            url
        ]
        
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=TIMEOUT + 5
        )
        
        if result.returncode == 0:
            # Extract content type and other headers
            headers = result.stdout
            content_type = ""
            if "content-type:" in headers.lower():
                content_type_match = re.search(r'content-type:\s*([^\r\n]+)', headers, re.IGNORECASE)
                if content_type_match:
                    content_type = content_type_match.group(1).strip()
            
            # Determine quality based on URL patterns or content type
            quality = "unknown"
            width = 0
            height = 0
            
            # Try to extract quality from URL patterns
            if "1080" in url or "1920" in url:
                quality = "1080p"
                width = 1920
                height = 1080
            elif "720" in url or "1280" in url:
                quality = "720p"
                width = 1280
                height = 720
            elif "480" in url:
                quality = "480p"
                width = 854
                height = 480
            
            return {
                **entry, 
                'working': True,
                'quality': quality,
                'width': width,
                'height': height,
                'content_type': content_type
            }
        
        # If we get here, the stream failed - let's capture the error
        error_msg = result.stderr.strip() if result.stderr else "Unknown error"
        return {
            **entry, 
            'working': False, 
            'quality': 'failed', 
            'width': 0, 
            'height': 0,
            'error': error_msg
        }
        
    except subprocess.TimeoutExpired:
        return {**entry, 'working': False, 'quality': 'timeout', 'width': 0, 'height': 0, 'error': 'Timeout'}
    except Exception as e:
        return {**entry, 'working': False, 'quality': f'error: {str(e)}', 'width': 0, 'height': 0, 'error': str(e)}

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
    with open(output_file, "w", encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        for entry in entries:
            f.write(f"{entry['info']}\n{entry['url']}\n")

def check_curl_availability():
    """Check if curl is available on the system."""
    try:
        result = subprocess.run(["curl", "--version"], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False

def analyze_failures(failed_streams):
    """Analyze why streams are failing and provide insights."""
    error_counts = defaultdict(int)
    for stream in failed_streams:
        error = stream.get('error', 'Unknown error')
        # Extract the main error type
        if 'timeout' in error.lower():
            error_counts['Timeout'] += 1
        elif '404' in error or 'not found' in error.lower():
            error_counts['404/Not Found'] += 1
        elif '403' in error or 'forbidden' in error.lower():
            error_counts['403/Forbidden'] += 1
        elif 'ssl' in error.lower() or 'certificate' in error.lower():
            error_counts['SSL/Certificate Error'] += 1
        else:
            error_counts['Other'] += 1
    
    return error_counts

def main():
    print("🔍 Vérification de curl...")
    if not check_curl_availability():
        print("❌ curl n'est pas installé ou n'est pas dans le PATH.")
        print("📦 Installez-le avec votre gestionnaire de paquets système")
        return
    
    print("📥 Téléchargement de la playlist...")
    try:
        m3u_text = download_playlist(M3U_URL)
        entries = parse_m3u(m3u_text)
        print(f"🎬 {len(entries)} flux trouvés. Test en cours avec curl...")
    except Exception as e:
        print(f"❌ Erreur lors du téléchargement: {e}")
        return

    # Process streams with curl and progress bar
    print("⏳ Test des flux (cela peut prendre du temps)...")
    results = []
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        # Submit all tasks
        future_to_entry = {executor.submit(check_stream_with_curl, entry): entry for entry in entries}
        
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
    
    # Analyze failures if all streams failed
    if len(working) == 0 and len(failed) > 0:
        print("\n🔍 Analyse des échecs...")
        error_counts = analyze_failures(failed)
        for error_type, count in error_counts.items():
            print(f"  {error_type}: {count} flux")
        
        # Show some example errors
        print("\n📋 Exemples d'erreurs:")
        for i, stream in enumerate(failed[:3]):
            print(f"  {stream['name']}: {stream.get('error', 'Unknown error')[:100]}...")
    
    if working:
        # Show some quality statistics
        qualities = [r['quality'] for r in working if r['quality'] != 'unknown']
        if qualities:
            print(f"📊 Qualités disponibles: {', '.join(set(qualities))}")

    best_streams = filter_best_quality(working)
    print(f"🔝 {len(best_streams)} flux sélectionnés avec la meilleure qualité.")

    if best_streams:
        write_playlist(best_streams)
        print("💾 Playlist enregistrée dans 'filtered.m3u'")
        
        # Show some examples of selected streams
        print("\n📺 Exemples de flux sélectionnés:")
        for i, stream in enumerate(best_streams[:5]):  # Show first 5
            quality_info = f" ({stream['quality']})" if stream['quality'] != 'unknown' else ""
            print(f"  {i+1}. {stream['name']}{quality_info}")
        if len(best_streams) > 5:
            print(f"  ... et {len(best_streams) - 5} autres")
    else:
        print("⚠️  Aucun flux valide trouvé.")

if __name__ == "__main__":
    main()
