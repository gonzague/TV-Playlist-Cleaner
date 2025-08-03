#!/usr/bin/env python3
"""
Script de comparaison des playlists M3U
"""

import re
from collections import defaultdict

def parse_playlist(filename):
    """Parse une playlist M3U et retourne les statistiques."""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.strip().splitlines()
        extinf_lines = [line for line in lines if line.startswith('#EXTINF')]
        url_lines = [line for line in lines if not line.startswith('#') and line.strip()]
        
        channels = []
        for i, info_line in enumerate(extinf_lines):
            if i < len(url_lines):
                # Extract channel name
                name_match = re.search(r',(.+)$', info_line)
                name = name_match.group(1).strip() if name_match else f"Channel_{i+1}"
                
                # Extract quality info
                quality_match = re.search(r'\((\d+p)\)', info_line)
                quality = quality_match.group(1) if quality_match else "unknown"
                
                # Extract group info
                group_match = re.search(r'group-title="([^"]+)"', info_line)
                group = group_match.group(1) if group_match else "General"
                
                channels.append({
                    'name': name,
                    'quality': quality,
                    'group': group,
                    'url': url_lines[i].strip()
                })
        
        return channels
    
    except FileNotFoundError:
        print(f"❌ Fichier {filename} non trouvé")
        return []
    except Exception as e:
        print(f"❌ Erreur lors de la lecture de {filename}: {e}")
        return []

def analyze_playlist(channels, filename):
    """Analyse une playlist et affiche les statistiques."""
    if not channels:
        return
    
    print(f"\n📊 Analyse de {filename}:")
    print(f"  📺 Nombre de chaînes: {len(channels)}")
    
    # Qualités
    qualities = defaultdict(int)
    for channel in channels:
        qualities[channel['quality']] += 1
    
    print(f"  🎯 Qualités:")
    for quality, count in sorted(qualities.items(), key=lambda x: x[1], reverse=True):
        print(f"    {quality}: {count} chaînes")
    
    # Groupes
    groups = defaultdict(int)
    for channel in channels:
        groups[channel['group']] += 1
    
    print(f"  📂 Groupes (top 10):")
    for group, count in sorted(groups.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"    {group}: {count} chaînes")
    
    # Chaînes uniques
    unique_names = set(channel['name'] for channel in channels)
    print(f"  🔍 Noms uniques: {len(unique_names)}")
    
    return {
        'total': len(channels),
        'qualities': dict(qualities),
        'groups': dict(groups),
        'unique_names': len(unique_names)
    }

def compare_playlists(files):
    """Compare plusieurs playlists."""
    print("🔍 Comparaison des playlists")
    print("=" * 50)
    
    results = {}
    all_channels = {}
    
    for filename in files:
        channels = parse_playlist(filename)
        if channels:
            results[filename] = analyze_playlist(channels, filename)
            all_channels[filename] = channels
    
    if len(results) < 2:
        print("\n⚠️  Au moins 2 playlists sont nécessaires pour la comparaison")
        return
    
    # Comparaison
    print(f"\n📈 Comparaison:")
    print(f"  📊 Nombre de chaînes:")
    for filename, stats in results.items():
        print(f"    {filename}: {stats['total']} chaînes")
    
    # Chaînes communes
    if len(all_channels) >= 2:
        filenames = list(all_channels.keys())
        channels1 = set(ch['name'] for ch in all_channels[filenames[0]])
        channels2 = set(ch['name'] for ch in all_channels[filenames[1]])
        
        common = channels1.intersection(channels2)
        only_in_1 = channels1 - channels2
        only_in_2 = channels2 - channels1
        
        print(f"\n  🔄 Chaînes communes: {len(common)}")
        print(f"  ➕ Uniquement dans {filenames[0]}: {len(only_in_1)}")
        print(f"  ➕ Uniquement dans {filenames[1]}: {len(only_in_2)}")
        
        if common:
            print(f"\n  📋 Exemples de chaînes communes:")
            for i, name in enumerate(sorted(list(common))[:5]):
                print(f"    {i+1}. {name}")
            if len(common) > 5:
                print(f"    ... et {len(common) - 5} autres")

def main():
    import sys
    
    if len(sys.argv) < 2:
        print("🔍 Comparateur de playlists M3U")
        print("=" * 40)
        print("\n💡 Utilisation:")
        print("  python compare_playlists.py playlist1.m3u playlist2.m3u")
        print("  python compare_playlists.py filtered.m3u french_only.m3u")
        print("\n📋 Fichiers disponibles:")
        
        import os
        m3u_files = [f for f in os.listdir('.') if f.endswith('.m3u')]
        for i, filename in enumerate(m3u_files, 1):
            channels = parse_playlist(filename)
            print(f"  {i}. {filename} ({len(channels)} chaînes)")
        
        return
    
    files = sys.argv[1:]
    compare_playlists(files)

if __name__ == "__main__":
    main() 