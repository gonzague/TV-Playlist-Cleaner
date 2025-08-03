#!/usr/bin/env python3
"""
Script de démonstration du nettoyeur de playlist TV
"""

import subprocess
import sys
import os

def run_command(cmd, description):
    """Exécute une commande et affiche le résultat."""
    print(f"\n🚀 {description}")
    print(f"   Commande: {' '.join(cmd)}")
    print("-" * 60)
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Succès")
            if result.stdout:
                print(result.stdout[-500:])  # Derniers 500 caractères
        else:
            print("❌ Échec")
            if result.stderr:
                print(result.stderr[-300:])  # Derniers 300 caractères
    except Exception as e:
        print(f"💥 Erreur: {e}")

def main():
    print("🎬 Démonstration du Nettoyeur de Playlist TV")
    print("=" * 60)
    
    # Vérifier les fichiers disponibles
    print("\n📋 Fichiers disponibles:")
    m3u_files = [f for f in os.listdir('.') if f.endswith('.m3u')]
    for i, filename in enumerate(m3u_files, 1):
        size = os.path.getsize(filename) if os.path.exists(filename) else 0
        print(f"  {i}. {filename} ({size:,} bytes)")
    
    # 1. Afficher les catégories disponibles
    run_command(
        ["python", "cleaner_config.py"],
        "Affichage des catégories disponibles"
    )
    
    # 2. Analyser les sources
    run_command(
        ["python", "sources_config.py"],
        "Configuration des sources M3U"
    )
    
    # 3. Comparer les playlists existantes
    if len(m3u_files) >= 2:
        run_command(
            ["python", "compare_playlists.py", m3u_files[0], m3u_files[1]],
            f"Comparaison des playlists {m3u_files[0]} et {m3u_files[1]}"
        )
    
    # 4. Test rapide d'une playlist
    if m3u_files:
        run_command(
            ["python", "test_quick.py"],
            f"Test rapide de la playlist {m3u_files[0]}"
        )
    
    print("\n" + "=" * 60)
    print("🎯 Démonstration terminée !")
    print("\n💡 Prochaines étapes:")
    print("  1. python cleaner_config.py french --direct-only")
    print("  2. python cleaner_config.py english --direct-only")
    print("  3. python cleaner_config.py all --direct-only --workers 20")
    print("  4. python compare_playlists.py playlist1.m3u playlist2.m3u")

if __name__ == "__main__":
    main() 